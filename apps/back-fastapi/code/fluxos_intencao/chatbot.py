# -*- coding: utf-8 -*-
"""
BIA • núcleo do bot: classificação + respostas + (opcional) ranking do catálogo.

Melhorias principais desta versão:
- Heurísticas melhores para detectar intenção de busca de produto (pedido_sugestao) e tamanho/modelagem.
- Parsing leve de orçamento (R$), cor e categoria a partir do texto do usuário — usados no ranking.
- Ranking mais completo com pesos configuráveis por ENV (similaridade, tamanho, estilo, preço, filtros).
- Fallback mais útil quando não encontra itens (usa FallbackManager com sugestões e categorias próximas).
- Telemetria ampliada (runtime_index_info inclui pesos, tamanho do índice e status do embedder).
- Logs moderados (sem verborragia) via logging padrão.
- Código mais tolerante a ambientes sem modelos/índice/embeddings (continua funcionando por regex).
"""

from __future__ import annotations
import os, json, re, logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from numpy.linalg import norm

# ------------------------------ Logging ---------------------------------------
log = logging.getLogger(__name__)
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    log.addHandler(h)
log.setLevel(os.getenv("BIA_LOG_LEVEL", "WARNING").upper())

# Dependências opcionais (tolerantes)
try:
    import joblib
except Exception:
    joblib = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # será checado antes de usar


# ------------------------------------------------------------------------------
# Descoberta de caminhos (robusta ao novo layout)
# ------------------------------------------------------------------------------
def _repo_root() -> Path:
    """
    Sobe diretórios até achar .git OU (apps e notebooks).
    Evita confundir subpastas que tenham README próprio.
    """
    p = Path(__file__).resolve()
    for q in [p, *p.parents]:
        if (q / ".git").exists() or ((q / "apps").exists() and (q / "notebooks").exists()):
            return q
    # fallback: .../apps/back-fastapi/code/fluxos_intencao/chatbot.py -> raiz ≈ parents[4]
    return p.parents[4]

REPO   = _repo_root()
NB     = REPO / "notebooks"
NB_OUT = NB / "outputs"
MODELS = NB_OUT / "models"

# Env overrides (opcionais)
ENV_EMB   = Path(os.getenv("BIA_EMBEDDER_DIR", "")).resolve() if os.getenv("BIA_EMBEDDER_DIR") else None
ENV_INT   = Path(os.getenv("BIA_INTENTS_DIR" , "")).resolve() if os.getenv("BIA_INTENTS_DIR")  else None
ENV_INDEX = Path(os.getenv("BIA_INDEX_DIR"   , "")).resolve() if os.getenv("BIA_INDEX_DIR")    else None
ENV_PROF  = Path(os.getenv("BIA_PROFILE_JSON", "")).resolve() if os.getenv("BIA_PROFILE_JSON") else None

def _pick_first_existing(cands: List[Optional[Path]]) -> Optional[Path]:
    for c in cands:
        if c and isinstance(c, Path) and c.exists():
            return c
    return None


# ------------------------------------------------------------------------------
# Artefatos: intents / índice / perfil  (todos opcionais)
# ------------------------------------------------------------------------------
INT_DIR = _pick_first_existing([
    ENV_INT,
    MODELS / "intents_calibrated",
    REPO   / "assets" / "models" / "intents_calibrated",
    REPO   / "models" / "intents_calibrated",  # legado
])

INDEX_DIR = _pick_first_existing([
    ENV_INDEX,
    MODELS / "fashion_embeddings" / "catalog_index",
    REPO   / "assets" / "models" / "fashion_embeddings" / "catalog_index",
    REPO   / "models" / "fashion_embeddings" / "catalog_index",  # legado
])

PROFILE_JSON = _pick_first_existing([
    ENV_PROF,
    REPO / "assets" / "profiles" / "cliente_exemplo.json",
    NB   / "data"   / "profiles" / "cliente_exemplo.json",   # compat
    REPO / "data"   / "profiles" / "cliente_exemplo.json",   # legado
])


# ------------------------------------------------------------------------------
# Config do ranking (pesos), ajustável por ENV
# ------------------------------------------------------------------------------
def _env_float(name: str, default: float) -> float:
    try:
        v = os.getenv(name)
        return float(v) if v is not None else default
    except Exception:
        return default

RANK_W_SIM    = _env_float("BIA_RANK_W_SIM",    0.60)
RANK_W_SIZE   = _env_float("BIA_RANK_W_SIZE",   0.15)
RANK_W_STYLE  = _env_float("BIA_RANK_W_STYLE",  0.10)
RANK_W_PRICE  = _env_float("BIA_RANK_W_PRICE",  0.10)
RANK_W_FILTER = _env_float("BIA_RANK_W_FILTER", 0.05)  # match de cor/marca/categoria
RANK_TOPK     = int(os.getenv("BIA_RANK_TOPK", "5"))
PRICE_TAU     = _env_float("BIA_PRICE_TAU", 200.0)     # suaviza a penalização por distância do orçamento

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# ------------------------------------------------------------------------------
# Carregar INTENTS (se existir). Se não existir, funciona só com regex/fallback.
# ------------------------------------------------------------------------------
clf = None
_labels: List[str] = []
if INT_DIR:
    clf_path  = INT_DIR / "clf.joblib"
    meta_path = INT_DIR / "meta.json"
    if clf_path.exists() and joblib is not None:
        try:
            clf = joblib.load(clf_path)
        except Exception as e:
            log.warning("Falha ao carregar classificador (%s): %s", clf_path, e)
            clf = None
    else:
        log.info("Classificador não encontrado em %s.", clf_path)

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            _labels = meta.get("meta", {}).get("labels") or meta.get("labels") or []
        except Exception as e:
            log.warning("Falha lendo meta.json (%s): %s", meta_path, e)

    if not _labels and clf is not None and hasattr(clf, "classes_"):
        _labels = list(map(str, clf.classes_))

if clf is None:
    log.info("Rodando sem classificador de intenções (usando regex + fallback).")


# ------------------------------------------------------------------------------
# Embedder (só instanciado se for realmente necessário)
# ------------------------------------------------------------------------------
EMBEDDER_NAME = os.getenv("BIA_EMBEDDER_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def _make_embedder() -> Optional[object]:
    """Cria o SentenceTransformer, se possível. Caso contrário, retorna None."""
    if SentenceTransformer is None:
        log.info("sentence-transformers não está instalado.")
        return None

    # Preferir diretório de FT se existir
    emb_dir_auto = MODELS / "fashion_embeddings"
    try:
        if ENV_EMB and ENV_EMB.exists():
            model = SentenceTransformer(str(ENV_EMB))
        elif emb_dir_auto.exists():
            model = SentenceTransformer(str(emb_dir_auto))
        else:
            model = SentenceTransformer(EMBEDDER_NAME)
        log.info("Embedder carregado: %s", getattr(model, 'name_or_path', 'custom'))
        return model
    except Exception as e:
        log.warning("Falha ao carregar embedder: %s", e)
        return None

_embedder: Optional[object] = None  # lazy


# ------------------------------------------------------------------------------
# Índice do catálogo (opcional)
# ------------------------------------------------------------------------------
index_items: pd.DataFrame = pd.DataFrame()
index_vecs_norm: Optional[np.ndarray] = None

if INDEX_DIR:
    items_csv     = INDEX_DIR / "items.csv"
    vecs_npy      = INDEX_DIR / "vectors.npy"
    vecs_norm_npy = INDEX_DIR / "vectors_norm.npy"  # opcional

    if items_csv.exists() and vecs_npy.exists():
        try:
            index_items = pd.read_csv(items_csv).fillna("")
            if vecs_norm_npy.exists():
                index_vecs_norm = np.load(vecs_norm_npy)
                src = "disk"
            else:
                raw = np.load(vecs_npy)
                norms = np.maximum(norm(raw, axis=1, keepdims=True), 1e-8)
                index_vecs_norm = (raw / norms).astype(np.float32)
                src = "memory"
            log.info("Índice ok: %s | itens=%d | normalizado=%s", INDEX_DIR, len(index_items), src)
        except Exception as e:
            index_items = pd.DataFrame()
            index_vecs_norm = None
            log.warning("Falha ao carregar índice (%s): %s", INDEX_DIR, e)
    else:
        log.info("Índice ausente em %s (items.csv/vectors.npy).", INDEX_DIR)
else:
    log.info("Rodando sem índice do catálogo.")


# ------------------------------------------------------------------------------
# Perfil (opcional) - se não houver, um perfil neutro é usado
# ------------------------------------------------------------------------------
if PROFILE_JSON and PROFILE_JSON.exists():
    try:
        profile = json.loads(PROFILE_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Falha lendo perfil (%s): %s", PROFILE_JSON, e)
        profile = {}
else:
    profile = {}

# Valores padrão para quando perfil estiver vazio
profile.setdefault("tamanho_superior", "M")
profile.setdefault("tamanho_inferior", "M")
profile.setdefault("tamanhos_equivalentes", ["M"])
profile.setdefault("estilos_preferidos", [])
profile.setdefault("cores_evitar", [])
profile.setdefault("tecidos_evitar", [])
profile.setdefault("cep", "")


# ------------------------------------------------------------------------------
# Regras rápidas (regex) + heurísticas de produto/categoria
# ------------------------------------------------------------------------------
REGEX_INTENTS: List[Tuple[str, re.Pattern]] = [
    ("saudacao",            re.compile(r"\b(oi|ol[aá]|bom dia|boa tarde|boa noite|e[ai]\b)\b", re.I)),
    ("como_comprar",        re.compile(r"\b(como (fa[cç]o|comprar|finalizar)|passo a passo|adicionar ao carrinho)\b", re.I)),
    ("frete_prazo",         re.compile(r"\b(prazo|entrega|frete|cep)\b", re.I)),
    ("formas_pagamento",    re.compile(r"\b(pix|cart[aã]o|boleto|pagamento|parcel(a|ar|amento)|sem\s+juros|aceitam?)\b", re.I)),
    ("agradecimento",       re.compile(r"\b(obrigad[oa]|valeu|agradecid[oa])\b", re.I)),
    ("ajuda",               re.compile(r"\b(ajuda|ajudar|help|socorro)\b", re.I)),
    ("atendimento_humano",  re.compile(r"\b(humano|atendente|atendimento|suporte)\b", re.I)),
    ("troca_devolucao",     re.compile(r"\b(devolu[cç][aã]o|troca|devolver|trocar)\b", re.I)),
    # Heurísticas para produto e tamanho/modelagem
    ("tamanho_modelagem",   re.compile(r"(veste|modelagem|fic(a|am)\s+(bom|boa|justo|apertado)|tamanho\s+(indicado|ideal))", re.I)),
    ("pedido_sugestao",     re.compile(r"(quero|procuro|tem|mostra|indica|sugest(ão|ao)|look|combina)\b.*", re.I)),
]

FASHION_CATS = [
    "vestido","blazer","calça","calca","camisa","camiseta","saia","short","bermuda","sapato","tênis","tenis",
    "bota","sandália","sandalia","moletom","casaco","jaqueta","bolsa","cinto","acessório","acessorio","meia"
]
COLORS = ["preto","branco","azul","vermelho","verde","amarelo","rosa","roxo","marrom","bege","cinza","prata","dourado","laranja","off-white","off white"]

def _softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()

def _normalize_intent_label(label: str) -> str:
    m = {
        "pedir_sugestao_produto": "pedido_sugestao",
        "pedido_sugestao_produto": "pedido_sugestao",
        "pedir_sugestao": "pedido_sugestao",
    }
    lab = (label or "").strip()
    return m.get(lab, lab)

def _looks_like_product_query(text: str) -> bool:
    t = (text or "").lower()
    return any(cat in t for cat in FASHION_CATS)

def _parse_budget(text: str) -> Dict[str, float]:
    """
    Extrai orçamento aproximado:
      - "até 200", "no máximo 150", "por até R$ 300", "entre 150 e 300", "uns 180", "na faixa de 250"
      - "R$ 199", "199 reais"
    Retorna: {"min":..., "max":..., "target":...} (alguns podem faltar)
    """
    t = (text or "").lower().replace(".", "").replace(",", ".")
    vals = [float(m) for m in re.findall(r"(?:r\$\s*)?(\d+(?:\.\d+)?)\s*(?:reais|r\$)?", t)]
    out: Dict[str, float] = {}
    if not vals:
        return out
    if "entre" in t and " e " in t:
        # entre X e Y
        xs = vals[:2]
        if len(xs) == 2:
            out["min"], out["max"] = min(xs), max(xs)
            out["target"] = (out["min"] + out["max"]) / 2.0
            return out
    if "até" in t or "ate" in t or "no máximo" in t or "no maximo" in t:
        out["max"] = max(vals)
        out["target"] = out["max"]
        return out
    # se só um valor: trata como target
    out["target"] = float(vals[0])
    # Se tiver dois e não for "entre", assume min/target
    if len(vals) >= 2 and "entre" not in t:
        out["min"] = min(vals[:2]); out["max"] = max(vals[:2])
    return out

def _parse_color(text: str) -> Optional[str]:
    t = (text or "").lower()
    for c in COLORS:
        if c in t:
            return c
    return None

def _parse_category(text: str) -> Optional[str]:
    t = (text or "").lower()
    for c in FASHION_CATS:
        if c in t:
            return c
    return None

def _safe_float(x) -> float:
    try:
        if x is None: return 0.0
        if isinstance(x, (int, float)): return float(x)
        s = str(x).strip().replace("R$", "").replace(".", "").replace(",", ".")
        return float(re.findall(r"-?\d+(?:\.\d+)?", s)[0]) if re.findall(r"-?\d+(?:\.\d+)?", s) else 0.0
    except Exception:
        return 0.0


# ------------------------------------------------------------------------------
# Classificação (regex; se houver clf+embedder, usa também ML; senão, segue regex)
# ------------------------------------------------------------------------------
def _ensure_embedder_needed(for_ranking: bool = False) -> Optional[object]:
    """Instancia o embedder sob demanda. Evita custo/erro quando inútil."""
    global _embedder
    if _embedder is not None:
        return _embedder
    # Só cria embedder se realmente for necessário:
    need = False
    if for_ranking and index_vecs_norm is not None:
        need = True
    if (clf is not None) and (_labels) and not for_ranking:
        need = True
    if not need:
        return None
    _embedder = _make_embedder()
    return _embedder

def classify_intent(text: str) -> Dict:
    t = text or ""

    # 1) regex rápida
    for lab, pat in REGEX_INTENTS:
        if pat.search(t):
            return {"intent": lab, "conf": 1.0, "gap": 1.0, "probs": {lab: 1.0}, "top3": [(lab, 1.0)]}

    # 1b) heurística forte para busca de produto se mencionar categorias
    if _looks_like_product_query(t):
        return {"intent": "pedido_sugestao", "probs": {"pedido_sugestao": 0.75}, "conf": 0.75, "gap": 0.50, "top3": [("pedido_sugestao", 0.75)]}

    # 2) classificador (se existir) — requer embedder
    if clf is not None and _labels:
        emb = _ensure_embedder_needed(for_ranking=False)
        if emb is not None and hasattr(emb, "encode"):
            try:
                v = emb.encode([t], convert_to_numpy=True)
                if hasattr(clf, "predict_proba"):
                    proba = clf.predict_proba(v)[0]
                else:
                    proba = _softmax(clf.decision_function(v)[0])

                classes = list(map(str, getattr(clf, "classes_", _labels)))
                pairs = list(zip(classes, map(float, proba)))
                pairs.sort(key=lambda x: x[1], reverse=True)
                if pairs:
                    p1 = float(pairs[0][1])
                    p2 = float(pairs[1][1]) if len(pairs) > 1 else 0.0
                    top1 = pairs[0][0]
                    return {
                        "intent": _normalize_intent_label(top1),
                        "conf": p1,
                        "gap": max(0.0, p1 - p2),
                        "probs": dict(pairs),
                        "top3": pairs[:3],
                    }
            except Exception as e:
                log.warning("Falha na classificação ML: %s", e)

    # 3) fallback
    return {"intent": "nao_entendi", "probs": {}, "conf": 0.0, "gap": 0.0, "top3": []}


# ------------------------------------------------------------------------------
# Ranking do catálogo (opcional)
# ------------------------------------------------------------------------------
def _compat_tamanho(item_sizes: str, profile_json: Dict) -> float:
    if not item_sizes:
        return 0.0
    sizes = [s.strip() for s in str(item_sizes).split(";") if s.strip()]
    prefs = set(map(str, profile_json.get("tamanhos_equivalentes", [])))
    if not prefs:
        prefs = {
            str(profile_json.get("tamanho_superior", "")),
            str(profile_json.get("tamanho_inferior", "")),
            str(profile_json.get("tamanho_sup", "")),
        }
    prefs = {p for p in prefs if p}
    if not prefs:
        return 0.5 if sizes else 0.0
    return 1.0 if prefs.intersection(sizes) else 0.0

def _score_estilo(row: pd.Series, profile_json: Dict) -> float:
    s = 0.0
    name = f"{row.get('brand','')} {row.get('name','')} {row.get('category','')} {row.get('description','')}".lower()
    for est in profile_json.get("estilos_preferidos", []):
        if str(est).lower() in name:
            s += 0.2
    for cor in profile_json.get("cores_evitar", []):
        if str(cor).lower() in name:
            s -= 0.1
    for tecido in profile_json.get("tecidos_evitar", []):
        if str(tecido).lower() in name:
            s -= 0.1
    return _clamp01(s)

def _score_price(price: float, hints: Dict[str, float]) -> float:
    if price <= 0.0 or not hints:
        return 0.0
    if "min" in hints and "max" in hints:
        if hints["min"] <= price <= hints["max"]:
            return 1.0
        # distância até o range
        d = 0.0
        if price < hints["min"]:
            d = hints["min"] - price
        elif price > hints["max"]:
            d = price - hints["max"]
        return _clamp01(np.exp(-d / max(1.0, PRICE_TAU)))
    if "target" in hints:
        d = abs(price - hints["target"])
        return _clamp01(np.exp(-d / max(1.0, PRICE_TAU)))
    return 0.0

def _score_filters(row: pd.Series, color: Optional[str], brand: Optional[str], category: Optional[str]) -> float:
    s = 0.0
    if color and str(row.get("color", "")).lower().find(color.lower()) >= 0:
        s += 0.4
    if brand and str(row.get("brand", "")).lower().find(brand.lower()) >= 0:
        s += 0.4
    # Categoria dá um pequeno boost (não filtra duro)
    if category and str(row.get("category", "")).lower().find(category.lower()) >= 0:
        s += 0.2
    return _clamp01(s)

def _qnorm(v: np.ndarray) -> np.ndarray:
    return (v / max(1e-8, norm(v))).astype(np.float32)

def rank_catalog(query: str, k: int = RANK_TOPK, profile_json: dict | None = None) -> pd.DataFrame:
    """
    Retorna DataFrame ranqueado. Usa:
      - Similaridade semântica (sentence-transformers)
      - Compatibilidade de tamanho, estilo do perfil
      - Orçamento/cor/categoria inferidos do texto
    """
    # Precisa de índice + embedder
    if index_vecs_norm is None or index_items.empty:
        return pd.DataFrame()

    emb = _ensure_embedder_needed(for_ranking=True)
    if emb is None or not hasattr(emb, "encode"):
        return pd.DataFrame()

    p = profile_json or profile

    # Hints a partir do texto
    budget = _parse_budget(query)
    color  = _parse_color(query)
    categ  = _parse_category(query)
    brand  = None  # pode ser ampliado com uma lista de marcas suportadas, se houver

    try:
        qv = emb.encode([query], convert_to_numpy=True)[0]
        qv = _qnorm(qv)
    except Exception as e:
        log.warning("Falha ao codificar consulta para ranking: %s", e)
        return pd.DataFrame()

    sims = (index_vecs_norm @ qv)

    rows = index_items.copy()
    rows["sim"] = sims
    rows["score_tamanho"] = rows["sizes"].map(lambda s: _compat_tamanho(s, p))
    rows["score_estilo"]  = rows.apply(lambda r: _score_estilo(r, p), axis=1)
    rows["price_num"]     = rows["price"].map(_safe_float)
    rows["score_preco"]   = rows["price_num"].map(lambda v: _score_price(v, budget))
    rows["score_filter"]  = rows.apply(lambda r: _score_filters(r, color=color, brand=brand, category=categ), axis=1)

    rows["score_total"] = (
        RANK_W_SIM    * rows["sim"] +
        RANK_W_SIZE   * rows["score_tamanho"] +
        RANK_W_STYLE  * rows["score_estilo"] +
        RANK_W_PRICE  * rows["score_preco"] +
        RANK_W_FILTER * rows["score_filter"]
    )

    rows = rows.sort_values("score_total", ascending=False).head(max(1, k)).reset_index(drop=True)
    rows["rank"] = rows.index + 1
    return rows[[
        "rank","score_total","sim","score_tamanho","score_estilo","score_preco","score_filter",
        "brand","name","category","color","material","price","sizes"
    ]]

def _format_recs(df: pd.DataFrame, profile_json: dict | None = None) -> str:
    if df is None or df.empty:
        return ""
    p = profile_json or profile
    out = []
    for _, r in df.iterrows():
        sizes = str(r.get("sizes","")).replace(";", ", ")
        tip_size = ""
        pref = p.get("tamanhos_equivalentes") or [
            p.get("tamanho_superior"),
            p.get("tamanho_inferior"),
            p.get("tamanho_sup"),
        ]
        pref = [x for x in pref if x]
        if pref:
            for x in pref:
                if x and x in str(r.get("sizes","")).split(";"):
                    tip_size = f" | **eu iria de {x}**"
                    break
        out.append(
            f"- **{r.get('brand','')} {r.get('name','')}** "
            f"({r.get('category','')}, {r.get('color','')}, {r.get('material','')}) "
            f"— R$ {r.get('price','')}  \n  tamanhos: {sizes}{tip_size}"
        )
    return "\n".join(out)


# ------------------------------------------------------------------------------
# Fallback Manager
# ------------------------------------------------------------------------------
try:
    from code.fallbacks.manager import FallbackManager
except Exception:
    try:
        from ..fallbacks.manager import FallbackManager  # type: ignore
    except Exception:
        class FallbackManager:  # fallback mínimo
            def need_product_fallback(self, records, min_score: float = 0.35) -> bool:
                return True
            def build_reply_no_products(self, query=None, alternatives=None, **kw) -> str:
                alts = "\n".join(f"- {a}" for a in (alternatives or [])[:5])
                return ("Não encontrei um match agora. Me diga peça/estilo/orçamento para eu refinar.\n" + (alts if alts else ""))

_fbm = FallbackManager()

def _suggest_similar_terms(query: str, topn: int = 5) -> List[str]:
    if index_vecs_norm is None or index_items.empty:
        return []
    emb = _ensure_embedder_needed(for_ranking=True)
    if emb is None or not hasattr(emb, "encode"):
        return []
    try:
        qv = emb.encode([query], convert_to_numpy=True)[0]
        qv = _qnorm(qv)
        sims = (index_vecs_norm @ qv)
        ix = np.argsort(-sims)[: max(topn, 5)]
        picks = index_items.iloc[ix][["brand", "name", "category"]].fillna("")
        alts = [f"{row.brand} {row.name} — {row.category}".strip() for row in picks.itertuples(index=False)]
        seen, uniq = set(), []
        for a in alts:
            if a and a not in seen:
                seen.add(a); uniq.append(a)
        return uniq[:topn]
    except Exception as e:
        log.warning("Falha ao sugerir termos: %s", e)
        return []


# ------------------------------------------------------------------------------
# Respostas
# ------------------------------------------------------------------------------
def generate_response(intent: str, user_text: str, meta: dict | None = None, profile_json: dict | None = None) -> str:
    p = profile_json or (meta or {}).get("profile_json") or profile
    intent = _normalize_intent_label((intent or "").strip())

    if intent == "saudacao":
        return "Oi! Que bom te ver por aqui. Posso te ajudar a encontrar algo?"

    if intent == "ajuda":
        return "Posso ajudar com: **sugestões de roupas**, **frete/prazo**, **pagamento** ou **trocas/devoluções**. Qual desses?"

    if intent == "atendimento_humano":
        return "Posso chamar alguém do time para te atender. Quer que eu encaminhe agora?"

    if intent == "como_comprar":
        return ("Claro! Para comprar:\n"
                "1) Abra a página do produto;\n"
                "2) Escolha o tamanho e clique em **Adicionar ao carrinho**;\n"
                "3) Vá para o **Carrinho** e clique em **Finalizar compra**;\n"
                "4) Informe seus dados e pagamento (Pix ou cartão). Se quiser, faço junto com você.")

    if intent == "frete_prazo":
        cep = str(p.get("cep") or "").strip()
        if cep:
            return f"Com base no seu CEP **{cep}**, o prazo estimado é **3–7 dias úteis** (simulado). Se quiser, calculo o frete detalhado."
        return "O prazo/valor do frete depende do seu **CEP**. Me passa o CEP que eu calculo rapidinho?"

    if intent == "formas_pagamento":
        return "Aceitamos **Pix** e **cartão** (parcelado). Se preferir, eu te mando o passo a passo na página do produto."

    if intent == "troca_devolucao":
        return ("Claro! Para **trocas e devoluções** (compras online), você tem até **7 dias corridos** após o recebimento. "
                "Me passa o **nº do pedido** e o motivo que eu abro a solicitação pra você.")

    if intent == "agradecimento":
        return "Obrigada você! Se precisar de qualquer coisa, tô por aqui."

    # Recomendações: tamanho_modelagem / pedido_sugestao
    if intent in {"tamanho_modelagem", "pedido_sugestao"}:
        recs = rank_catalog(user_text, k=RANK_TOPK, profile_json=p)
        if recs is None or recs.empty:
            # usa FallbackManager para montar uma msg com sugestões
            # aproveita categorias do índice (se houver) para enriquecer
            items_meta = []
            try:
                if not index_items.empty and "category" in index_items.columns:
                    # pegar até 3 categorias populares
                    topcats = (
                        index_items["category"]
                        .astype(str).str.strip()
                        .replace("", np.nan)
                        .dropna()
                        .value_counts()
                        .head(3)
                        .index.tolist()
                    )
                    items_meta = [{"category": c} for c in topcats]
            except Exception:
                pass
            alternativas = _suggest_similar_terms(user_text, topn=5)
            return _fbm.build_reply_no_products(
                query=user_text,
                alternatives=alternativas,
                items_meta=items_meta,
                profile=p,
            )

        return ("Bora achar o look certo para você? Considerei seu perfil 😉\n\n"
                f"{_format_recs(recs, profile_json=p)}\n\n"
                "Se quiser, te ajudo a montar o look completo (bolsa + sapato) e já separo no seu tamanho.")

    # Fallback padrão
    return "Não entendi direitinho. Quer reformular ou me dar mais detalhes?"


# ------------------------------------------------------------------------------
# Telemetria/diagnóstico
# ------------------------------------------------------------------------------
def runtime_index_info() -> Dict:
    return {
        "index_path": str(INDEX_DIR) if INDEX_DIR else "",
        "items": int(len(index_items)) if isinstance(index_items, pd.DataFrame) else 0,
        "embedder": getattr(_embedder, "name_or_path", "none") if _embedder else "none",
        "intents_dir": str(INT_DIR) if INT_DIR else "",
        "clf_loaded": bool(clf is not None),
        "weights": {
            "sim": RANK_W_SIM, "size": RANK_W_SIZE, "style": RANK_W_STYLE,
            "price": RANK_W_PRICE, "filter": RANK_W_FILTER
        },
        "price_tau": PRICE_TAU,
        "topk": RANK_TOPK,
    }
