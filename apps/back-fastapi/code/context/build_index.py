# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, os, json, time
import pandas as pd
import numpy as np

# Tenta importar o loader do projeto; se n�o tiver, usa fallback direto
try:
    from .embedding_loader import get_embedder as _loader_get_embedder  # type: ignore
except Exception:
    _loader_get_embedder = None

def _safe_get_embedder(name: str | None):
    """
    Usa o get_embedder(name) do projeto, mas se a assinatura for antiga (sem args),
    chama sem par�metro; se n�o existir, cai no SentenceTransformer direto.
    """
    if _loader_get_embedder is not None:
        try:
            return _loader_get_embedder(name)        # nova assinatura
        except TypeError:
            enc, nm = _loader_get_embedder()         # assinatura antiga
            return enc, (name or nm)

    # fallback puro
    from sentence_transformers import SentenceTransformer
    model_name = name or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    model = SentenceTransformer(model_name)
    def encode(texts):
        return model.encode(texts, normalize_embeddings=True)
    return encode, model_name

def _concat_text(row: dict) -> str:
    parts = [
        str(row.get("brand","")), str(row.get("name","")), str(row.get("category","")),
        str(row.get("color","")), str(row.get("material","")), str(row.get("description",""))
    ]
    return " ".join([p for p in parts if p])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--embedder", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    df = pd.read_csv(args.catalog).fillna("")
    texts = [_concat_text(r) for r in df.to_dict(orient="records")]

    encode, embedder_name = _safe_get_embedder(args.embedder)
    vecs = encode(texts).astype("float32")

    items_csv = os.path.join(args.out, "items.csv")
    vecs_npy  = os.path.join(args.out, "vectors.npy")
    meta_json = os.path.join(args.out, "meta.json")

    df.to_csv(items_csv, index=False, encoding="utf-8")
    np.save(vecs_npy, vecs)
    with open(meta_json, "w", encoding="utf-8") as f:
        json.dump({"embedder": embedder_name, "built_at": int(time.time())}, f, ensure_ascii=False, indent=2)

    print(f"[INDEX] ok -> {args.out}")

if __name__ == "__main__":
    main()

