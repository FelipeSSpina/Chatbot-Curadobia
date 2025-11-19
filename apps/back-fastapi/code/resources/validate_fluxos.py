# -*- coding: utf-8 -*-
#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys, json, yaml
from jsonschema import Draft202012Validator
from pathlib import Path

def main():
    here = Path(__file__).resolve().parent  # pasta 'código/resources'
    ap = argparse.ArgumentParser(description="Valida fluxos.yaml contra fluxos.schema.json")
    ap.add_argument("--schema", default=str((here / "fluxos.schema.json").as_posix()))
    ap.add_argument("--yaml",   default=str((here / "fluxos.yaml").as_posix()))
    args = ap.parse_args()

    schema_path = Path(args.schema)
    yaml_path = Path(args.yaml)

    if not schema_path.exists():
        print(f"❌ Schema não encontrado: {schema_path}")
        sys.exit(1)
    if not yaml_path.exists():
        print(f"❌ YAML não encontrado: {yaml_path}")
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        print("❌ Fluxos inválidos:")
        for err in errors:
            loc = ".".join([str(x) for x in err.path])
            print(f" - {loc}: {err.message}")
        sys.exit(1)
    print("✅ OK: fluxos.yaml está válido contra o schema.")

if __name__ == "__main__":
    main()


