# -*- coding: utf-8 -*-
"""
Treinador leve para ajustar MiniLM ao domínio de moda.

Entradas:
- CSV com colunas: query,positive[,negative]
  * Se 'negative' existir -> TripletLoss (anchor, positive, negative).
  * Caso contrário -> MultipleNegativesRankingLoss com pares (query, positive).

Melhorias:
- Normalização Unicode (UTF-8/NFKC) e remoção de caracteres corrompidos.
- Sem drop_last (preserva dados em dataset pequeno).
- Registro de hiperparâmetros/métricas em out/train_log.json.
- **Batch-size adaptativo**: se usar TripletLoss e batch>32, reduz para 32.
  Em caso de OOM, tenta novamente reduzindo pela metade até >=4.
"""

import argparse, os, json, time, unicodedata, random
from pathlib import Path
import pandas as pd
from torch.utils.data import DataLoader
from sentence_transformers import SentenceTransformer, InputExample, losses

def _clean(s: str) -> str:
    s = str(s or "")
    s = unicodedata.normalize("NFKC", s)
    return s.replace("\uFFFD", "").replace("�", "").strip()

def load_pairs(path: str):
    p = Path(path)
    if not p.exists():
        df = pd.DataFrame({
            "query": ["vestido midi preto", "blazer alfaiataria bege", "calça reta off white"],
            "positive": ["vestido preto midi elegante", "blazer bege de linho", "calça reta cor off white algodão"],
        })
    else:
        df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8")
    df = df.applymap(_clean)

    has_neg = "negative" in df.columns
    samples = []
    if has_neg:
        for r in df.itertuples(index=False):
            samples.append(InputExample(texts=[r.query, r.positive, getattr(r, "negative")]))
    else:
        for r in df.itertuples(index=False):
            samples.append(InputExample(texts=[r.query, r.positive]))
    return samples, has_neg

def _fit_with_retry(model, loss, samples, batch_size, epochs, out_dir, warmup_steps):
    """Tenta treinar; se OOM, reduz batch pela metade até 4."""
    bs = int(batch_size)
    while bs >= 4:
        try:
            loader = DataLoader(samples, shuffle=True, batch_size=bs)
            model.fit(train_objectives=[(loader, loss)],
                      epochs=epochs,
                      warmup_steps=warmup_steps,
                      output_path=out_dir)
            return bs, None
        except RuntimeError as e:
            msg = str(e).lower()
            if "out of memory" in msg or "cuda" in msg:
                bs = max(4, bs // 2)
                print(f"[TRAIN] OOM detectado, tentando novamente com batch_size={bs}...")
                continue
            return bs, e
    return bs, RuntimeError("Falha por OOM com batch_size mínimo.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/embeddings/fashion_pairs.csv")
    ap.add_argument("--base", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    ap.add_argument("--out", default="notebooks/outputs/models/fashion_embeddings")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)

    samples, has_neg = load_pairs(args.pairs)
    model = SentenceTransformer(args.base)

    # Loss + batch-size adaptativo
    loss = losses.TripletLoss(model) if has_neg else losses.MultipleNegativesRankingLoss(model)
    eff_bs = args.batch_size
    if has_neg and eff_bs > 32:
        print(f"[TRAIN] TripletLoss detectado: ajustando batch_size {eff_bs} → 32 por padrão.")
        eff_bs = 32

    warmup = max(10, int(0.1 * max(1, (len(samples) // max(1, eff_bs)))))
    t0 = time.time()
    used_bs, err = _fit_with_retry(model, loss, samples, eff_bs, args.epochs, args.out, warmup)
    dur = time.time() - t0

    # Log de execução
    os.makedirs(args.out, exist_ok=True)
    log_path = Path(args.out) / "train_log.json"
    log = {
        "pairs_path": args.pairs,
        "base_model": args.base,
        "output_path": args.out,
        "epochs": args.epochs,
        "batch_size_requested": args.batch_size,
        "batch_size_used": used_bs,
        "samples": len(samples),
        "loss": "TripletLoss" if has_neg else "MultipleNegativesRankingLoss",
        "warmup_steps": warmup,
        "duration_sec": round(dur, 2),
        "seed": args.seed,
        "error": None if err is None else str(err),
    }
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[TRAIN] Modelo salvo em: {args.out}")
    print(f"[TRAIN] Log: {log_path} | batch_size={used_bs}")

if __name__ == "__main__":
    main()
