# -*- coding: utf-8 -*-
# Gera queries_indices.json a partir de eval_queries.csv e do catálogo.
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="data/catalog/catalog_normalized.csv")
    ap.add_argument("--eval_csv", default="data/embeddings/eval_queries.csv")
    ap.add_argument("--out_json", default="data/embeddings/queries_indices.json")
    args = ap.parse_args()

    cat = pd.read_csv(args.catalog).fillna("")
    mask_series = (cat["brand"].astype(str) + " " + cat["name"].astype(str) + " " + cat["category"].astype(str)).str.lower()

    q = pd.read_csv(args.eval_csv).fillna("")
    payload = []
    for r in q.itertuples(index=False):
        query = str(getattr(r, "query"))
        must = str(getattr(r, "must_have", "")).strip().lower()
        idxs = [i for i, txt in enumerate(mask_series) if must in txt] if must else []
        payload.append({"query": query, "relevant_indices": idxs})

    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] gravado {args.out_json} com {len(payload)} consultas.")

if __name__ == "__main__":
    main()
