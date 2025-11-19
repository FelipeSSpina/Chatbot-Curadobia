# file: code/fluxos_intencao/chat_web.py
# -*- coding: utf-8 -*-
"""Gradio da BIA com cache (SQLite), rehidratação de histórico e memória de sessão (tamanho, cor, marca, CEP)."""
from __future__ import annotations
import os, sys, time, re
import gradio as gr

from code.context.session import SessionManager
from code.fallbacks.manager import FallbackManager
from code.ambiguity.detector import AmbiguityDetector
from code.ambiguity.clarify import clarify

# --- imports relativos com fallback -------------------------------------------
try:
    from .guards import (
        coerce_intent, extract_cep, extract_size, extract_color, extract_brand,
        looks_like_product_query, has_shipping_terms, is_pref_only
    )
except Exception:
    from code.fluxos_intencao.guards import coerce_intent, extract_cep, extract_size, extract_color, extract_brand, looks_like_product_query, has_shipping_terms, is_pref_only  # type: ignore

try:
    from .chatbot import classify_intent, generate_response, rank_catalog  # rank_catalog só para LOG
except Exception:
    from chatbot import classify_intent, generate_response  # type: ignore
    rank_catalog = None  # type: ignore

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# -------------------- config/instâncias ---------------------------------------
MIN_CONF, MIN_GAP = 0.50, 0.20
SESSION = SessionManager(ttl_seconds=3600)
FALLBACK = FallbackManager()
AMB = AmbiguityDetector(confidence_threshold=MIN_CONF, gap_threshold=MIN_GAP, mode=os.getenv("AMB_MODE","any"))
AMB_MAX_CLARIFY = int(os.getenv("AMB_MAX_CLARIFY", "2"))

SID = os.environ.get("BIA_SID", "web-session")  # "mesma sessão" por enquanto

# -------------------- labels amigáveis p/ clarificação -------------------------
INTENT_HUMAN = {
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

def _friendly_top12(pred: dict) -> tuple[str, str]:
    labels = [lbl for (lbl, _p) in (pred.get("top3") or [])]
    if pred.get("intent") and pred["intent"] not in labels:
        labels.insert(0, pred["intent"])
    dedup = []
    for l in labels:
        if l and l not in dedup:
            dedup.append(l)
    dedup += ["", ""]
    t1, t2 = dedup[0], dedup[1]
    return INTENT_HUMAN.get(t1, t1), INTENT_HUMAN.get(t2, t2)

# -------------------- utils ----------------------------------------------------
def _normalize_pred(pred: dict) -> dict:
    pred = dict(pred or {})
    intent = pred.get("intent") or "nao_entendi"
    probs = pred.get("probs") or {}
    conf = pred.get("conf")
    try: conf = float(conf)
    except Exception: conf = None
    if conf is None or conf == 0.0:
        try: conf = float(probs.get(intent, 0.0))
        except Exception: conf = 0.0
    try:
        items = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        p1 = float(items[0][1]) if items else float(conf or 0.0)
        p2 = float(items[1][1]) if len(items) > 1 else 0.0
        gap = max(0.0, p1 - p2); top3 = items[:3]
    except Exception:
        gap, top3 = 0.0, []
    pred.update(intent=intent, conf=float(conf or 0.0), gap=float(gap), top3=top3)
    pred.setdefault("probs", probs)
    return pred

def _pairs_from_history(hist: list[dict]) -> list[tuple[str, str]]:
    """Converte turns do SQLite para lista [(user, bot)] para o componente Chatbot."""
    pairs: list[tuple[str, str]] = []
    user_buf: str | None = None
    for t in hist:
        role = (t.get("role") or "").lower()
        txt = str(t.get("text") or "")
        if role == "user":
            if user_buf is not None:
                pairs.append((user_buf, ""))
            user_buf = txt
        elif role == "bot":
            if user_buf is None:
                pairs.append(("", txt))
            else:
                pairs.append((user_buf, txt))
                user_buf = None
        else:
            continue
    if user_buf is not None:
        pairs.append((user_buf, ""))
    return pairs

def _runtime_profile(state) -> dict:
    """Perfil em tempo real = perfil persistido + prefs da sessão + slots."""
    p = SESSION.get_profile(state) or {}
    for k in ("tamanho_sup", "tamanho_inf", "cor", "marca", "cep"):
        v = SESSION.get_pref(state.session_id, k, None)
        if v:
            p[k] = v
    if state.slots.get("cep") and not p.get("cep"):
        p["cep"] = state.slots["cep"]
    return p

def _safe_generate(intent: str, message: str, **kw) -> str:
    """Encapsula generate_response para aceitar meta/profile_json com compatibilidade."""
    try:
        import inspect as _inspect
    except Exception:
        _inspect = None

    _g = globals().get("generate_response")
    if _g is None:
        try:
            from code.fallbacks.manager import FallbackManager as _FM
            return _FM().build_reply_low_confidence([(intent or "nao_entendi", 0.66)])
        except Exception:
            return f"[fallback] (intent={intent})"

    meta = kw.get("meta") or {}
    try:
        if _inspect is not None:
            sig = _inspect.signature(_g)
            params = sig.parameters
            args = {}
            if "meta" in params: args["meta"] = meta
            if "profile_json" in params and "profile_json" not in args:
                args["profile_json"] = meta.get("profile_json", {})
            return str(_g(intent, message, **args))
        return str(_g(intent, message))
    except TypeError:
        try:
            from code.fallbacks.manager import FallbackManager as _FM
            return _FM().build_reply_low_confidence([(intent or "nao_entendi", 0.66)])
        except Exception:
            return f"[fallback] (intent={intent})"

# --------- helpers de ambiguidade (mesma lógica do app.py) --------------------
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
        if s_low >= max(s_conf, s_gap): return "ambigua_low_signal"
        if s_gap >= s_conf: return "ambigua_gap_top2"
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
    if state.slots.get("clarify_count"):
        state.slots["clarify_count"] = 0

# -------------------- núcleo da conversa ---------------------------------------
def respond_core(message: str) -> tuple[str, str, float, float]:
    """
    Retorna (reply, intent, conf, gap) e persiste tudo no SQLite.
    Memória de sessão: tamanho/cor/marca/CEP.
    """
    sid = SID
    state = SESSION.load(sid)
    tmsg = (message or "").strip()

    # --------- Interceptadores diretos antes de extrair prefs -----------------
    # Humano / atendimento
    if re.search(r"\b(falar|conversar|chamar|preciso|quero)\b.*\b(humano|pessoa|atendente|atendimento|suporte)\b", tmsg, re.I) \
       or re.search(r"\b(humano|atendente|atendimento|suporte)\b", tmsg, re.I):
        msg = "Posso chamar alguém do time para te atender. Quer que eu encaminhe agora?"
        SESSION.append_turn(state, role="user", text=tmsg, intent="atendimento_humano")
        SESSION.append_turn(state, role="bot",  text=msg,  intent="atendimento_humano")
        SESSION.save(state)
        return msg, "atendimento_humano", 1.0, 1.0

    # Troca / devolução
    if re.search(r"\b(devolu[cç][aã]o|troca|devolver|trocar)\b", tmsg, re.I):
        msg = ("Claro! Para **trocas e devoluções** (compras online), você tem até **7 dias corridos** após o recebimento, "
               "conforme o CDC. Me passa o **nº do pedido** e o motivo que eu abro a solicitação pra você.")
        SESSION.append_turn(state, role="user", text=tmsg, intent="troca_devolucao")
        SESSION.append_turn(state, role="bot",  text=msg,  intent="troca_devolucao")
        SESSION.save(state)
        return msg, "troca_devolucao", 1.0, 1.0

    # Ajuda genérica
    if re.search(r"\b(ajuda|ajudar|help|socorro)\b", tmsg, re.I):
        msg = "Posso ajudar com: **sugestões de roupas**, **frete/prazo**, **pagamento** ou **trocas/devoluções**. Qual desses?"
        SESSION.append_turn(state, role="user", text=tmsg, intent="ajuda")
        SESSION.append_turn(state, role="bot",  text=msg,  intent="ajuda")
        SESSION.save(state)
        return msg, "ajuda", 1.0, 1.0

    # --------- Extrações de preferências/slots --------------------------------
    size = extract_size(tmsg)
    color = extract_color(tmsg)
    brand = extract_brand(tmsg)
    if size:  SESSION.remember_pref(sid, "tamanho_sup", size, ttl_sec=None)
    if color: SESSION.remember_pref(sid, "cor",         color, ttl_sec=None)
    if brand: SESSION.remember_pref(sid, "marca",       brand, ttl_sec=None)

    cep = extract_cep(tmsg)
    if cep:
        state.slots["cep"] = cep
        SESSION.remember_pref(sid, "cep", cep, ttl_sec=None)

    # --------- Atalho de frete antes do classificador -------------------------
    if has_shipping_terms(tmsg):
        if cep:
            msg = f"Com base no seu CEP **{cep}**, o prazo estimado é **3–7 dias úteis** (simulado). Se quiser, calculo o frete detalhado."
            SESSION.append_turn(state, role="user", text=tmsg, intent="frete_prazo")
            SESSION.append_turn(state, role="bot",  text=msg,  intent="frete_prazo")
            SESSION.save(state)
            return msg, "frete_prazo", 1.0, 1.0
        else:
            state.slots["need_cep"] = True
            msg = "O prazo/valor do frete depende do seu **CEP**. Me passa o CEP que eu calculo rapidinho?"
            SESSION.append_turn(state, role="user", text=tmsg, intent="frete_prazo")
            SESSION.append_turn(state, role="bot",  text=msg,  intent="frete_prazo")
            SESSION.save(state)
            return msg, "frete_prazo", 0.95, 0.95

    # --------- Preferências puras ---------------------------------------------
    if is_pref_only(tmsg):
        bits = []
        if size:  bits.append(f"tamanho **{size}**")
        if color: bits.append(f"cor **{color}**")
        if brand: bits.append(f"marca **{brand}**")
        reply = "Anotei que você curte " + " e ".join(bits) + ". Quer que eu busque peças nessa linha?"
        SESSION.append_turn(state, role="user", text=tmsg, intent="preferencias")
        SESSION.append_turn(state, role="bot",  text=reply, intent="preferencias")
        SESSION.save(state)
        return reply, "preferencias", 1.0, 1.0

    # --------- Slot CEP pendente ----------------------------------------------
    if state.slots.get("need_cep"):
        if cep:
            state.slots["need_cep"] = False
            _reset_clarify_if_resolved(state)
            reply = f"CEP {cep} anotado! Prazo estimado: 3–7 dias úteis (simulado)."
            SESSION.log_event(state, kind="cep_collected", reason="slot_filled", payload={"cep": cep})
        else:
            reply = "Me envia o CEP no formato 89010-000 ou 89010000, por favor."
            SESSION.log_event(state, kind="cep_missing", reason="awaiting_input", payload={})
        SESSION.append_turn(state, role="user", text=tmsg, intent="frete_prazo")
        SESSION.append_turn(state, role="bot",  text=reply, intent="frete_prazo")
        SESSION.save(state)
        return reply, "frete_prazo", 1.0 if cep else 0.9, 1.0 if cep else 0.9

    # --------- Classificação + coerção ----------------------------------------
    pred = _normalize_pred(classify_intent(tmsg))
    pred = coerce_intent(tmsg, pred, MIN_CONF, MIN_GAP)
    intent, conf, gap, top3 = pred["intent"], pred["conf"], pred["gap"], pred["top3"]

    # Promoção de buscas de produto: força pedido_sugestao e evita clarificação
    if looks_like_product_query(tmsg):
        if intent not in {"pedido_sugestao", "tamanho_modelagem"}:
            intent = "pedido_sugestao"
            pred["intent"] = intent
        pred["conf"] = conf = max(float(conf or 0.0), MIN_CONF + 0.05)
        pred["gap"]  = gap  = max(float(gap  or 0.0), MIN_GAP  + 0.05)

    # --------- Ambiguidade (detector completo) --------------------------------
    res = AMB.from_prediction(tmsg, pred)
    if res.ambiguous and not looks_like_product_query(tmsg):
        _amb_update_state(state, res)

        top1, top2 = _friendly_top12(pred)

        if int(state.slots.get("clarify_count", 0)) > AMB_MAX_CLARIFY:
            msg = clarify("atendimento", top1=top1, top2=top2, strategy="round_robin", state=state.slots)
            events = state.slots.setdefault("fallback_events", [])
            events.append(FALLBACK.build_event(
                reason="ambiguity_escalate", intent=intent, confidence=conf, gap=gap,
                extra={"kind":"clarify_escalate", "clarify_key":"atendimento",
                       "clarify_count": int(state.slots.get("clarify_count",0)),
                       "clarify_last_ts": int(state.slots.get("clarify_last_ts", 0)) }
            ))
            state.slots["fallback_events"] = events[-20:]
            SESSION.append_turn(state, role="user", text=tmsg, intent="clarify_user", confidence=conf, gap_top2=gap)
            SESSION.append_turn(state, role="bot",  text=msg,  intent="clarify_atendimento")
            SESSION.save(state)
            return msg, "clarify", conf, gap

        key = _clarify_key_for(res)
        msg = clarify(key, top1=top1, top2=top2, strategy="round_robin", state=state.slots)
        events = state.slots.setdefault("fallback_events", [])
        events.append(FALLBACK.build_event(
            reason=res.reason, intent=intent, confidence=conf, gap=gap,
            extra={"kind":"clarify", "clarify_key": key,
                   "clarify_count": int(state.slots.get("clarify_count",0)),
                   "clarify_last_ts": int(state.slots.get("clarify_last_ts", 0)) }
        ))
        state.slots["fallback_events"] = events[-20:]
        SESSION.append_turn(state, role="user", text=tmsg, intent="clarify_user", confidence=conf, gap_top2=gap)
        SESSION.append_turn(state, role="bot",  text=msg,  intent="clarify")
        SESSION.save(state)
        return msg, "clarify", conf, gap

    # --------- Não ambígua: seguir fluxo normal / fallbacks -------------------
    _reset_clarify_if_resolved(state)

    if conf < MIN_CONF or gap < MIN_GAP or FALLBACK.need_low_confidence(confidence=conf, gap_top2=gap):
        reply = FALLBACK.build_reply_low_confidence(top3, state=state.slots)
        SESSION.log_event(state, kind="low_confidence", reason="below_thresholds",
                          payload={"intent": intent, "conf": conf, "gap": gap, "top3": top3, "thresholds": FALLBACK.get_thresholds()})
    else:
        # CEP necessário?
        if intent == "frete_prazo" and not cep and not state.slots.get("cep") and has_shipping_terms(tmsg):
            state.slots["need_cep"] = True
            reply = "O prazo/valor do frete depende do seu **CEP**. Me passa o CEP que eu calculo rapidinho?"
            SESSION.log_event(state, kind="cep_required", reason="missing_slot", payload={})
        else:
            profile_rt = _runtime_profile(state)
            reply = _safe_generate(intent, tmsg, meta={"profile_json": profile_rt})

            # LOG opcional de fallback do catálogo
            if intent in {"tamanho_modelagem", "pedido_sugestao"} and rank_catalog is not None:
                try:
                    recs = rank_catalog(tmsg, k=5, profile_json=profile_rt)
                    if FALLBACK.need_product_fallback(recs.to_dict("records"), min_score=0.35):
                        similares = []
                        for _, r in recs.head(5).iterrows():
                            name = f"{r.get('brand','')} {r.get('name','')}".strip()
                            cat = r.get("category", "")
                            if name: similares.append(f"{name} — {cat}".strip(" —"))
                        SESSION.log_event(
                            state, kind="fallback_no_products", reason="rank_empty_or_low",
                            payload={"q": tmsg, "similares": similares[:5], "avg_score": float(recs["score_total"].mean()) if not recs.empty else 0.0},
                        )
                except Exception:
                    pass

    # --------- Persistência de turnos -----------------------------------------
    SESSION.append_turn(state, role="user", text=tmsg, intent=intent, confidence=conf, gap_top2=gap)
    SESSION.append_turn(state, role="bot",  text=reply, intent=intent)
    SESSION.save(state)
    return reply, intent, conf, gap

# -------------------- UI (Blocks) com rehidratação ------------------------------
with gr.Blocks(theme=gr.themes.Soft(primary_hue="indigo"), title="BIA — Curadobia") as demo:
    gr.Markdown("### BIA — Curadobia\nHistórico e preferências lembradas **na mesma sessão**.")

    chatbot = gr.Chatbot(height=540, type="tuples", show_copy_button=True)
    txt = gr.Textbox(placeholder="Descreva o que você procura (ex.: 'vestido midi azul M') ou faça uma pergunta...", autofocus=True)
    send_btn = gr.Button("Enviar", variant="primary")
    clear_btn = gr.Button("Limpar conversa (sessão atual)")

    # 1) Rehidratar do SQLite ao abrir
    def _load_history():
        state = SESSION.load(SID)
        return _pairs_from_history(state.history)

    demo.load(fn=_load_history, inputs=None, outputs=[chatbot])

    # 2) Enviar mensagem
    def _on_send(user_msg: str, chat: list[tuple[str, str]]):
        if not (user_msg or "").strip():
            return gr.update(), chat
        reply, intent, conf, gap = respond_core(user_msg)
        chat = (chat or []) + [(user_msg, reply)]
        return "", chat

    send_btn.click(_on_send, inputs=[txt, chatbot], outputs=[txt, chatbot])
    txt.submit(_on_send, inputs=[txt, chatbot], outputs=[txt, chatbot])

    # 3) Limpar sessão atual (útil para testes)
    def _on_clear():
        SESSION.clear(SID)
        return []

    clear_btn.click(_on_clear, inputs=None, outputs=[chatbot])

if __name__ == "__main__":
    host = os.environ.get("BIA_HOST", "127.0.0.1")
    port = int(os.environ.get("BIA_PORT", "7860"))
    print(f"[WEB] Gradio em http://{host}:{port}")
    demo.launch(server_name=host, server_port=port, inbrowser=False, show_api=False)
