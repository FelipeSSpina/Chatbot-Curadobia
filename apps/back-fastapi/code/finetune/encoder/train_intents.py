# -*- coding: utf-8 -*-
# file: code/finetune/encoder/train_intents.py
# CÉLULA 1 — Treino do classificador de intenções (embeddings + LR calibrado)
import argparse, json, os, random, numpy as np, pandas as pd
from dataclasses import dataclass, asdict
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from joblib import dump

@dataclass
class Meta:
    embedder: str
    seed: int
    threshold: float
    gap_top2: float
    labels: list

def set_seed(seed: int):
    random.seed(seed); np.random.seed(seed)

def load_data(path: str):
    df = pd.read_csv(path)
    if not {"text","label"}.issubset(df.columns):
        raise ValueError("CSV precisa conter colunas 'text' e 'label'.")
    return df

def embed_texts(model, texts):
    return model.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True)

def train(args):
    set_seed(args.seed)
    os.makedirs(args.out, exist_ok=True)
    df = load_data(args.data)
    labels = sorted(df["label"].unique().tolist())

    emb = SentenceTransformer(args.embedder)
    X = embed_texts(emb, df["text"].tolist())
    y = df["label"].values

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=args.seed, stratify=y)

    base = LogisticRegression(max_iter=300, class_weight="balanced", multi_class="auto", solver="lbfgs")
    try:
        clf = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    except TypeError:
        clf = CalibratedClassifierCV(base_estimator=base, method="sigmoid", cv=3)

    clf.fit(X_tr, y_tr)

    y_pred = clf.predict(X_te)
    report = classification_report(y_te, y_pred, digits=4)
    print(report)

    dump(clf, os.path.join(args.out, "clf.joblib"))
    meta = Meta(embedder=args.embedder, seed=args.seed, threshold=args.threshold, gap_top2=args.gap_top2, labels=labels)
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(meta), f, ensure_ascii=False, indent=2)
    print(f"✔ Modelo salvo em {args.out}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--embedder", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    p.add_argument("--out", required=True)
    p.add_argument("--threshold", type=float, default=0.30)
    p.add_argument("--gap_top2", type=float, default=0.08)
    p.add_argument("--seed", type=int, default=42)  # <-- corrigido
    args = p.parse_args()
    train(args)


