# -*- coding: utf-8 -*-
# file: code/fallbacks/messages.py
"""Mensagens modelo no tom BIA para cen�rios de fallback."""
from __future__ import annotations

from typing import Dict, Iterable


def render_message(key: str, **slots: str) -> str:
    template = MESSAGES.get(key, MESSAGES["generic"])
    return template.format(**slots)


MESSAGES: Dict[str, str] = {
    "generic": "T� quase l�! Me conta s� mais um detalhe pra eu acertar em cheio?",
    "ask_size": "Pra garantir o caimento perfeito, qual tamanho ou medida voc� prefere usar nessa pe�a?",
    "ask_category": "T� buscando algo pra qual ocasi�o? Posso separar vestido, cal�a ou look completo.",
    "ask_budget": "Tem alguma faixa de pre�o ideal? Assim eu j� filtro o que combina com voc�.",
    "handoff_offer": "Se quiser, pe�o pro time humano te ligar rapidinho e resolver tudo ao vivo.",
    "no_catalog": "Ainda n�o achei essa pe�a. Quer que eu ca�e algo parecido em cor, tecido ou estilo?",
    "api_error": "Minha consulta travou um pouquinho. Posso tentar de novo ou mando pro time humano continuar?",
    "timeout": "Demorei mais que o normal aqui nos bastidores. Prefere que eu siga buscando ou te conecto com algu�m?",
    "low_confidence": "Fiquei entre duas possibilidades. Voc� quer falar de {top1} ou de {top2}?",
}


def known_keys() -> Iterable[str]:
    return MESSAGES.keys()


__all__ = ["render_message", "known_keys", "MESSAGES"]


