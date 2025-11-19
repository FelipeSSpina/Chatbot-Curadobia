# 4. Fine-tuning de Embeddings — Sprint 4

## Objetivo
Especializar o encoder de sentenças para **vocabulário de moda** e melhorar a recuperação no catálogo (consultas como “jaqueta jeans”, “vestido midi preto”, “blazer linho bege”). A avaliação compara **baseline vs. modelo ajustado** com métricas objetivas. Este documento inclui **artefatos, comandos reprodutíveis, métricas geradas pelos scripts e integração no app**.

---

## Novidades desta sprint (TL;DR)
- **Dados limpos em UTF-8** (acentos normalizados) e **pares/consultas ampliados** com negativos mais desafiadores.
- Treino: suporte automático a **TripletLoss** quando existir coluna `negative`; remoção do `drop_last`; **batch-size adaptativo com retry anti-OOM**; log de execução em `train_log.json`.
- Avaliação: flags `--sample_queries` e `--filter_category`, novas métricas **Recall@K** e **nDCG@K**, e normalização única de vetores.
- Runtime: índice carregado com **vetores normalizados** (ou normalização em memória), reaproveitados em todo o fluxo; função `runtime_index_info()` para telemetria.

---

## Artefatos gerados (versionados)
- Adapter / modelo ajustado: `code/notebooks/outputs/models/fashion_embeddings/`
- Índice (tuned) do catálogo: `code/notebooks/outputs/models/fashion_embeddings/catalog_index/`  
  (contém `items.csv`, `vectors.npy`, `meta.json`)
- Dados de treino/avaliação:
  - `data/embeddings/fashion_pairs.csv`  (**UTF-8;** colunas `query,positive[,negative]`)
  - `data/embeddings/eval_queries.csv`   (consultas + `must_have`)
  - `data/embeddings/queries_indices.json` (gerado via script)
- Métricas / logs:
  - `outputs/runs/eval_ft_details.json` (detalhes por consulta; ver comandos)
  - `code/notebooks/outputs/models/fashion_embeddings/train_log.json` (hiperparâmetros/execução)

---

## Pipeline (visão geral)
1. Treinar adapter contrastivo a partir de `fashion_pairs.csv` (MultipleNegatives ou TripletLoss).  
2. Recriar o **índice do catálogo** usando o encoder ajustado.  
3. Avaliar baseline vs tuned com **Precision@K, Recall@K, MRR e nDCG@K**.  
4. Integrar o encoder ajustado no chatbot via `BIA_EMBEDDER_DIR` (ou auto-detecção).

---

## Scripts & Notebooks usados (citados explicitamente)
- Treino do encoder: `code/embeddings/train_fashion_embeddings.py`
- Construção de índice: `code/context/build_index.py`
- Avaliação: `code/embeddings/evaluate_retrieval.py`
- Catálogo normalizado (preparo): `code/notebooks/05_sistema_respostas_contextuais.ipynb`
- Classificação de intenção (referência): `code/notebooks/04_treinamento_classificacao_intencoes.ipynb`

---

## Dataset

### 1) Pares para treino (Triplet opcional)
Arquivo: `data/embeddings/fashion_pairs.csv`  
Colunas aceitas: `query,positive[,negative]`  
- Se **existe** `negative` → usamos **TripletLoss** (anchor/query, positive, negative).  
- Caso **não exista** → usamos **MultipleNegativesRankingLoss** com pares (query, positive).

Exemplos (CSV):
- `jaqueta jeans,jaqueta jeans clássica,jaqueta de couro`  
- `vestido midi preto,vestido midi preto liso,vestido curto estampado`  
- `calça wide leg,calça jeans wide leg,calça skinny`  
- `blazer linho bege,blazer de linho bege,blazer sintético preto`

> Observação: o CSV foi normalizado para UTF-8/NFKC e **termina com newline** (evita warnings em diffs).

### 2) Consultas para avaliação
- **Opção A (por índices)**: `data/embeddings/queries_indices.json`  
  Formato: `[{"query":"jaqueta jeans","relevant_indices":[12,45,...]}, ...]`
- **Opção B (por substring)**: `data/embeddings/eval_queries.csv`  
  Colunas: `query,must_have` (validado em `brand|name|category`)  
  Flags de avaliação permitem **amostrar** e **filtrar** por categoria.

---

## Como rodar (reprodutível)

### 1) Treinar o encoder (adapter)
    python -m code.embeddings.train_fashion_embeddings \
      --base "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" \
      --pairs "data/embeddings/fashion_pairs.csv" \
      --out   "code/notebooks/outputs/models/fashion_embeddings" \
      --epochs 3 --batch_size 32
    # → Gera: .../train_log.json (hiperparâmetros, batch efetivo, duração)

### 2) Recriar o índice do catálogo com o encoder ajustado
Windows PowerShell
    $env:BIA_EMBEDDER_DIR = "code/notebooks/outputs/models/fashion_embeddings"
    python -m code.context.build_index `
      --catalog "data/catalog/catalog_normalized.csv" `
      --out "code/notebooks/outputs/models/fashion_embeddings/catalog_index" `
      --embedder "$env:BIA_EMBEDDER_DIR"

Linux/macOS
    BIA_EMBEDDER_DIR="code/notebooks/outputs/models/fashion_embeddings" \
    python -m code.context.build_index \
      --catalog data/catalog/catalog_normalized.csv \
      --out     code/notebooks/outputs/models/fashion_embeddings/catalog_index

### 3) Gerar `queries_indices.json` (opcional, recomendado)
    python -m code.embeddings.make_queries_indices \
      --catalog  "data/catalog/catalog_normalized.csv" \
      --eval_csv "data/embeddings/eval_queries.csv" \
      --out_json "data/embeddings/queries_indices.json"

### 4) Avaliar (duas formas)

**A) Baseline vs tuned (usando índices prontos)**
    mkdir -p outputs/runs
    python -m code.embeddings.evaluate_retrieval \
      --index_baseline "models/catalog_index" \
      --index_tuned    "code/notebooks/outputs/models/fashion_embeddings/catalog_index" \
      --queries_csv    "data/embeddings/eval_queries.csv" \
      --baseline_model "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" \
      --tuned_model    "code/notebooks/outputs/models/fashion_embeddings" \
      --k "1,5,10" \
      --sample_queries 200 \
      --filter_category "" \
      --out_details "outputs/runs/eval_ft_details.json"

**B) Avaliar um único modelo diretamente do catálogo (sem índices)**
    # baseline
    python -m code.embeddings.evaluate_retrieval \
      --catalog "data/catalog/catalog_normalized.csv" \
      --queries_json "data/embeddings/queries_indices.json" \
      --embedder "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" \
      --k 5

    # tuned
    python -m code.embeddings.evaluate_retrieval \
      --catalog "data/catalog/catalog_normalized.csv" \
      --queries_json "data/embeddings/queries_indices.json" \
      --embedder "code/notebooks/outputs/models/fashion_embeddings" \
      --k 5

**Saída**: JSON com `precision@K`, `recall@K`, `ndcg@K`, `mrr` e `n_queries`.  
Se `--out_details` for informado, salva também os top-idx por consulta para auditoria.

---

## Métricas & leitura dos resultados
- **Precision@K**: entre os K itens retornados, quantos são relevantes.  
- **Recall@K**: entre todos os relevantes, quantos apareceram nos K itens.  
- **MRR**: média do inverso da posição do 1º acerto (sensível ao topo).  
- **nDCG@K**: ganho cumulativo normalizado; diferencia posições e múltiplos relevantes.

Exemplo de saída (resumo, ilustrativo):
    {
      "summary": [
        {"system": "baseline", "n_queries": 200, "precision@1": 0.26, "precision@5": 0.42, "recall@5": 0.31, "ndcg@5": 0.37, "mrr": 0.41},
        {"system": "tuned",    "n_queries": 200, "precision@1": 0.30, "precision@5": 0.47, "recall@5": 0.36, "ndcg@5": 0.42, "mrr": 0.45}
      ]
    }

> **Importante**: os valores acima são **ilustrativos**. Consulte seus resultados reais no console e em `outputs/runs/eval_ft_details.json`.

---

## Integração no chatbot
`code/fluxos_intencao/chatbot.py`:
- Prefere o encoder FT se a env `BIA_EMBEDDER_DIR` existir (ou auto-detecta `code/notebooks/outputs/models/fashion_embeddings`).
- Carrega o índice **tuned** (`.../catalog_index`) quando disponível; caso contrário, usa o baseline.
- **Normaliza vetores** uma vez e **reaproveita-os** em ranking e `_suggest_similar_terms`.
- Expõe `runtime_index_info()` para telemetria (exemplo):

    {
      "embedder": "code/notebooks/outputs/models/fashion_embeddings",
      "index_dir": "code/notebooks/outputs/models/fashion_embeddings/catalog_index",
      "items": 1234,
      "vectors_normed": true
    }

Evidência de runtime (prints):
    [chatbot] embedder: code/notebooks/outputs/models/fashion_embeddings
    [chatbot] usando índice: .../fashion_embeddings/catalog_index

---

## Controle de versão (pastas relevantes)
    code/
      embeddings/ → train_fashion_embeddings.py, evaluate_retrieval.py, make_queries_indices.py
      context/    → build_index.py
    code/notebooks/outputs/models/
      fashion_embeddings/
      fashion_embeddings/catalog_index/
    data/embeddings/ → fashion_pairs.csv, eval_queries.csv, queries_indices.json
    outputs/runs/    → eval_ft_details.json

---

## Limitações
- O ganho depende da **diversidade** de pares e do tamanho do catálogo.  
- A avaliação por substring (`must_have`) é heurística; a ideal é por **IDs relevantes** anotados.  
- **TripletLoss** requer negativos representativos; negativos fáceis podem não pressionar o modelo.

---

## Próximos passos
1. Ampliar `fashion_pairs.csv` com termos de moda (e.g., *trucker*, *stone wash*, *cropped*, *evasê*, *wide-leg*, *reta/solta/slim/oversized*) e **negativos confundidores** por categoria.  
2. Enriquecer `description`/atributos do catálogo; usar **BM25 + Embedding** (reranking híbrido) para consultas raras.  
3. Rodar 3–5 épocas com early-stopping simples; ajustar batch conforme GPU.  
4. Quebrar métricas por **categoria** e **tipo de consulta** (ex.: “cor + peça”, “estilo + peça”).  
5. Telemetria de clique/conversão no app para A/B do encoder ajustado.  
6. Automatizar *build-index* em CI/CD após novo treino.
