# -*- coding: utf-8 -*-
# file: /code/context/make_sample_profile.py
import argparse, os, json
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/profiles/cliente_exemplo.json")
    args = p.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    profile = {
        "user_id": "demo",
        "tamanho_superior": "M",
        "tamanho_inferior": "38",
        "tamanhos_equivalentes": ["M","38","40"],
        "estilos_preferidos": ["alfaiataria","minimalista"],
        "cores_evitar": ["amarelo"],
        "ocasioes_frequentes": ["jantar","trabalho"],
        "tecidos_evitar": ["poliéster"]
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"✔ Perfil exemplo criado em {args.out}")
if __name__ == "__main__":
    main()


