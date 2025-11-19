# file: code/fallbacks/manager.py
# -*- coding: utf-8 -*-
"""Gerencia decisões de fallback para o chatbot Curadobia."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple
import os, random, time

def _env_float(name: str, default: float) -> float:
    try:
        v = os.getenv(name)
        return float(v) if v is not None else default
    except Exception:
        return default

# Thresholds ALINHADOS ao gating global (override por ENV)
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "min_conf": _env_float("FALLBACK_MIN_CONF", _env_float("AMB_MIN_CONF", 0.50)),
    "min_gap":  _env_float("FALLBACK_MIN_GAP",  _env_float("AMB_MIN_GAP",  0.20)),
}

# Mensagens com variações para evitar repetição
_LOW_CONF_MSGS_TWO = [
    "Fiquei em dúvida sobre o tema. Posso seguir por {opts}?",
    "Não tenho certeza do que você quis dizer. Quer falar de {opts}?",
]
_LOW_CONF_MSGS_ONE = [
    "Você quis dizer {only}?",
    "É sobre {only}?",
]
_LOW_CONF_MSGS_GENERIC = [
    "Não captei bem. Pode reformular por favor?",
    "Não tenho certeza do assunto. Pode explicar um pouquinho melhor?",
]

_NO_PRODUCTS_MSGS = [
    "Não encontrei itens ideais agora{ctx}. Posso sugerir categorias parecidas{cats}?",
    "Ainda não achei uma boa combinação{ctx}. Quer ver opções próximas{cats}?",
]

def _pick_index(n: int, key: str, state: Optional[MutableMapping], strategy: str = "round_robin", seed: Optional[int] = None) -> int:
    if n <= 1: return 0
    if strategy == "round_robin" and state is not None:
        slot = f"fallback_rr::{key}"
        last = int((state or {}).get(slot, -1))
        idx = (last + 1) % n
        state[slot] = idx
        return idx
    rng = random.Random(seed)
    return rng.randrange(n)

def _human_join(labels: List[str]) -> str:
    labels = [l for l in labels if l]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    # máximo 2 para manter a frase concisa
    return " ou ".join(labels[:2])

class FallbackManager:
    """Aplica heurísticas centralizadas e constrói respostas de fallback."""
    def __init__(self, thresholds: Optional[Mapping[str, float]] = None) -> None:
        self._th: Dict[str, float] = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self._th.update({k: float(v) for k, v in thresholds.items() if k in ("min_conf","min_gap")})

    # Expor thresholds atuais (telemetria)
    def get_thresholds(self) -> Dict[str, float]:
        return dict(self._th)

    # --- Heurísticas base -------------------------------------------------
    def need_low_confidence(self, *, confidence: float, gap_top2: float) -> bool:
        """True se a predição deve ser tratada como baixa confiança."""
        try:
            return float(confidence) < self._th["min_conf"] or float(gap_top2) < self._th["min_gap"]
        except Exception:
            return True

    def need_product_fallback(
        self,
        scored_candidates: Sequence[Mapping[str, Any]] | None,
        *,
        min_score: float = 0.35,
        min_count: int = 1,
    ) -> bool:
        """Aciona fallback quando não há itens (ou poucos) acima do score mínimo."""
        if not scored_candidates:
            return True
        good = [it for it in scored_candidates if float(it.get("score_total") or it.get("score", 0.0)) >= float(min_score)]
        return len(good) < int(min_count)

    def need_api_retry(
        self,
        status_code: int | None,
        *,
        retriable: Iterable[int] = (408, 429, 500, 502, 503, 504),
    ) -> bool:
        """Indica se a requisição falhou de modo que vale reexecutar ou oferecer humano."""
        return status_code in set(retriable)

    # --- Mensagens de apoio -----------------------------------------------
    def build_reply_no_products(
        self,
        query: Optional[str] = None,
        alternatives: Optional[List[str]] = None,
        *,
        items_meta: Optional[Sequence[Mapping[str, Any]]] = None,
        profile: Optional[Mapping[str, Any]] = None,
        state: Optional[MutableMapping] = None,
        seed: Optional[int] = None,
    ) -> str:
        """
        Sugere opções quando nada foi encontrado ou a similaridade ficou baixa.
        Aceita metadados (ex.: {"name","category","price"}) e alterna a redação.
        """
        # contexto curto baseado no perfil
        pbits = []
        if profile:
            if profile.get("tamanho_sup"): pbits.append(f"tam {profile['tamanho_sup']}")
            if profile.get("tamanho_inf"): pbits.append(f"tam {profile['tamanho_inf']}")
            if profile.get("cor"):         pbits.append(f"cor {profile['cor']}")
            if profile.get("marca"):       pbits.append(f"marca {profile['marca']}")
        ctx = f" (baseado no seu perfil: {', '.join(pbits)})" if pbits else ""

        # categorias próximas (se disponíveis)
        cats = ""
        if items_meta:
            cats_all = [str(it.get("category","")).strip() for it in items_meta if it.get("category")]
            uniq = []
            for c in cats_all:
                if c and c not in uniq:
                    uniq.append(c)
                if len(uniq) >= 3: break
            cats = f" como {', '.join(uniq)}" if uniq else ""

        # cabeça (frase exigida pelo barema)
        head = f'Não tenho exatamente isso para “{query or ""}”, mas veja estas opções similares...'.strip()

        # variação + bullets (se houver)
        body_tpl = _NO_PRODUCTS_MSGS[_pick_index(len(_NO_PRODUCTS_MSGS), "no_products", state, seed=seed)]
        msg = head + "\n" + body_tpl.format(ctx=ctx, cats=cats)

        if alternatives:
            bullets = "\n".join(f"- {alt}" for alt in alternatives[:5])
            msg += f"\n{bullets}"

        msg += "\n\nSe quiser, eu já refino por tamanho, modelo ou preço."
        return msg

    def build_reply_low_confidence(
        self,
        top_intents: Sequence[Tuple[str, float]] | None,
        *,
        state: Optional[MutableMapping] = None,
        seed: Optional[int] = None,
    ) -> str:
        # Extrai apenas labels válidos
        labels = [lab for lab, _ in (top_intents or []) if lab]
        if len(labels) >= 2:
            opts = _human_join(labels[:2])
            tpl = _LOW_CONF_MSGS_TWO[_pick_index(len(_LOW_CONF_MSGS_TWO), "low_conf_two", state, seed=seed)]
            return tpl.format(opts=opts)
        if len(labels) == 1:
            only = labels[0]
            tpl = _LOW_CONF_MSGS_ONE[_pick_index(len(_LOW_CONF_MSGS_ONE), "low_conf_one", state, seed=seed)]
            return tpl.format(only=only)
        # Sem nenhuma opção — genérico seguro (evita “ou ?”)
        return _LOW_CONF_MSGS_GENERIC[_pick_index(len(_LOW_CONF_MSGS_GENERIC), "low_conf_gen", state, seed=seed)]

    def build_reply_api_issue(self) -> str:
        return (
            "Uuups, meu acesso aos estoques deu uma travadinha. "
            "Posso tentar de novo em instantes ou chamar alguém do time para te ajudar."
        )

    def build_reply_timeout(self) -> str:
        return (
            "Demorou mais que o normal para eu consultar tudo. "
            "Quer que eu continue buscando aqui ou prefere que eu peça para o time te chamar?"
        )

    # --- Logging utilitário ------------------------------------------------
    def record_event(self, *, session: Any = None, state: Any = None, kind: str, reason: str, payload: Mapping[str, Any] | None = None) -> None:
        """Integra com SessionManager.log_event quando disponível."""
        if session is not None and state is not None:
            try:
                session.log_event(state, kind=kind, reason=reason, payload=dict(payload or {}))
            except Exception:
                pass

    def build_event(self, *, reason: str, intent: str, confidence: float, gap: float,
                    extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Evento padronizado para `state.slots['fallback_events']`."""
        ev = {
            "ts": int(time.time()),
            "reason": reason,
            "intent": intent,
            "confidence": float(confidence),
            "gap": float(gap),
            "thresholds": self.get_thresholds(),
        }
        if extra:
            ev.update(dict(extra))
        return ev

__all__ = ["FallbackManager", "DEFAULT_THRESHOLDS"]
