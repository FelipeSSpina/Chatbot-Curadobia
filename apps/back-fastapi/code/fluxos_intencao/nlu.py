# -*- coding: utf-8 -*-
# code/fluxos_intencao/nlu.py
from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, Any, List

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


class IntentClassifier:
    """
    Carrega encoder + classificador (sklearn), gera embeddings e aplica
    regras simples de fallback (limiar + gap do top-2).
    Sempre retorna DICIONÁRIO compatível com o service.ChatService.
    """

    def __init__(
        self,
        models_dir: Path,
        embedder_name: str,
        intent_threshold: float = 0.40,
        top2_gap: float = 0.10,
        fallback_label: str = "nao_entendi",
        **kwargs,
    ) -> None:
        """
        Alias suportados:
          - threshold -> intent_threshold
          - gap       -> top2_gap
        Qualquer outro kw extra é ignorado (para não quebrar).
        """
        # Aliases vindos do service/config antigos
        if "threshold" in kwargs and kwargs["threshold"] is not None:
            intent_threshold = kwargs["threshold"]
        if "gap" in kwargs and kwargs["gap"] is not None:
            top2_gap = kwargs["gap"]

        self.models_dir = Path(models_dir)
        self.intent_threshold = float(intent_threshold)
        self.top2_gap = float(top2_gap)
        self.fallback_label = str(fallback_label)

        # Artefatos treinados
        self.le = joblib.load(self.models_dir / "label_encoder.pkl")
        self.clf = joblib.load(self.models_dir / "classifier.pkl")
        self.labels: np.ndarray = self.le.classes_

        # Embedder HF
        self.embedder_name = embedder_name
        self.emb = SentenceTransformer(self.embedder_name)

    # --------------------------------------------------------------- #
    def _clean(self, s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    def _embed(self, textos: List[str] | str) -> np.ndarray:
        if isinstance(textos, str):
            textos = [textos]
        textos = [self._clean(t) for t in textos]
        vec = self.emb.encode(
            textos,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vec)

    # --------------------------------------------------------------- #
    def predict_text(self, text: str) -> Dict[str, Any]:
        """
        Retorna:
        {
          "intent": <str>,
          "conf": <float>,                # confiança do top-1
          "probs": {rotulo: prob, ...},   # todas as classes
          "top1": <str>, "top2": <str>,
          "gap": <float>                  # top1 - top2
        }
        """
        X = self._embed([text])
        probs = self.clf.predict_proba(X)[0]
        order = np.argsort(probs)[::-1]

        top1_idx = int(order[0])
        top2_idx = int(order[1]) if len(order) > 1 else top1_idx

        top1_label = str(self.labels[top1_idx])
        top2_label = str(self.labels[top2_idx])

        top1_conf = float(probs[top1_idx])
        gap = float(top1_conf - float(probs[top2_idx]))

        final_label = (
            top1_label
            if (top1_conf >= self.intent_threshold and gap >= self.top2_gap)
            else self.fallback_label
        )

        probs_dict = {str(self.labels[i]): float(probs[i]) for i in range(len(self.labels))}

        return {
            "intent": final_label,
            "conf": top1_conf,
            "probs": probs_dict,
            "top1": top1_label,
            "top2": top2_label,
            "gap": gap,
        }

    # Alias usado no service
    def predict(self, text: str) -> Dict[str, Any]:
        return self.predict_text(text)


