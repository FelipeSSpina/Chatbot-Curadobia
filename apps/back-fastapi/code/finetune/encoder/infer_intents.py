# -*- coding: utf-8 -*-
# file: code/finetune/encoder/infer_intents.py
import argparse, json, os
import numpy as np, pandas as pd
from sklearn.metrics import classification_report, f1_score, confusion_matrix
from joblib import load

def load_meta(model_dir):
    with open(os.path.join(model_dir, "meta.json"), "r", encoding="utf-8") as f:
        return json.load(f)

def main(args):
    meta = load_meta(args.model_dir)
    clf = load(os.path.join(args.model_dir, "clf.joblib"))
    embedder_name = meta["embedder"]

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(embedder_name)

    df = pd.read_csv(args.data).fillna("")
    X = model.encode(df["text"].tolist(), normalize_embeddings=True)
    y_true = df["label"].tolist()
    y_pred = clf.predict(X)

    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    f1_macro = f1_score(y_true, y_pred, average="macro")

    # Usa labels do meta.json
    labels = meta.get("labels", sorted(list(set(y_true) | set(y_pred))))
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()

    out = {
        "f1_macro": f1_macro,
        "report": report,
        "confusion": cm,
        "labels": labels
    }
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"F1 macro: {f1_macro:.6f}")
    print(f"✔ Relatório salvo em {args.report}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_dir", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()
    main(args)


