# file: code/fluxos_intencao/guards.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Optional

# Vocabulário de produto (singular/plural/acentos)
PRODUCT_WORDS = {
    "vestido","blazer","calça","calca","saia","jaqueta","camisa","camiseta",
    "top","short","shorts","jeans","bolsa","sapato","bermuda","cardigan",
    "suéter","sueter","mule","bota","sandália","sandalia","tenis","tênis",
    "moletom","trench","trench coat","polo","chemise","puffer","oversized","oversize",
    "plissado","plissada","baguete","jaqueta sarja","jaqueta couro","jaqueta jeans",
    "regata","body"
}

# Tamanhos comuns (alfanuméricos)
SIZE_WORDS = {"pp","p","m","g","gg","xg","xs","s","l","xl","xxl","34","36","38","40","42","44","46","48"}

# Cores frequentes em PT-BR (inclui variantes compostas)
COLOR_WORDS = {
    "preto","preta","branco","branca","off white","off-white","offwhite",
    "azul","azul marinho","vermelho","verde","verde musgo","bege","marrom","caramelo","cinza",
    "rosa","roxo","lilás","lilas","laranja","amarelo","bordô","bordo",
    "vinho","creme","nude","mostarda","musgo","marinho"
}

# CEP (aceita -, espaços e traços unicode)
CEP_RE   = re.compile(r"\b(\d{5}[-\s–—]?\d{3})\b")
SIZE_RE  = re.compile(r"\b(pp|p|m|g|gg|xg|xs|s|l|xl|xxl|3[2468]|[3-5]\d)\b", re.I)
COLOR_RE = re.compile(
    r"\b(preto|preta|branco|branca|off[- ]?white|offwhite|azul(?:\s+marinho)?|vermelho|verde(?:\s+musgo)?|bege|marrom|caramelo|cinza|rosa|roxo|lil[aá]s|laranja|amarelo|bord[ôo]|vinho|creme|nude|mostarda|musgo|marinho)\b",
    re.I,
)

# ---------------- MARCA (mais restrito e seguro) ----------------
# 1) "marca X" / "marca: X" / "brand X" / "brand: X"
BRAND_AFTER_WORD_RE = re.compile(
    r"\b(?:marca|brand)\s*[:\-]?\s*([A-Za-z][\w\-]{2,20}(?:\s+[A-Za-z][\w\-]{2,20}){0,2})\b", re.I
)
# 2) "da/de marca X"
BRAND_DA_DE_MARCA_RE = re.compile(
    r"\b(?:da|de)\s+(?:marca|brand)\s+([A-Za-z][\w\-]{2,20}(?:\s+[A-Za-z][\w\-]{2,20}){0,2})\b", re.I
)
# 3) "da/de X" (sem 'marca'), no máx. 2 tokens – com filtros depois
BRAND_DA_DE_RE = re.compile(
    r"\b(?:da|de)\s+([A-Z][\w\-]{2,20})(?:\s+([A-Z][\w\-]{2,20}))?\b"
)

# Palavras que NÃO podem ser marca
BRAND_STOPWORDS = {
    "entrega","prazo","frete","cep","capital","pagamento","juros",
    "parcelamento","sem","rio","janeiro","interior","demora","chega","funciona"
}
# Siglas/locais comuns que dão falsos-positivos
BRAND_BAD_SIGLAS = {"SP","RJ","MG","BH","BR"}

FRETE_WORDS = ("frete","entrega","prazo","cep")

def has_shipping_terms(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in FRETE_WORDS)

def looks_like_product_query(text: str) -> bool:
    """
    Parece busca de produto (para coerções): contém palavra de produto
    ou tamanho/cor explícitos.
    """
    t = (text or "").lower().strip()
    if not t:
        return False
    if any(w in t for w in PRODUCT_WORDS):
        return True
    if SIZE_RE.search(t):
        return True
    if COLOR_RE.search(t):
        return True
    return False

def extract_cep(text: str) -> Optional[str]:
    m = CEP_RE.search(text or "")
    if not m:
        return None
    cep = m.group(1)
    cep = re.sub(r"[^\d]", "", cep)
    return cep if len(cep) == 8 else None

def extract_size(text: str) -> Optional[str]:
    m = SIZE_RE.search(text or "")
    if not m:
        return None
    return m.group(1).upper()

def extract_color(text: str) -> Optional[str]:
    m = COLOR_RE.search(text or "")
    if not m:
        return None
    c = m.group(1).lower().strip()
    c = c.replace("off white","off-white")
    if c in ("offwhite","off white","off-white"): return "off-white"
    if c in ("lilas","lilás"): return "lilás"
    if c in ("bordo","bordô"): return "bordô"
    if c in ("preta","preto"): return "preto"
    if c in ("branca","branco"): return "branco"
    return c

def extract_brand(text: str) -> Optional[str]:
    """
    Heurística mais segura:
    - "marca X" / "marca: X" / "brand X"
    - "da/de marca X"
    - "da/de X" (no máx. 2 tokens, só se parecer nome de marca; filtra siglas/verbos/stopwords)
    Também remove prefixo "marca " se o candidato vier como "marca Farm".
    """
    t = (text or "").strip()
    if not t:
        return None

    cand: Optional[str] = None

    m = BRAND_AFTER_WORD_RE.search(t)
    if m:
        cand = m.group(1).strip(" -'").strip()
    else:
        m = BRAND_DA_DE_MARCA_RE.search(t)
        if m:
            cand = m.group(1).strip(" -'").strip()
        else:
            m = BRAND_DA_DE_RE.search(t)
            if m:
                # junta 1-2 tokens
                tok1 = m.group(1) or ""
                tok2 = m.group(2) or ""
                tokens = [tok1] + ([tok2] if tok2 else [])
                # filtros: nada de siglas problemáticas; segundo token não pode ser verbo/stopword
                if tokens[0].upper() in BRAND_BAD_SIGLAS:
                    return None
                if len(tokens) == 2 and tokens[1].lower() in BRAND_STOPWORDS:
                    return None
                cand = " ".join(tokens).strip()

    if not cand:
        return None

    low = cand.lower()
    # remove prefixo "marca " se escapou
    if low.startswith("marca "):
        cand = cand.split(" ", 1)[1].strip()
        low = cand.lower()
    # filtra stopwords/termos de produto
    if any(tok in BRAND_STOPWORDS for tok in low.split()):
        return None
    if low in PRODUCT_WORDS:
        return None
    # mínimo 2 caracteres úteis
    return cand[:40] if len(cand) >= 2 else None

def is_pref_only(text: str) -> bool:
    """
    True quando o usuário só declara preferências (tamanho/cor/marca),
    sem citar peça/categoria e sem verbos de ação.
    """
    t = (text or "").strip().lower()
    if not t:
        return False
    has_size  = bool(SIZE_RE.search(t))
    has_color = bool(COLOR_RE.search(t))
    has_brand = bool(extract_brand(t))  # usa extrator restrito
    mentions_item = any(w in t for w in PRODUCT_WORDS)
    verbs_seek = re.search(
        r"\b(buscar|procuro|quero|preciso|sugest[aã]o|indica|indicar|vestir|usar|procurando|busco)\b",
        t, re.I
    )
    return (has_size or has_color or has_brand) and (not mentions_item) and not verbs_seek

def coerce_intent(text: str, pred: dict, min_conf: float = 0.55, min_gap: float = 0.25) -> dict:
    """
    Coerções:
    - CEP encontrado → 'frete_prazo'
    - Saudação + pista de produto → 'pedido_sugestao'
    - Texto parece busca de produto mas modelo não está em {canônicos} → 'pedido_sugestao'
    """
    t = (text or "")

    # 1) CEP explícito
    cep = extract_cep(t)
    if cep and pred.get("intent") != "frete_prazo":
        coerced = dict(pred)
        coerced["intent"] = "frete_prazo"
        coerced["conf"] = max(float(pred.get("conf") or 0.0), max(min_conf, 0.9))
        coerced["gap"]  = max(float(pred.get("gap")  or 0.0), max(min_gap, 0.5))
        coerced["forced_by"] = "cep_guard"
        return coerced

    # 2) Saudação + pista de produto
    if (pred.get("intent") == "saudacao") and looks_like_product_query(t):
        coerced = dict(pred)
        coerced["intent"] = "pedido_sugestao"
        coerced["conf"] = min(float(pred.get("conf") or 0.0), min_conf - 1e-3)
        coerced["gap"]  = min(float(pred.get("gap")  or 0.0), min_gap  - 1e-3)
        coerced["forced_by"] = "product_guard"
        return coerced

    # 3) Genérico: parece busca de produto mas modelo não está em {canônicos}
    if looks_like_product_query(t) and pred.get("intent") not in {"pedido_sugestao","tamanho_modelagem","frete_prazo","formas_pagamento"}:
        coerced = dict(pred)
        coerced["intent"] = "pedido_sugestao"
        coerced["conf"] = min(float(pred.get("conf") or 0.0), min_conf - 1e-3)
        coerced["gap"]  = min(float(pred.get("gap")  or 0.0), min_gap  - 1e-3)
        coerced["forced_by"] = "product_guard_generic"
        return coerced

    return pred
