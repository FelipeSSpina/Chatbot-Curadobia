# -*- coding: utf-8 -*-
"""Chat CLI da BIA com cache, clarifica��o de ambiguidades, guard-rails e slot de CEP."""
from __future__ import annotations
import os, sys, time
from code.context.session import SessionManager
from code.fallbacks.manager import FallbackManager
from code.ambiguity.detector import AmbiguityDetector
from code.ambiguity.clarify import clarify
try:
    from .guards import coerce_intent, extract_cep
except Exception:
    from code.fluxos_intencao.guards import coerce_intent, extract_cep  # fallback

try:  # stdout UTF-8 no Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from .chatbot import classify_intent, generate_response
except Exception:
    from chatbot import classify_intent, generate_response  # type: ignore

MIN_CONF, MIN_GAP = 0.55, 0.25

def _normalize_pred(pred: dict) -> dict:
    pred = dict(pred or {}); intent = pred.get("intent") or "nao_entendi"; probs = pred.get("probs") or {}
    conf = pred.get("conf")
    try: conf = float(conf)
    except: conf = None
    if conf is None or conf == 0.0:
        try: conf = float(probs.get(intent, 0.0))
        except: conf = 0.0
    try:
        items = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        p1 = float(items[0][1]) if items else float(conf or 0.0)
        p2 = float(items[1][1]) if len(items) > 1 else 0.0
        gap = max(0.0, p1 - p2); top3 = items[:3]
    except: gap, top3 = 0.0, []
    pred.update(intent=intent, conf=float(conf or 0.0), gap=float(gap), top3=top3)
    pred.setdefault("probs", probs); return pred

def _record_fallback(state, sm: SessionManager, *, user_text: str, intent: str, conf: float, gap: float, reason: str):
    sm.append_turn(state, role="user", text=user_text, intent=intent, confidence=conf, gap_top2=gap)
    ev = state.slots.setdefault("fallback_events", [])
    ev.append({"reason": reason, "intent": intent, "confidence": conf, "gap": gap})
    state.slots["fallback_events"] = ev[-20:]

def main() -> None:
    print("=== BIA | Curadobia � CLI ===")
    print("Digite sua mensagem (ou 'sair').")
    sm = SessionManager(ttl_seconds=3600)
    state = sm.load(os.getenv("BIA_SESSION_ID", "cli-session"))
    fb   = FallbackManager()
    amb  = AmbiguityDetector(confidence_threshold=MIN_CONF, gap_threshold=MIN_GAP)
    pending_cep = False

    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando. At� mais!"); break
        if user.lower() in {"sair","exit","quit"}:
            print("At� mais!"); break

        if pending_cep:
            cep = extract_cep(user)
            if cep:
                reply = f"CEP {cep} anotado! Prazo estimado: 3�7 dias �teis (simulado)."
                print(reply)
                pending_cep = False
                sm.append_turn(state, role="user", text=user, intent="frete_prazo")
                sm.append_turn(state, role="bot",  text=reply, intent="frete_prazo")
                sm.save(state)
            else:
                print("Me manda o CEP no formato 89010-000 ??")
            continue

        pred = _normalize_pred(classify_intent(user))
        pred = coerce_intent(user, pred, MIN_CONF, MIN_GAP)
        intent, conf, gap, top3 = pred["intent"], pred["conf"], pred["gap"], pred["top3"]

        if amb.from_scores(conf, gap, user, intents=top3).ambiguous:
            reply = clarify(intent)
            _record_fallback(state, sm, user_text=user, intent=intent, conf=conf, gap=gap, reason="ambiguity")
            sm.append_turn(state, role="bot", text=reply, intent="clarificacao"); sm.save(state)
            print(reply); continue

        if conf < MIN_CONF or gap < MIN_GAP or fb.need_low_confidence(confidence=conf, gap_top2=gap):
            reply = fb.build_reply_low_confidence(top3)
            _record_fallback(state, sm, user_text=user, intent=intent, conf=conf, gap=gap, reason="low_confidence")
            sm.append_turn(state, role="bot", text=reply, intent="fallback_baixa_confianca"); sm.save(state)
            print(reply); continue

        if intent == "frete_prazo" and not extract_cep(user):
            print("O prazo/valor do frete depende do seu CEP. Me passa o CEP que eu calculo rapidinho?")
            pending_cep = True
            continue

        started = time.perf_counter()
        reply = generate_response(intent, user)
        sm.append_turn(state, role="user", text=user, intent=intent, confidence=conf, gap_top2=gap)
        sm.append_turn(state, role="bot",  text=reply, intent=intent); sm.save(state)
        print(f"[{intent} | conf={conf:.3f} gap={gap:.3f} | {time.perf_counter()-started:.2f}s] {reply}")

if __name__ == "__main__":
    main()

