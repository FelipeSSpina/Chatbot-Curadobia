# file: code/webapi/app.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, asyncio, time
from typing import AsyncGenerator, Dict, List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from code.context.session import SessionManager
from code.fallbacks.manager import FallbackManager
from code.ambiguity.detector import AmbiguityDetector
from code.ambiguity.clarify import clarify
from code.fluxos_intencao.guards import (
    coerce_intent, extract_cep, extract_size, extract_color, extract_brand,
    looks_like_product_query, has_shipping_terms, is_pref_only
)
from code.fluxos_intencao.chatbot import classify_intent, generate_response

# -------------------- Config ----------------------------------------------------
MIN_CONF, MIN_GAP = 0.50, 0.20
SESSION = SessionManager(ttl_seconds=3600)
FALLBACK = FallbackManager()
AMB = AmbiguityDetector(
    confidence_threshold=MIN_CONF,
    gap_threshold=MIN_GAP,
    mode=os.getenv("AMB_MODE", "any")  # mais sensível a low-signal
)
AMB_MAX_CLARIFY = int(os.getenv("AMB_MAX_CLARIFY", "2"))

# Rótulos amigáveis para clarificação
INTENT_HUMAN: Dict[str, str] = {
    "pedido_sugestao": "pedido de sugestão",
    "tamanho_modelagem": "tamanho/modelagem",
    "frete_prazo": "frete/prazo",
    "formas_pagamento": "pagamento",
    "saudacao": "saudação",
    "agradecimento": "agradecimento",
    "nao_entendi": "não entendi",
    "ajuda": "ajuda",
    "troca_devolucao": "troca/devolução",
    "atendimento_humano": "atendimento humano",
}

# -------------------- FastAPI ---------------------------------------------------
app = FastAPI(title="Curadobia Web API", version="1.0.0")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    os.environ.get("CORS_ORIGIN", ""),
]
ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# -------------------- Modelos ---------------------------------------------------
class ChatRequest(BaseModel):
    # Compat: aceitar message (novo) ou prompt (legado)
    message: Optional[str] = None
    prompt: Optional[str] = None
    session_id: Optional[str] = "web-session"
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    gap_top2: float
    need_cep: bool = False
    events: List[Dict] = []

# -------------------- Utils -----------------------------------------------------
def _normalize_pred(pred: dict) -> dict:
    pred = dict(pred or {})
    intent = pred.get("intent") or "nao_entendi"
    probs = pred.get("probs") or {}
    conf = pred.get("conf")
    try:
        conf = float(conf)
    except Exception:
        conf = None
    if conf is None or conf == 0.0:
        try:
            conf = float(probs.get(intent, 0.0))
        except Exception:
            conf = 0.0
    try:
        items = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        p1 = float(items[0][1]) if items else float(conf or 0.0)
        p2 = float(items[1][1]) if len(items) > 1 else 0.0
        gap = max(0.0, p1 - p2)
        top3 = items[:3]
    except Exception:
        gap, top3 = 0.0, []
    pred.update(intent=intent, conf=float(conf or 0.0), gap=float(gap), top3=top3)
    pred.setdefault("probs", probs)
    return pred

def _runtime_profile(state):
    p = SESSION.get_profile(state) or {}
    for k in ("tamanho_sup", "tamanho_inf", "cor", "marca", "cep"):
        v = SESSION.get_pref(state.session_id, k, None)
        if v:
            p[k] = v
    if state.slots.get("cep") and not p.get("cep"):
        p["cep"] = state.slots["cep"]
    return p

# ===== Helpers de ambiguidade ===================================================
def _clarify_key_for(res) -> str:
    if res.reason == "small_gap_top2":
        return "ambigua_gap_top2"
    if "low_signal" in res.reason:
        return "ambigua_low_signal"
    if res.reason == "low_confidence":
        return "nao_entendi"
    if res.reason == "combined_score":
        m = res.metrics or {}
        s_conf, s_gap, s_low = m.get("s_conf", 0.0), m.get("s_gap", 0.0), m.get("s_low", 0.0)
        if s_low >= max(s_conf, s_gap):
            return "ambigua_low_signal"
        if s_gap >= s_conf:
            return "ambigua_gap_top2"
        return "nao_entendi"
    return "ambigua_generica"

def _amb_update_state(state, res) -> None:
    amb = state.slots.setdefault("ambiguity", {})
    amb["reason"] = res.reason
    amb["metrics"] = res.metrics
    amb["triggered_rules"] = res.triggered_rules
    state.slots["clarify_count"] = int(state.slots.get("clarify_count", 0)) + 1
    state.slots["clarify_last_ts"] = int(time.time())

def _reset_clarify_if_resolved(state) -> None:
    """Zera contadores e remove o slot 'ambiguity' quando saímos de clarificação."""
    if state.slots.get("clarify_count") or state.slots.get("ambiguity") or state.slots.get("clarify_last_ts"):
        state.slots["clarify_count"] = 0
        state.slots.pop("clarify_last_ts", None)
        state.slots.pop("ambiguity", None)

def _friendly_top12(pred: dict) -> tuple[str, str]:
    labels = [lbl for (lbl, _p) in (pred.get("top3") or [])]
    if pred.get("intent") and pred["intent"] not in labels:
        labels.insert(0, pred["intent"])
    dedup: List[str] = []
    for l in labels:
        if l and l not in dedup:
            dedup.append(l)
    dedup += ["", ""]
    top1_raw, top2_raw = dedup[0], dedup[1]
    return INTENT_HUMAN.get(top1_raw, top1_raw), INTENT_HUMAN.get(top2_raw, top2_raw)

# ================================================================================

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Compat: usar message (novo) ou prompt (legado)
    raw_msg = (req.message if (req.message is not None and req.message != "") else req.prompt)
    if not (raw_msg and str(raw_msg).strip()):
        raise HTTPException(status_code=422, detail="The request body must include 'message' or 'prompt'.")

    state = SESSION.load(req.session_id or "web-session", user_id=req.user_id)
    message = str(raw_msg).strip()

    # ---------------- interceptadores diretos (antes de tudo) ------------------
    # Falar com humano / atendimento
    if re.search(r"\b(falar|conversar|chamar|preciso|quero)\b.*\b(humano|pessoa|atendente|atendimento|suporte)\b", message, re.I) \
       or re.search(r"\b(humano|atendente|atendimento|suporte)\b", message, re.I):
        reply = "Posso chamar alguém do time para te atender. Quer que eu encaminhe agora?"
        SESSION.append_turn(state, role="user", text=message, intent="atendimento_humano")
        SESSION.append_turn(state, role="bot",  text=reply,   intent="atendimento_humano")
        SESSION.save(state)
        return ChatResponse(reply=reply, intent="atendimento_humano", confidence=1.0, gap_top2=1.0,
                            need_cep=state.slots.get("need_cep", False),
                            events=state.slots.get("fallback_events", []))

    # Devolução / troca (FAQ simples)
    if re.search(r"\b(devolu[cç][aã]o|troca|devolver|trocar)\b", message, re.I):
        reply = ("Claro! Para **trocas e devoluções** (compras online), você tem até **7 dias corridos** após o recebimento, "
                 "conforme o CDC. Me passa o **nº do pedido** e o motivo que eu abro a solicitação pra você.")
        SESSION.append_turn(state, role="user", text=message, intent="troca_devolucao")
        SESSION.append_turn(state, role="bot",  text=reply,   intent="troca_devolucao")
        SESSION.save(state)
        return ChatResponse(reply=reply, intent="troca_devolucao", confidence=1.0, gap_top2=1.0,
                            need_cep=state.slots.get("need_cep", False),
                            events=state.slots.get("fallback_events", []))

    # Ajuda genérica
    if re.search(r"\b(ajuda|ajudar|help|socorro)\b", message, re.I):
        reply = "Posso ajudar com: **sugestões de roupas**, **frete/prazo**, **pagamento** ou **trocas/devoluções**. Qual desses?"
        SESSION.append_turn(state, role="user", text=message, intent="ajuda")
        SESSION.append_turn(state, role="bot",  text=reply,   intent="ajuda")
        SESSION.save(state)
        return ChatResponse(reply=reply, intent="ajuda", confidence=1.0, gap_top2=1.0,
                            need_cep=state.slots.get("need_cep", False),
                            events=state.slots.get("fallback_events", []))

    # --- extrações básicas ------------------------------------------------------
    size  = extract_size(message)
    color = extract_color(message)
    brand = extract_brand(message)
    cep   = extract_cep(message)

    if size:  SESSION.remember_pref(state.session_id, "tamanho_sup", size, ttl_sec=None)
    if color: SESSION.remember_pref(state.session_id, "cor",         color, ttl_sec=None)
    if brand: SESSION.remember_pref(state.session_id, "marca",       brand, ttl_sec=None)
    if cep:
        state.slots["cep"] = cep
        SESSION.remember_pref(state.session_id, "cep", cep, ttl_sec=None)

    # Frete: atalho ANTES de classificar (reduz dependência do modelo)
    if has_shipping_terms(message):
        if cep:
            reply = f"Com base no seu CEP **{cep}**, o prazo estimado é **3–7 dias úteis** (simulado). Se quiser, calculo o frete detalhado."
            SESSION.append_turn(state, role="user", text=message, intent="frete_prazo")
            SESSION.append_turn(state, role="bot",  text=reply,   intent="frete_prazo")
            SESSION.save(state)
            return ChatResponse(reply=reply, intent="frete_prazo", confidence=1.0, gap_top2=1.0,
                                need_cep=False, events=state.slots.get("fallback_events", []))
        else:
            state.slots["need_cep"] = True
            reply = "O prazo/valor do frete depende do seu **CEP**. Me passa o CEP que eu calculo rapidinho?"
            SESSION.append_turn(state, role="user", text=message, intent="frete_prazo")
            SESSION.append_turn(state, role="bot",  text=reply,   intent="frete_prazo")
            SESSION.save(state)
            return ChatResponse(reply=reply, intent="frete_prazo", confidence=0.95, gap_top2=0.95,
                                need_cep=True, events=state.slots.get("fallback_events", []))

    # Preferências sem consulta de produto → só acusar recebimento
    if is_pref_only(message):
        bits = []
        if size:  bits.append(f"tamanho **{size}**")
        if color: bits.append(f"cor **{color}**")
        if brand: bits.append(f"marca **{brand}**")
        reply = "Anotei que você curte " + " e ".join(bits) + ". Quer que eu busque peças nessa linha?"
        SESSION.append_turn(state, role="user", text=message, intent="preferencias")
        SESSION.append_turn(state, role="bot",  text=reply,   intent="preferencias")
        SESSION.save(state)
        return ChatResponse(reply=reply, intent="preferencias", confidence=1.0, gap_top2=1.0,
                            need_cep=False, events=state.slots.get("fallback_events", []))

    # Slot CEP pendente (ciclo aberto)
    if state.slots.get("need_cep"):
        if cep:
            state.slots["need_cep"] = False
            _reset_clarify_if_resolved(state)
            reply = f"CEP {cep} anotado! Prazo estimado: 3–7 dias úteis (simulado)."
            SESSION.log_event(state, kind="cep_collected", reason="slot_filled", payload={"cep": cep})
        else:
            reply = "Me envia o CEP no formato 89010-000 ou 89010000, por favor."
            SESSION.log_event(state, kind="cep_missing", reason="awaiting_input", payload={})
        SESSION.append_turn(state, role="user", text=message, intent="frete_prazo")
        SESSION.append_turn(state, role="bot",  text=reply,  intent="frete_prazo")
        SESSION.save(state)
        return ChatResponse(reply=reply, intent="frete_prazo", confidence=1.0 if cep else 0.9, gap_top2=1.0,
                            need_cep=state.slots.get("need_cep", False),
                            events=state.slots.get("fallback_events", []))

    # --- classificação + coerção ------------------------------------------------
    pred = _normalize_pred(classify_intent(message))
    pred = coerce_intent(message, pred, MIN_CONF, MIN_GAP)
    intent, conf, gap, top3 = pred["intent"], pred["conf"], pred["gap"], pred["top3"]

    # Promoção de buscas de produto: força pedido_sugestao e evita clarificação
    if looks_like_product_query(message):
        if intent not in {"pedido_sugestao", "tamanho_modelagem"}:
            intent = "pedido_sugestao"
            pred["intent"] = intent
        pred["conf"] = conf = max(float(conf or 0.0), MIN_CONF + 0.05)
        pred["gap"]  = gap  = max(float(gap  or 0.0), MIN_GAP  + 0.05)

    # Log de debug do classificador
    SESSION.log_event(
        state, kind="pred_debug", reason="post_classify",
        payload={"intent": intent, "conf": conf, "gap": gap, "top3": top3, "text": message[:200]}
    )

    # ===== Ambiguidade: pular clarificação se for busca de produto =============
    res = AMB.from_prediction(message, pred)
    if res.ambiguous and not looks_like_product_query(message):
        _amb_update_state(state, res)
        top1, top2 = _friendly_top12(pred)

        if int(state.slots.get("clarify_count", 0)) > AMB_MAX_CLARIFY:
            reply = clarify("atendimento", top1=top1, top2=top2, strategy="round_robin", state=state.slots)
            events = state.slots.setdefault("fallback_events", [])
            events.append(FALLBACK.build_event(
                reason="ambiguity_escalate", intent=intent, confidence=conf, gap=gap,
                extra={"kind":"clarify_escalate","clarify_key":"atendimento",
                       "clarify_count": int(state.slots.get("clarify_count",0)),
                       "clarify_last_ts": int(state.slots.get("clarify_last_ts", 0))}
            ))
            state.slots["fallback_events"] = events[-20:]
            SESSION.append_turn(state, role="user", text=message, intent="clarify_user", confidence=conf, gap_top2=gap)
            SESSION.append_turn(state, role="bot",  text=reply,   intent="clarify_atendimento")
            SESSION.save(state)
            return ChatResponse(reply=reply, intent="clarify", confidence=conf, gap_top2=gap,
                                need_cep=state.slots.get("need_cep", False),
                                events=state.slots.get("fallback_events", []))

        key = _clarify_key_for(res)
        reply = clarify(key, top1=top1, top2=top2, strategy="round_robin", state=state.slots)
        events = state.slots.setdefault("fallback_events", [])
        events.append(FALLBACK.build_event(
            reason=res.reason, intent=intent, confidence=conf, gap=gap,
            extra={"kind":"clarify","clarify_key": key,
                   "clarify_count": int(state.slots.get("clarify_count",0)),
                   "clarify_last_ts": int(state.slots.get("clarify_last_ts", 0))}
        ))
        state.slots["fallback_events"] = events[-20:]
        SESSION.append_turn(state, role="user", text=message, intent="clarify_user", confidence=conf, gap_top2=gap)
        SESSION.append_turn(state, role="bot",  text=reply,   intent="clarify")
        SESSION.save(state)
        return ChatResponse(reply=reply, intent="clarify", confidence=conf, gap_top2=gap,
                            need_cep=state.slots.get("need_cep", False),
                            events=state.slots.get("fallback_events", []))

    # ===== Não ambígua: seguir fluxo normal / fallbacks =========================
    _reset_clarify_if_resolved(state)

    if conf < MIN_CONF or gap < MIN_GAP or FALLBACK.need_low_confidence(confidence=conf, gap_top2=gap):
        reply = FALLBACK.build_reply_low_confidence(top3, state=state.slots)
        events = state.slots.setdefault("fallback_events", [])
        events.append(FALLBACK.build_event(
            reason="low_confidence", intent=intent, confidence=conf, gap=gap,
            extra={"kind":"fallback_low_conf","used_thresholds": FALLBACK.get_thresholds()}
        ))
        state.slots["fallback_events"] = events[-20:]
    else:
        if intent == "frete_prazo" and not cep and not state.slots.get("cep") and has_shipping_terms(message):
            state.slots["need_cep"] = True
            reply = "O prazo/valor do frete depende do seu **CEP**. Me passa o CEP que eu calculo rapidinho?"
        else:
            profile_rt = _runtime_profile(state)
            reply = generate_response(intent, message, meta={"profile_json": profile_rt})

    # Persistência e resposta
    SESSION.append_turn(state, role="user", text=message, intent=intent, confidence=conf, gap_top2=gap)
    SESSION.append_turn(state, role="bot",  text=reply,   intent=intent)
    SESSION.save(state)
    return ChatResponse(reply=reply, intent=intent, confidence=conf, gap_top2=gap,
                        need_cep=state.slots.get("need_cep", False),
                        events=state.slots.get("fallback_events", []))

# ==================== STREAMING =================================================
async def stream_text_chunks(text: str, delay_ms: int = 18) -> AsyncGenerator[str, None]:
    chunks, buf = [], ""
    for tok in text.split(" "):
        if len(buf) + len(tok) + 1 > 18:
            chunks.append(buf)
            buf = tok
        else:
            buf = f"{buf} {tok}".strip()
    if buf:
        chunks.append(buf)
    for ch in chunks:
        yield ch
        await asyncio.sleep(delay_ms / 1000)

@app.get("/api/stream")
async def stream(
    message: Optional[str] = Query(None),
    prompt: Optional[str] = Query(None),
    session_id: str = Query("web-session"),
    user_id: Optional[str] = Query(None),
):
    # Compat: aceitar ?message=... ou ?prompt=...
    raw_msg = message if (message is not None and message != "") else prompt
    if not (raw_msg and str(raw_msg).strip()):
        raise HTTPException(status_code=422, detail="Query must include 'message' or 'prompt'.")

    req = ChatRequest(message=str(raw_msg).strip(), session_id=session_id, user_id=user_id)
    resp: ChatResponse = chat(req)

    async def event_generator():
        async for ch in stream_text_chunks(resp.reply):
            yield {"event": "token", "data": ch}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())
