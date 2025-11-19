# -*- coding: utf-8 -*-
# file: code/fluxos_intencao/cli_demo.py
#!/usr/bin/env python3
import argparse, os
from pathlib import Path
from .service import ChatService

def main():
    p = argparse.ArgumentParser(description="CLI de demo do orquestrador de fluxos")
    p.add_argument("--yaml",       default="code/resources/fluxos.yaml")
    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", ""))
    p.add_argument("--embedder",   default=os.environ.get("HF_EMBEDDER", "sentence-transformers/all-MiniLM-L6-v2"))
    args = p.parse_args()

    if args.yaml:       os.environ["FLUXOS_YAML"] = str(Path(args.yaml).resolve())
    if args.models_dir: os.environ["MODELS_DIR"]  = str(Path(args.models_dir).resolve())
    if args.embedder:   os.environ["HF_EMBEDDER"] = args.embedder

    svc = ChatService()
    print("💬 Sessão iniciada. (digite 'sair' para encerrar)\n")

    # Mostra a entry do estado atual (START) como boas-vindas
    initial = svc.engine.entry_text(svc.state)
    if initial:
        print(f"BIA: {initial}  [estado={svc.state} | intenção=—]")

    while True:
        try:
            msg = input("Você: ").strip()
            if msg.lower() in ("sair", "exit", "quit"):
                break
            reply, meta = svc.handle(msg, ctx={})
            print(f"BIA: {reply}  [estado={meta['estado']} | intenção={meta['intencao']}]")
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()


