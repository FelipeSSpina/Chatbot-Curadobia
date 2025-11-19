from dataclasses import dataclass
from pathlib import Path
import os, json

ROOT = Path(__file__).resolve().parents[1]        # .../code
RES  = ROOT / "resources"
DOCS = ROOT.parent / "docs"

@dataclass
class Config:
    fluxos_yaml: Path = RES / "fluxos.yaml"
    db_path: Path     = ROOT / "fluxos_intencao.sqlite"
    # default agora aponta para code/notebooks/modelos
    models_dir: Path  = ROOT.parent.parent.parent / "notebooks" / "modelos"
    hf_embedder: str  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    intent_threshold: float = 0.40
    intent_top2_gap: float  = 0.10
    fallback_label: str     = "nao_entendi"

    @classmethod
    def from_env(cls):
        cfg = cls()
        def cast(name, value):
            low = name.lower()
            if any(x in low for x in ("path", "dir", "yaml")):
                return Path(value)
            if low in ("intent_threshold", "intent_top2_gap"):
                return float(value)
            return value
        for name in vars(cfg).keys():
            val = os.getenv(name.upper())
            if val:
                setattr(cfg, name, cast(name, val))
        return cfg

def pretty(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


