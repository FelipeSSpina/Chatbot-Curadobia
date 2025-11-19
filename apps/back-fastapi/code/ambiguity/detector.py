# file: code/ambiguity/detector.py
# -*- coding: utf-8 -*-
"""
Detector de ambiguidade para o pipeline BIA.

Critérios configuráveis:
- Baixa confiança (conf < MIN_CONF)
- Gap pequeno entre top-1 e top-2 (gap < MIN_GAP)
- Frases de baixo sinal (LOW_SIGNAL): substrings e/ou regex

Combinação:
- Modo "any" (padrão): se QUALQUER critério aciona, é ambígua (retrocompatível).
- Modo "score": combina (s_conf, s_gap, s_low) com pesos e compara com min_score.

Configuração:
- Pode vir de code.config.ambiguity (se existir) e/ou variáveis de ambiente:
  AMB_MIN_CONF, AMB_MIN_GAP, AMB_WEIGHTS='{"conf":1,"gap":1,"low":1}',
  AMB_MODE=('any'|'score'), AMB_MIN_SCORE='1.0', AMB_REASON_POLICY
    ('dominant' | 'first' | 'combined_only')

API:
    det = AmbiguityDetector()
    res = det.from_scores(conf, gap, text, intents=top3)
    if res.ambiguous:
        # chamar clarify() e registrar motivo em res.reason
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union
import json
import logging
import os
import re

Pattern = re.Pattern

# ------------------------------------------------------------------------------
# Tentativa de carregar defaults centralizados (opcional)
# ------------------------------------------------------------------------------
try:
    # Se quiser centralizar, crie: code/config/ambiguity.py
    # com MIN_CONF, MIN_GAP, LOW_SIGNAL, WEIGHTS, MODE, MIN_SCORE
    from code.config import ambiguity as _cfg  # type: ignore
    _CFG_MIN_CONF = getattr(_cfg, "MIN_CONF", 0.50)
    _CFG_MIN_GAP = getattr(_cfg, "MIN_GAP", 0.20)
    _CFG_LOW_SIGNAL = getattr(_cfg, "LOW_SIGNAL", None)
    _CFG_WEIGHTS = getattr(_cfg, "WEIGHTS", None)   # {"conf":1,"gap":1,"low":1}
    _CFG_MODE = getattr(_cfg, "MODE", "any")        # "any" | "score"
    _CFG_MIN_SCORE = getattr(_cfg, "MIN_SCORE", 1.0)
except Exception:
    _CFG_MIN_CONF = 0.50
    _CFG_MIN_GAP = 0.20
    _CFG_LOW_SIGNAL = None
    _CFG_WEIGHTS = None
    _CFG_MODE = "any"
    _CFG_MIN_SCORE = 1.0

# ------------------------------------------------------------------------------
# Defaults de segurança (usados se não houver config/env)
# ------------------------------------------------------------------------------
DEFAULT_MIN_CONF: float = float(_CFG_MIN_CONF)
DEFAULT_MIN_GAP: float = float(_CFG_MIN_GAP)
DEFAULT_WEIGHTS: Dict[str, float] = dict(_CFG_WEIGHTS or {"conf": 1.0, "gap": 1.0, "low": 1.0})
DEFAULT_MODE: str = str(_CFG_MODE or "any")  # "any" | "score"
DEFAULT_MIN_SCORE: float = float(_CFG_MIN_SCORE)

# Conjunto padrão de frases de baixo sinal (substrings).
DEFAULT_LOW_SIGNAL_SUBSTRINGS: List[str] = list(_CFG_LOW_SIGNAL or [
    "preciso de ajuda", "me ajuda", "me ajude", "não sei", "nao sei",
    "tô em dúvida", "to em duvida", "não tenho certeza", "nao tenho certeza",
    "não sei ainda", "nao sei ainda", "me orienta", "pode me orientar",
    "me dá uma força", "me de uma força", "tô perdido", "to perdido",
    "pode ajudar", "me ajuda por favor", "ajuda por favor",
])

# Regex padrão (conservadoras) — ativas por padrão
DEFAULT_LOW_SIGNAL_REGEX: List[Pattern] = [
    re.compile(r"^\s*$"),                               # só espaço/vazio
    re.compile(r"^\s*[\?\!\.\,\-\:\;\(\)\[\]\{\}\/\\]{1,}\s*$"),  # só pontuação
    re.compile(r"^\s*\?{2,}\s*$"),                      # só "???"
    re.compile(r"^\s*ajuda\s*$", flags=re.IGNORECASE),  # "ajuda" isolado
    re.compile(r"[🤔🤷‍♀️🤷‍♂️]"),                        # emojis de dúvida/“shrug”
]


# ------------------------------------------------------------------------------
# Utils
# ------------------------------------------------------------------------------
def _clamp01(x: float) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return 0.0


def _parse_env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except Exception:
        return default


def _parse_env_json(name: str, default: Mapping[str, float]) -> Mapping[str, float]:
    val = os.getenv(name)
    if not val:
        return default
    try:
        obj = json.loads(val)
        if isinstance(obj, dict):
            return obj
        return default
    except Exception:
        return default


# ------------------------------------------------------------------------------
# Result
# ------------------------------------------------------------------------------
@dataclass(slots=True)
class AmbiguityResult:
    ambiguous: bool
    reason: str                   # "low_signal_phrase" | "low_confidence" | "small_gap_top2" | "combined_score" | "confident"
    details: Dict                # conf, gap, intents, thresholds, weights, mode, min_score, reason_policy
    metrics: Dict                # s_conf, s_gap, s_low, score
    triggered_rules: List[str]   # lista com as regras que dispararam (para telemetria)

    def to_dict(self) -> Dict:
        return asdict(self)


# ------------------------------------------------------------------------------
# Detector
# ------------------------------------------------------------------------------
class AmbiguityDetector:
    """Detector de ambiguidade por (conf, gap) + frases de baixo sinal (substr/regex)."""

    def __init__(
        self,
        *,
        confidence_threshold: Optional[float] = None,
        gap_threshold: Optional[float] = None,
        low_signal_phrases: Optional[Iterable[Union[str, Pattern]]] = None,
        low_signal_regex: Optional[Iterable[Pattern]] = None,
        weights: Optional[Mapping[str, float]] = None,
        mode: Optional[str] = None,         # "any" (default, retrocompatível) | "score"
        min_score: Optional[float] = None,  # usado quando mode="score"
        use_env: bool = True,
        logger: Optional[logging.Logger] = None,
        reason_policy: Optional[str] = None,  # "dominant" | "first" | "combined_only"
    ) -> None:
        self.log = logger or logging.getLogger(__name__)

        # thresholds (env -> arg -> default)
        conf_thr = confidence_threshold if confidence_threshold is not None else DEFAULT_MIN_CONF
        gap_thr = gap_threshold if gap_threshold is not None else DEFAULT_MIN_GAP
        if use_env:
            conf_thr = _parse_env_float("AMB_MIN_CONF", conf_thr)
            gap_thr = _parse_env_float("AMB_MIN_GAP", gap_thr)
        self.conf_thr = _clamp01(conf_thr)
        self.gap_thr = _clamp01(gap_thr)

        # weights (env -> arg -> default)
        w = dict(DEFAULT_WEIGHTS)
        if use_env:
            w_env = _parse_env_json("AMB_WEIGHTS", w)
            w.update({k: float(v) for k, v in w_env.items() if k in ("conf", "gap", "low")})
        if weights:
            w.update({k: float(v) for k, v in weights.items() if k in ("conf", "gap", "low")})
        self.weights: Dict[str, float] = {"conf": float(w["conf"]), "gap": float(w["gap"]), "low": float(w["low"])}

        # modo + min_score
        m = (mode or DEFAULT_MODE).lower()
        if use_env:
            m = (os.getenv("AMB_MODE", m) or m).lower()
        self.mode: str = "score" if m == "score" else "any"

        ms = DEFAULT_MIN_SCORE if min_score is None else float(min_score)
        if use_env:
            ms = _parse_env_float("AMB_MIN_SCORE", ms)
        self.min_score: float = float(ms)

        # razão (política) no modo score
        rp = (reason_policy or os.getenv("AMB_REASON_POLICY", "dominant")).lower()
        self.reason_policy: str = "dominant" if rp not in ("first", "combined_only") else rp

        # low_signal: substrings e regex
        self.low_signal_substrings: List[str] = []
        self.low_signal_patterns: List[Pattern] = []

        # origem: defaults + args
        substr = list(DEFAULT_LOW_SIGNAL_SUBSTRINGS)
        regs = list(DEFAULT_LOW_SIGNAL_REGEX)

        if low_signal_phrases:
            for p in low_signal_phrases:
                if isinstance(p, re.Pattern):
                    regs.append(p)
                elif isinstance(p, str):
                    s = p.strip()
                    if s.startswith("/") and s.endswith("/") and len(s) > 2:
                        # convenção: "/regex/" vira regex
                        try:
                            regs.append(re.compile(s[1:-1], flags=re.IGNORECASE))
                        except Exception:
                            self.log.debug("Ignorando regex inválida em low_signal_phrases: %r", s)
                    else:
                        substr.append(s)
        if low_signal_regex:
            for rgx in low_signal_regex:
                if isinstance(rgx, re.Pattern):
                    regs.append(rgx)

        # normalização
        self.low_signal_substrings = [s.lower() for s in substr if s]
        self.low_signal_patterns = regs

    # ---------------------------- utils internas -----------------------------
    @staticmethod
    def _f(x) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _is_low_signal(self, text: str) -> bool:
        t = (text or "")
        tl = t.lower()
        # substrings
        for s in self.low_signal_substrings:
            if s in tl:
                return True
        # regex
        for rgx in self.low_signal_patterns:
            try:
                if rgx.search(t):
                    return True
            except Exception:
                continue
        return False

    # ------------------------------- API principal ---------------------------
    def _scores(self, conf: float, gap: float, low_sig: bool) -> Dict[str, float]:
        """
        Constrói scores normalizados relativos aos thresholds.
        s_conf > 0 só quando conf < conf_thr; idem s_gap quando gap < gap_thr.
        s_low é 1.0 quando low_signal acionou, senão 0.0.
        """
        s_conf = 0.0
        if self.conf_thr > 0:
            deficit = max(0.0, self.conf_thr - conf)
            s_conf = deficit / self.conf_thr

        s_gap = 0.0
        if self.gap_thr > 0:
            deficit = max(0.0, self.gap_thr - gap)
            s_gap = deficit / self.gap_thr

        s_low = 1.0 if low_sig else 0.0
        return {"s_conf": s_conf, "s_gap": s_gap, "s_low": s_low}

    def from_scores(
        self,
        conf: float,
        gap: float,
        text: str,
        intents: Optional[Sequence[Tuple[str, float]]] = None,
    ) -> AmbiguityResult:
        """
        Decide se a mensagem é ambígua usando (conf, gap) e frases de baixo sinal.

        Args:
            conf: confiança do top-1 (0..1)
            gap:  p1 - p2 (0..1)
            text: mensagem original do usuário
            intents: sequência [(label, prob)] opcional, para logging/telemetria
        """
        c = _clamp01(self._f(conf))
        g = _clamp01(self._f(gap))
        intents = intents or []

        low_sig = self._is_low_signal(text)
        metrics = self._scores(c, g, low_sig)

        # regras que dispararam individualmente
        triggered: List[str] = []
        if low_sig: triggered.append("low_signal_phrase")
        if c < self.conf_thr: triggered.append("low_confidence")
        if g < self.gap_thr: triggered.append("small_gap_top2")

        # score combinado
        w = self.weights
        score = (w["conf"] * metrics["s_conf"]
                 + w["gap"] * metrics["s_gap"]
                 + w["low"] * metrics["s_low"])
        metrics["score"] = float(score)

        # decisão
        if self.mode == "score":
            if score >= float(self.min_score):
                ambiguous = True
                reason = "combined_score"
            elif triggered:
                ambiguous = True
                if self.reason_policy == "dominant":
                    trio = [("low_signal_phrase", metrics["s_low"]),
                            ("small_gap_top2",    metrics["s_gap"]),
                            ("low_confidence",    metrics["s_conf"])]
                    reason = max(trio, key=lambda t: t[1])[0]
                elif self.reason_policy == "first":
                    reason = triggered[0]
                else:  # "combined_only" -> se não bateu min_score, considera não ambígua
                    ambiguous = False
                    reason = "confident"
            else:
                ambiguous = False
                reason = "confident"
        else:  # "any" (retrocompatível)
            ambiguous = bool(triggered)
            reason = triggered[0] if triggered else "confident"

        details = {
            "conf": c,
            "gap": g,
            "intents": intents,
            "thresholds": {"min_conf": self.conf_thr, "min_gap": self.gap_thr},
            "weights": dict(self.weights),
            "mode": self.mode,
            "min_score": self.min_score,
            "reason_policy": self.reason_policy,
        }
        return AmbiguityResult(
            ambiguous=ambiguous,
            reason=reason,
            details=details,
            metrics=metrics,
            triggered_rules=triggered,
        )

    # Conveniência: quando só temos o texto e a predição normalizada
    def from_prediction(self, text: str, pred: Mapping) -> AmbiguityResult:
        """
        pred esperado (tolerante):
          {"conf": float, "gap": float, "top3": [(label, prob), ...]}
        Aceita também "gap_top2" ou calcula gap de probs se necessário.
        """
        conf = self._f(pred.get("conf"))
        gap = pred.get("gap")
        if gap is None:
            gap = pred.get("gap_top2")
        if gap is None:
            # tenta derivar (p1 - p2) de probs
            probs = pred.get("probs")
            if isinstance(probs, Mapping) and probs:
                try:
                    vals = sorted([float(v) for v in probs.values()], reverse=True)
                    gap = vals[0] - vals[1] if len(vals) >= 2 else 1.0
                except Exception:
                    gap = 0.0
            else:
                gap = 0.0

        intents = pred.get("top3") or pred.get("topk") or []
        return self.from_scores(conf=conf, gap=self._f(gap), text=text, intents=intents)

    # ------------------------------ Atualizações ------------------------------
    def update_thresholds(self, *, min_conf: Optional[float] = None, min_gap: Optional[float] = None) -> None:
        """Atualiza thresholds com clamp 0–1 e loga alterações."""
        old_conf, old_gap = self.conf_thr, self.gap_thr
        if min_conf is not None:
            self.conf_thr = _clamp01(min_conf)
        if min_gap is not None:
            self.gap_thr = _clamp01(min_gap)
        if (self.conf_thr != old_conf) or (self.gap_thr != old_gap):
            self.log.info("Ambiguity thresholds updated: min_conf %.3f→%.3f, min_gap %.3f→%.3f",
                          old_conf, self.conf_thr, old_gap, self.gap_thr)

    def update_weights(self, *, w_conf: Optional[float] = None, w_gap: Optional[float] = None, w_low: Optional[float] = None) -> None:
        """Atualiza pesos (não são clampados a 0–1; aceitam >1)."""
        old = dict(self.weights)
        if w_conf is not None:
            self.weights["conf"] = float(w_conf)
        if w_gap is not None:
            self.weights["gap"] = float(w_gap)
        if w_low is not None:
            self.weights["low"] = float(w_low)
        if self.weights != old:
            self.log.info("Ambiguity weights updated: %s → %s", old, self.weights)

    def replace_low_signal(self, phrases: Iterable[Union[str, Pattern]]) -> None:
        """Substitui completamente a lista de low-signal (strings e/ou regex)."""
        substr: List[str] = []
        regs: List[Pattern] = []
        for p in phrases:
            if isinstance(p, re.Pattern):
                regs.append(p)
            elif isinstance(p, str):
                s = p.strip()
                if s.startswith("/") and s.endswith("/") and len(s) > 2:
                    try:
                        regs.append(re.compile(s[1:-1], flags=re.IGNORECASE))
                    except Exception:
                        self.log.debug("Ignorando regex inválida em replace_low_signal: %r", s)
                else:
                    substr.append(s)
        self.low_signal_substrings = [s.lower() for s in substr if s]
        self.low_signal_patterns = regs
        self.log.info("Ambiguity low-signal list replaced (substr=%d, regex=%d)",
                      len(self.low_signal_substrings), len(self.low_signal_patterns))

    def add_low_signal_phrases(self, phrases: Iterable[str]) -> None:
        """Adiciona substrings ao low-signal (normaliza para lower)."""
        added = 0
        for p in phrases:
            if not p:
                continue
            s = p.lower().strip()
            if s and s not in self.low_signal_substrings:
                self.low_signal_substrings.append(s)
                added += 1
        if added:
            self.log.info("Added %d low-signal substrings.", added)

    def add_low_signal_regex(self, patterns: Iterable[Pattern]) -> None:
        """Adiciona padrões regex ao low-signal."""
        added = 0
        for rgx in patterns:
            if isinstance(rgx, re.Pattern):
                self.low_signal_patterns.append(rgx)
                added += 1
        if added:
            self.log.info("Added %d low-signal regex patterns.", added)


# ------------------------------------------------------------------------------
# Modo “teste rápido”: python -m code.ambiguity.detector
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    det_any = AmbiguityDetector(mode="any")
    det_score = AmbiguityDetector(mode="score", min_score=1.0, weights={"conf": 1.0, "gap": 1.0, "low": 1.0})

    samples = [
        (0.92, 0.05, "quero algo legal", [("pedido_sugestao", 0.52), ("frete_prazo", 0.47)]),
        (0.41, 0.30, "não sei ainda", [("pedido_sugestao", 0.41), ("formas_pagamento", 0.34)]),
        (0.88, 0.31, "preciso de ajuda", [("saudacao", 0.36), ("pedido_sugestao", 0.34)]),
        (0.80, 0.50, "quero jaqueta jeans M", [("pedido_sugestao", 0.80), ("tamanho_modelagem", 0.20)]),
    ]

    print("=== MODE=any ===")
    for conf, gap, text, top3 in samples:
        r = det_any.from_scores(conf, gap, text, intents=top3)
        print(text, "=>", r.to_dict())

    print("\n=== MODE=score ===")
    for conf, gap, text, top3 in samples:
        r = det_score.from_scores(conf, gap, text, intents=top3)
        print(text, "=>", r.to_dict())
