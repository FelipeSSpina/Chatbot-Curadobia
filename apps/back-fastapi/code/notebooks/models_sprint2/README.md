# Curadobia � Classificador de Inten��es (Sprint 2)

**Embeddings**: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
**Modelo**: CalibratedClassifierCV (calibrado: True)
**Labels**: agradecimento, buscar_produto_por_categoria, buscar_produto_por_nome, despedida, erros_plataforma, falar_com_humano, formas_pagamento, frete_prazo, materiais_cuidados, saudacao, status_pedido, styling_sugestao_look, tamanho_modelagem

## Uso r�pido
```python
from sentence_transformers import SentenceTransformer
import joblib
embedder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
clf = joblib.load("classifier.pkl")
le �= joblib.load("label_encoder.pkl")
textos = ["oi bia", "qual prazo para 01234-567?"]
X = embedder.encode(textos, normalize_embeddings=True)
pred = clf.predict(X)
labels = le.inverse_transform(pred)
print(labels)

