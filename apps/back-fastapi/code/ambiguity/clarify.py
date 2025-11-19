# file: code/ambiguity/clarify.py
# -*- coding: utf-8 -*-
"""
Sugestões de perguntas de esclarecimento no tom BIA.

- Dicionário com chaves explícitas (ex.: "atendimento", "nao_entendi",
  "ambigua_gap_top2", "ambigua_low_signal", "multi_intencao", etc.)
- Pelo menos 2 variações por chave para evitar repetição.
- Suporte a variáveis {top1}, {top2} (e extras via extra_vars).
- API compatível com a antiga (clarify(intent, order=0)).
- Estratégias opcionais: "random" (seed) ou "round_robin" (state) para escolha.
"""

from __future__ import annotations
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence
import random


class SafeFormatDict(dict):
    """Evita KeyError ao formatar templates; mantém {chave} se não fornecida."""
    def __missing__(self, key):
        return "{" + key + "}"


# ====== TEMPLATES ==============================================================
# Mantemos as chaves que você já usava e adicionamos novas.
TEMPLATES: Dict[str, List[str]] = {
    # Casos existentes
    "tamanho_modelagem": [
        "Você costuma vestir qual tamanho nessa parte do corpo? Posso ajustar a grade certinho.",
        "Quer me passar busto/cintura/quadril pra eu sugerir o melhor caimento?",
    ],
    "pedido_sugestao_produto": [
        "Qual ocasião você tem em mente? Trabalho, jantar ou algo mais descontraído?",
        "Prefere que eu puxe algo mais minimalista, vibrante ou outro estilo?",
    ],
    "frete_prazo": [
        "Me passa o CEP pra eu calcular rapidinho?",
        "Se puder mandar o CEP, eu já te trago prazo e opções de frete.",
    ],
    "formas_pagamento": [
        "Você está pensando em Pix, cartão ou quer saber sobre parcelamento?",
        "Posso detalhar as formas de pagamento: prefere à vista, Pix ou cartão parcelado?",
    ],

    # Aliases úteis
    "pedido_sugestao": [
        "Qual ocasião você tem em mente? Trabalho, jantar ou algo mais descontraído?",
        "Prefere que eu puxe algo mais minimalista, vibrante ou outro estilo?",
    ],
    "prazo_entrega": [
        "Me passa o CEP pra eu calcular rapidinho?",
        "Se puder mandar o CEP, eu já te trago prazo e opções de frete.",
    ],
    "preco_pagamento": [
        "Você está pensando em Pix, cartão ou quer saber sobre parcelamento?",
        "Posso detalhar as formas de pagamento: prefere à vista, Pix ou cartão parcelado?",
    ],

    # Ambiguidade/clarificação (novos casos)
    "nao_entendi": [
        "Não captei bem. Você quis dizer {top1} ou {top2}?",
        "Fiquei na dúvida — seu assunto é {top1} ou {top2}?"
    ],
    "atendimento": [
        "Posso te passar para o time humano. Antes, confirma: é sobre {top1} ou {top2}?",
        "Se preferir, chamo alguém do time. Só me diga: {top1} ou {top2}?"
    ],
    "ambigua_gap_top2": [
        "Fiquei entre {top1} e {top2}. Qual desses descreve melhor seu pedido?",
        "Estou em dúvida entre {top1} e {top2}. Qual você prefere que eu siga?"
    ],
    "ambigua_low_signal": [
        "Consegue detalhar um pouco? Por exemplo: {top1} ou {top2}?",
        "Preciso de mais contexto — é mais {top1} ou {top2}?"
    ],
    "multi_intencao": [
        "Percebi mais de um assunto. Vamos por partes: começamos por {top1} ou {top2}?",
        "Tem duas coisas aqui. Qual priorizamos agora: {top1} ou {top2}?"
    ],

    # Fallback genérico
    "ambigua_generica": [
        "Você pode especificar melhor? Ex.: {top1} ou {top2}.",
        "Me dá uma pista: é mais {top1} ou {top2}?"
    ],
}

# Mantemos "default" como alias do genérico para compatibilidade com código antigo
TEMPLATES["default"] = TEMPLATES["ambigua_generica"]


def _pick_index(n: int, key: str,
                strategy: Optional[str],
                seed: Optional[int],
                state: Optional[MutableMapping]) -> int:
    """Escolhe o índice conforme a estratégia.

    Regras:
    - n<=1 -> 0
    - strategy="round_robin" com state mutável -> rotaciona e salva no state
    - strategy="round_robin" sem state -> usa aleatório (evita sempre 0)
    - strategy="random" -> aleatório (seed opcional)
    - strategy=None -> índice 0 (será guiado por 'order' fora daqui)
    """
    if n <= 1:
        return 0
    if not strategy:
        return 0
    if strategy == "round_robin":
        if state is not None:
            slot = f"clarify_rr::{key}"
            last = int((state or {}).get(slot, -1))
            idx = (last + 1) % n
            state[slot] = idx
            return idx
        rng = random.Random(seed)
        return rng.randrange(n)
    if strategy == "random":
        rng = random.Random(seed)
        return rng.randrange(n)
    return 0


def clarify(
    intent: Optional[str],
    *,
    order: Optional[int] = 0,
    top1: Optional[str] = None,
    top2: Optional[str] = None,
    strategy: Optional[str] = None,            # None | "random" | "round_robin"
    seed: Optional[int] = None,                # usado com "random" (ou fallback rr sem state)
    state: Optional[MutableMapping] = None,    # usado com "round_robin"
    extra_vars: Optional[Mapping[str, str]] = None,
) -> str:
    """
    Gera uma mensagem de clarificação.

    Compatibilidade: se você só passar (intent, order=...), o comportamento
    é idêntico ao arquivo antigo (pega a variação pelo índice 'order').

    Para rotação/aleatoriedade:
      - strategy="round_robin", informar 'state' (dict de sessão). Sem state → aleatório.
      - strategy="random", informar 'seed' (opcional).

    As variáveis {top1}/{top2} são substituídas se forem fornecidas.
    """
    key = intent or ""
    options = TEMPLATES.get(key, TEMPLATES["default"])

    # 1) Se estratégia foi definida, ela prevalece sobre 'order'
    if strategy:
        idx = _pick_index(len(options), key, strategy, seed, state)
    else:
        # 2) Comportamento antigo (order baseado em índice, clamp no range)
        idx = min(max(int(order or 0), 0), len(options) - 1)

    text = options[idx]

    vars_dict = SafeFormatDict(top1=top1 or "", top2=top2 or "")
    if extra_vars:
        vars_dict.update(extra_vars)

    try:
        return text.format_map(vars_dict)
    except Exception:
        # Em caso de erro de formatação, retorna texto cru
        return text


def available_keys() -> Iterable[str]:
    """Lista chaves disponíveis (útil para validação/telemetria)."""
    return TEMPLATES.keys()


def scripted_loop(intent: Optional[str]) -> Sequence[str]:
    """
    Retorna a sequência de variações (sem formatação) para um intent,
    preservando compatibilidade com chamadas anteriores.
    """
    options = TEMPLATES.get(intent or "", TEMPLATES["default"])
    return list(options)


__all__ = ["clarify", "available_keys", "scripted_loop"]
