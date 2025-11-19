---
title: "Curadobia � Sprint 2 � Exec Summary"
---

# ? Resumo Executivo

**Embedder:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
**Modelo final:** `Calibrated CalibratedClassifierCV`
**Threshold:** `0.30`  |  **GAP top-2:** `0.00`
**Hugging Face:** https://huggingface.co/t07-cc11-g4/2025-2a-t07-cc11-g04-intent-classifier-sprint2

## ?? Scoreboard (top linhas)
```text
                                 modelo conjunto  accuracy  f1_macro  f1_weighted                 observa��es
                       TFIDF � TFIDF+LR CV (val)    0.7486    0.7255          NaN Melhor baseline TF-IDF (CV)
        Embeddings � LogisticRegression CV (val)    0.6464    0.5932       0.6573       Sentence-Transformers
              Embeddings � RandomForest CV (val)    0.6565    0.3496       0.6063       Sentence-Transformers
           CalibratedClassifierCV (raw)    TESTE    0.6892    0.4186       0.6758                   Calibrado
CalibratedClassifierCV (+threshold/gap)    TESTE    0.5608    0.3681       0.5700                   Calibrado
```

## ?? Teste (raw vs threshold/gap)

```text
                                  setup  accuracy  f1_macro  f1_weighted
           CalibratedClassifierCV (raw)    0.6892    0.4186       0.6758
CalibratedClassifierCV (+threshold/gap)    0.5608    0.3681       0.5700
```

## ?? Artefatos publicados (models\_sprint2)

- models_sprint2\README.md
- models_sprint2\classifier.pkl
- models_sprint2\config.json
- models_sprint2\embedding_model_name.txt
- models_sprint2\intent_names.json
- models_sprint2\label_encoder.pkl
- models_sprint2\thresholds.json

## ??? Relat�rios & figuras (reports)

- notebooks\modelos\reports\EXEC_SUMMARY.md
- notebooks\modelos\reports\classification_report.csv
- notebooks\modelos\reports\comparacao_teste_raw_vs_threshold.csv
- notebooks\modelos\reports\f1_por_classe.png
- notebooks\modelos\reports\hf_repo_files.txt
- notebooks\modelos\reports\matriz_confusao_norm.png
- notebooks\modelos\reports\scoreboard_consolidado.csv

## ? Entreg�veis

* Treinamento com embeddings + algoritmo (LR/RF) e CV adaptativa.
* Probabilidades **calibradas** e sele��o �tima de **threshold/gap** por valida��o.
* Export de m�tricas (classification report, matriz de confus�o normalizada, F1 por classe, reliability, t-SNE).
* Publica��o no **Hugging Face** com artefatos (classifier, label encoder, embedder, thresholds).
* Baselines TF-IDF + explicabilidade (n-grams por classe e para 'outros'/'nao\_entendi').

