# -*- coding: utf-8 -*-
# file: code/context/normalize_catalog.py
# Normaliza um catálogo CSV/Excel para o schema:
# id,brand,name,category,color,material,price,sizes,stock_json,description
import argparse, os, json, re, pandas as pd

CAND = {
    "id": ["id","sku","codigo","cod"],
    "brand": ["brand","marca"],
    "name": ["name","produto","nome","titulo","description_short"],
    "category": ["category","categoria","tipo"],
    "color": ["color","cor"],
    "material": ["material","tecido","composicao","fabric"],
    "price": ["price","preco","valor"],
    "sizes": ["sizes","tamanhos","grade","grade_tam","variantes_tamanho"],
    "stock": ["stock_json","estoque","quantidade","qtd","stock"]
}

def pick(df, keys, default=None):
    cols = list(df.columns)
    for k in keys:
        for c in cols:
            if c.lower().strip() == k:
                return c
    return default

def coerce_sizes(val):
    if pd.isna(val): return ""
    s = str(val)
    s = re.sub(r"[,\|/]", ";", s)
    s = ";".join([x.strip().upper() for x in s.split(";") if x.strip()])
    return s

def guess_stock(row, stock_col):
    # tenta ler stock_json; senão cria com 1 por tamanho
    if stock_col and pd.notna(row[stock_col]):
        try:
            obj = row[stock_col]
            if isinstance(obj, str):
                return json.dumps(json.loads(obj))
            if isinstance(obj, dict):
                return json.dumps(obj)
        except Exception:
            pass
    sizes = str(row["sizes"]).split(";") if pd.notna(row["sizes"]) else []
    return json.dumps({s: 1 for s in sizes if s})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="CSV/Excel com o catálogo bruto (export do PDF ou planilha)")
    ap.add_argument("--out", required=True, help="CSV normalizado")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if args.src.lower().endswith((".xlsx",".xls")):
        try:
            import openpyxl  # para .xlsx
        except Exception:
            raise SystemExit("Para ler .xlsx, instale: pip install openpyxl")
        df = pd.read_excel(args.src)
    else:
        df = pd.read_csv(args.src)

    # normaliza nomes
    df.columns = [c.strip() for c in df.columns]
    lower_map = {c: c.lower().strip() for c in df.columns}
    df = df.rename(columns=lower_map)

    out = pd.DataFrame()
    out["id"]       = df[pick(df, CAND["id"], default=list(df.columns)[0])] if pick(df, CAND["id"]) else range(1, len(df)+1)
    out["brand"]    = df[pick(df, CAND["brand"], default=list(df.columns)[0])]
    out["name"]     = df[pick(df, CAND["name"], default=list(df.columns)[1])]
    out["category"] = df[pick(df, CAND["category"], default=list(df.columns)[2])]
    out["color"]    = df[pick(df, CAND["color"])] if pick(df, CAND["color"]) else ""
    out["material"] = df[pick(df, CAND["material"])] if pick(df, CAND["material"]) else ""
    price_col = pick(df, CAND["price"])
    out["price"]    = pd.to_numeric(df[price_col] if price_col else 0, errors="coerce").fillna(0).round(2)

    sizes_col = pick(df, CAND["sizes"])
    out["sizes"] = df[sizes_col].map(coerce_sizes) if sizes_col else ""

    stock_col = pick(df, CAND["stock"])
    out["stock_json"] = df.apply(lambda r: guess_stock(r, stock_col), axis=1)

    def build_desc(r):
        parts = [str(r.get("brand","")), str(r.get("name","")), str(r.get("category","")), str(r.get("material",""))]
        return " | ".join([p for p in parts if p and p != "nan"])
    out["description"] = df["description"] if "description" in df.columns else out.apply(build_desc, axis=1)

    out.to_csv(args.out, index=False, encoding="utf-8")
    print(f"✔ Catálogo normalizado em {args.out} ({len(out)} itens)")

if __name__ == "__main__":
    main()


