# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import argparse, yaml, csv

def main():
    ap = argparse.ArgumentParser(description="Exporta tabela de transições a partir do fluxos.yaml")
    ap.add_argument("--yaml", default="2025-2A-T07-CC11-G04/código/resources/fluxos.yaml")
    ap.add_argument("--out", default="2025-2A-T07-CC11-G04/docs/tabela_transicoes.csv")
    args = ap.parse_args()

    with open(args.yaml, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    rows = []
    for state, sdef in doc.get("states", {}).items():
        for tr in sdef.get("transitions", []) or []:
            rows.append({
                "origem": state,
                "intencao": tr.get("intent", ""),
                "guarda": tr.get("guard", ""),
                "acao": tr.get("action", ""),
                "proximo_estado": tr.get("next", "")
            })

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["origem","intencao","guarda","acao","proximo_estado"])
        w.writeheader()
        w.writerows(rows)
    print(f"✅ Exportado {len(rows)} transições em {args.out}")

if __name__ == "__main__":
    main()


