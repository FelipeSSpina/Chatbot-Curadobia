### `code/context/api.py`
```python
# file: code/context/api.py
import os, json, numpy as np, pandas as pd
from sentence_transformers import SentenceTransformer

_cached = {"index_dir": None, "items": None, "vecs": None, "model": None}

def load_index(index_dir: str):
    if _cached["index_dir"] == index_dir and _cached["items"] is not None:
        return _cached["items"], _cached["vecs"], _cached["model"]
    items = pd.read_csv(os.path.join(index_dir, "items.csv")).fillna("")
    vecs = np.load(os.path.join(index_dir, "vectors.npy"))
    with open(os.path.join(index_dir, "meta.json"), "r", encoding="utf-8") as f:
        meta = json.load(f)
    model = SentenceTransformer(meta["embedder"])
    _cached.update(index_dir=index_dir, items=items, vecs=vecs, model=model)
    return items, vecs, model

def _cos(a,b): return np.dot(a,b.T)
def _sizes(s): return [x.strip().upper() for x in str(s).split(";") if x.strip()]

def _size_score(profile, sizes, stock_json):
    want = set(map(lambda x: str(x).upper(), (profile.get("tamanhos_equivalentes") or [])))
    for key in ["tamanho_superior","tamanho_inferior"]:
        v = str(profile.get(key,"")).upper().strip()
        if v: want.add(v)
    if not want: return 0.0
    try: stock = json.loads(stock_json) if isinstance(stock_json,str) else stock_json
    except: stock = {}
    for w in want:
        if w in sizes and int(stock.get(w,1))>0: return 1.0
    if any(w in sizes for w in want): return 0.5
    return 0.0

def suggest(index_dir: str, profile: dict, query: str, k: int = 5):
    items, vecs, model = load_index(index_dir)
    qvec = model.encode([query], normalize_embeddings=True)
    sims = _cos(qvec, vecs)[0]
    rows = items.to_dict(orient="records")
    scored = []
    for i, r in enumerate(rows):
        s_size = _size_score(profile, _sizes(r.get("sizes","")), r.get("stock_json","{}"))
        total = 0.8*float(sims[i]) + 0.2*s_size
        scored.append((total, i))
    scored.sort(reverse=True)
    return [rows[i] for _, i in scored[:max(1,k)]]
