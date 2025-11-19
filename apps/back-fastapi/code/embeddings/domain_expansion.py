# -*- coding: utf-8 -*-
# file: code/embeddings/domain_expansion.py
"""Ferramentas para expans�o de vocabul�rio e consultas do dom�nio moda."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

_DEFAULT_TERMS: Dict[str, List[str]] = {
    "vestido": ["midi", "longuete", "evas�", "alfaiataria"],
    "blazer": ["alfaiataria", "estruturado", "oversized"],
    "tecido": ["linho", "viscose", "crepe", "jacquard"],
    "caimento": ["acinturado", "solto", "reta", "flare"],
    "tamanho": ["pp", "p", "m", "g", "gg", "36", "38", "40", "42"],
}


@dataclass(slots=True)
class FashionVocabulary:
    synonyms: Dict[str, List[str]] = field(default_factory=lambda: dict(_DEFAULT_TERMS))

    def add(self, term: str, related: Sequence[str]) -> None:
        base = self.synonyms.setdefault(term.lower(), [])
        for item in related:
            item_l = item.lower().strip()
            if item_l and item_l not in base:
                base.append(item_l)

    def expand_query(self, query: str, max_terms: int = 8) -> List[str]:
        tokens = [tok.strip().lower() for tok in query.split() if tok.strip()]
        expansions: List[str] = []
        for tok in tokens:
            expansions.extend(self.synonyms.get(tok, []))
        combined = list(dict.fromkeys(tokens + expansions))
        return combined[:max_terms]

    def to_json(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.synonyms, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path | str) -> "FashionVocabulary":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(synonyms={k.lower(): [v.lower() for v in values] for k, values in payload.items()})


def export_terms(csv_path: Path | str, vocab: FashionVocabulary) -> None:
    import csv

    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["termo", "sinonimo"])
        for term, synonyms in sorted(vocab.synonyms.items()):
            for syn in synonyms:
                writer.writerow([term, syn])


__all__ = ["FashionVocabulary", "export_terms"]


