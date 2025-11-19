# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Callable, Tuple, List
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def get_embedder(name: str | None = None) -> Tuple[Callable[[List[str]], "np.ndarray"], str]:
    """
    Retorna (encode_fn, model_name). Aceita nome opcional do modelo.
    Compat�vel com chamadas antigas que n�o passavam par�metro.
    """
    model_name = name or DEFAULT_MODEL
    model = SentenceTransformer(model_name)

    def encode(texts):
        return model.encode(texts, normalize_embeddings=True)

    return encode, model_name

