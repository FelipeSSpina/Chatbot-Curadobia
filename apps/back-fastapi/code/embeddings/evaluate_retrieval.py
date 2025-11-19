# -*- coding: utf-8 -*-
"""
Avaliação de recuperação semântica para o catálogo Curadobia.

Novidades:
- Filtros (--filter_category) e amostragem (--sample_queries N --seed).
- Métricas extra: Recall@K e nDCG@K, além de Precision@K e MRR.
- Saída JSON com resumo e (opcional) detalhes por consulta.

Modos:
(1) Avaliar UM modelo:
  python -m code.embeddings.evaluate_retrieval \
    --catalog data/catalog/catalog_normalized.csv \
    --queries_csv data/embeddings/eval_queries.csv \
    --embedder sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
    --k 1,5,10

(2) Comparar BASELINE vs. TUNED com índices:
  python -m code.embeddings.evaluate_retrieval \
    --index_baseline models/catalog_index \
    --index_tuned    notebooks/outputs/models/fashion_embeddings/catalog_index \
    --queries_csv    data/embeddings/eval_queries.csv \
    --baseline_model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
    --tuned_model    notebooks/outputs/models/fashion_embeddings \
    --k 5
"""

from __future__ import annotations
import argparse, json
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import random

import numpy as np
import pandas as pd
from numpy.linalg import norm
from sentence_transformers import SentenceTransformer

# --------------------- utilidades ---------------------
def load_catalog(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path).fillna("")
    return df

def build_text(row: pd.Series) -> str:
    return " ".join([
        str(row.get("brand", "")),
        str(row.get("name", "")),
        str(row.get("category", "")),
        str(row.get("material", "")),
        str(row.get("description", "")),
    ]).strip()

def encode_items(embedder: SentenceTransformer, catalog: pd.DataFrame) -> np.ndarray:
    texts = catalog.apply(build_text, axis=1).tolist()
    vecs = embedder.encode(texts, convert_to_numpy=True)
    # normaliza uma vez
    norms = np.maximum(norm(vecs, axis=1, keepdims=True), 1e-8)
    return (vecs / norms).astype(np.float32)

def rank(vecs_norm: np.ndarray, qv_norm: np.ndarray, k: int) -> np.ndarray:
    sims = (vecs_norm @ qv_norm)
    return np.argsort(-sims)[:k]

def precision_at_k(results: Sequence[int], relevant: Iterable[int], k: int) -> float:
    rel = set(int(i) for i in relevant)
    hits = sum(1 for idx in results[:k] if idx in rel)
    return hits / max(1, k)

def recall_at_k(results: Sequence[int], relevant: Iterable[int], k: int) -> float:
    rel = set(int(i) for i in relevant)
    hits = sum(1 for idx in results[:k] if idx in rel)
    return hits / max(1, len(rel) or 1)

def ndcg_at_k(results: Sequence[int], relevant: Iterable[int], k: int) -> float:
    rel = set(int(i) for i in relevant)
    dcg = 0.0
    for rank_idx, idx in enumerate(results[:k], start=1):
        gain = 1.0 if idx in rel else 0.0
        dcg += gain / np.log2(rank_idx + 1)
    # ideal DCG
    ideal_hits = min(k, len(rel))
    idcg = sum(1.0 / np.log2(i + 1) for i in range(1, ideal_hits + 1))
    return (dcg / idcg) if idcg > 0 else 0.0

def mean_reciprocal_rank(results: Sequence[int], relevant: Iterable[int]) -> float:
    rel = set(int(i) for i in relevant)
    for rank_idx, idx in enumerate(results, start=1):
        if idx in rel:
            return 1.0 / rank_idx
    return 0.0

def parse_ks(s: str) -> List[int]:
    return sorted({int(x.strip()) for x in str(s or "5").split(",") if x.strip()})

def load_queries_json(path: Path | str) -> List[Tuple[str, Sequence[int]]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(str(it["query"]), list(map(int, it.get("relevant_indices", [])))) for it in payload]

def load_queries_csv(path: Path | str, catalog: pd.DataFrame) -> List[Tuple[str, Sequence[int]]]:
    """
    CSV com colunas: query,must_have (substring que deve aparecer em brand/name/category)
    Gera relevantes por varredura no catálogo.
    """
    dfq = pd.read_csv(path).fillna("")
    pairs: List[Tuple[str, Sequence[int]]] = []
    mask_all = (catalog["brand"].astype(str) + " " + catalog["name"].astype(str) + " " + catalog["category"].astype(str)).str.lower()
    for it in dfq.itertuples(index=False):
        q = str(getattr(it, "query"))
        mh = str(getattr(it, "must_have", "")).strip().lower()
        if not mh:
            pairs.append((q, []))
            continue
        idxs = [i for i, txt in enumerate(mask_all) if mh in txt]
        pairs.append((q, idxs))
    return pairs

def maybe_load_index(dir_path: Optional[str]) -> Optional[Tuple[pd.DataFrame, np.ndarray]]:
    if not dir_path:
        return None
    p = Path(dir_path)
    items = p / "items.csv"
    vecs = p / "vectors.npy"
    if items.exists() and vecs.exists():
        # normaliza em memória
        items_df = pd.read_csv(items).fillna("")
        raw = np.load(vecs)
        norms = np.maximum(norm(raw, axis=1, keepdims=True), 1e-8)
        return items_df, (raw / norms).astype(np.float32)
    return None

# --------------------- avaliação ---------------------
def eval_system(
    *,
    name: str,
    queries: List[Tuple[str, Sequence[int]]],
    catalog: pd.DataFrame,
    item_vecs_norm: Optional[np.ndarray],
    embedder: Optional[SentenceTransformer],
    ks: List[int],
) -> Dict:
    assert item_vecs_norm is not None or embedder is not None, "Passe vetores OU um embedder."

    if item_vecs_norm is None:
        assert embedder is not None
        item_vecs_norm = encode_items(embedder, catalog)

    results = []
    per_k_precisions: Dict[int, List[float]] = {k: [] for k in ks}
    per_k_recalls: Dict[int, List[float]] = {k: [] for k in ks}
    per_k_ndcg: Dict[int, List[float]] = {k: [] for k in ks}
    mrrs: List[float] = []

    for q, relevant in queries:
        if embedder is None:
            raise ValueError("É preciso um embedder para codificar as consultas.")
        qv = embedder.encode([q], convert_to_numpy=True)[0]
        qv = (qv / max(1e-8, norm(qv))).astype(np.float32)

        top_n = max(ks)
        idx = rank(item_vecs_norm, qv, k=top_n).tolist()

        for k in ks:
            per_k_precisions[k].append(precision_at_k(idx, relevant, k))
            per_k_recalls[k].append(recall_at_k(idx, relevant, k))
            per_k_ndcg[k].append(ndcg_at_k(idx, relevant, k))
        mrrs.append(mean_reciprocal_rank(idx, relevant))

        results.append({"query": q, "relevant": list(map(int, relevant)), "top_idx": idx})

    summary = {
        "system": name,
        "n_queries": len(queries),
        **{f"precision@{k}": round(mean(per_k_precisions[k]), 4) for k in ks},
        **{f"recall@{k}": round(mean(per_k_recalls[k]), 4) for k in ks},
        **{f"ndcg@{k}": round(mean(per_k_ndcg[k]), 4) for k in ks},
        "mrr": round(mean(mrrs), 4) if mrrs else 0.0,
    }
    return {"summary": summary, "results": results}

# --------------------- CLI ---------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Avaliação de recuperação (P@K/R@K/nDCG/MRR) para embeddings do catálogo.")
    # catálogo/índices
    ap.add_argument("--catalog", default="data/catalog/catalog_normalized.csv")
    ap.add_argument("--index_baseline", default=None)
    ap.add_argument("--index_tuned", default=None)
    # modelos
    ap.add_argument("--embedder", default=None)
    ap.add_argument("--baseline_model", default=None)
    ap.add_argument("--tuned_model", default=None)
    # queries
    ap.add_argument("--queries_json", default=None)
    ap.add_argument("--queries_csv", default=None)
    ap.add_argument("--sample_queries", type=int, default=None, help="Amostrar N consultas aleatórias")
    ap.add_argument("--seed", type=int, default=42)
    # filtros
    ap.add_argument("--filter_category", default=None, help="Avaliar apenas itens com esta categoria (substring)")
    # extras
    ap.add_argument("--k", default="5")
    ap.add_argument("--out_details", default=None)
    args = ap.parse_args()

    random.seed(args.seed)
    ks = parse_ks(args.k)

    # Carregar catálogo / índices normalizados
    idx_base = maybe_load_index(args.index_baseline)
    idx_tune = maybe_load_index(args.index_tuned)
    if idx_base:
        catalog = idx_base[0]
    elif idx_tune:
        catalog = idx_tune[0]
    else:
        catalog = load_catalog(args.catalog)

    if args.filter_category:
        mask = (catalog["category"].astype(str).str.lower().str.contains(args.filter_category.lower()))
        catalog = catalog[mask].reset_index(drop=True)

    # Carregar consultas
    if args.queries_json:
        queries = load_queries_json(args.queries_json)
    elif args.queries_csv:
        queries = load_queries_csv(args.queries_csv, catalog)
    else:
        raise SystemExit("Forneça --queries_json ou --queries_csv.")

    if args.sample_queries and args.sample_queries < len(queries):
        queries = random.sample(queries, args.sample_queries)

    outputs = []

    # Caso 1: avaliação única
    if args.embedder and not (args.baseline_model or args.tuned_model):
        model = SentenceTransformer(args.embedder)
        out = eval_system(
            name=args.embedder,
            queries=queries,
            catalog=catalog,
            item_vecs_norm=None,  # calcularemos
            embedder=model,
            ks=ks,
        )
        outputs.append(out)

    # Caso 2: comparação baseline vs tuned
    if args.baseline_model and args.tuned_model:
        base_embedder = SentenceTransformer(args.baseline_model)
        tuned_embedder = SentenceTransformer(args.tuned_model)

        out_base = eval_system(
            name="baseline",
            queries=queries,
            catalog=catalog,
            item_vecs_norm=idx_base[1] if idx_base else None,
            embedder=base_embedder,
            ks=ks,
        )
        out_tune = eval_system(
            name="tuned",
            queries=queries,
            catalog=catalog,
            item_vecs_norm=idx_tune[1] if idx_tune else None,
            embedder=tuned_embedder,
            ks=ks,
        )
        outputs.extend([out_base, out_tune])

    if not outputs:
        raise SystemExit("Nada para avaliar: informe --embedder ou ( --baseline_model e --tuned_model ).")

    # Agregar e imprimir
    summary = [o["summary"] for o in outputs]
    print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))

    # Salvar detalhes opcionalmente
    if args.out_details:
        Path(args.out_details).write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
