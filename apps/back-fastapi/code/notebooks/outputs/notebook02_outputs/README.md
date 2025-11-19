# Curadobia — Classificador de Intenções (v1)

Artefatos de modelo treinados no notebook `04_treinamento_classificacao_intencoes.ipynb`.

- **Embedder**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Algoritmo**: `LogisticRegression`
- **Arquivos aqui**:
  - `classifier.pkl` — classificador final
  - `label_encoder.pkl` — encoder das classes
  - `config.json` — metadados de treino
  - `embedding_model_name.txt` — nome do embedder utilizado
  - `README.md` — este guia

## Métricas (teste)
- Accuracy: **0.6386**
- F1-macro: **0.4399**
- F1-weighted: **0.6582**
- Nº de classes: **12**

## Classes
`agradecimento`, `como_comprar`, `despedida`, `disponibilidade_estoque`,
`erros_plataforma`, `formas_pagamento`, `frete_prazo`, `nao_entendi`,
`pedir_sugestao_produto`, `saudacao`, `tamanho_modelagem`, `troca_devolucao_politica`.

---

## Como usar

### A) Via CLI (demo local)

#### Windows PowerShell (um único bloco)
```powershell
# 1) Ativar venv (se já existir)
& .\.venv\Scripts\Activate.ps1

# 2) Instalar dependências do projeto (raiz do repo)
pip install -r .\requirements.txt

# 3) Rodar verificação do YAML dos fluxos (opcional, mas recomendado)
python .\code\resources\validate_fluxos.py --schema .\code\resources\fluxos.schema.json --yaml .\code\resources\fluxos.yaml

# 4) Exportar a tabela de transições (gera docs\tabela_transicoes.csv)
python .\code\resources\export_transicoes.py --yaml .\code\resources\fluxos.yaml --out .\docs\tabela_transicoes.csv

# 5) Executar a demo de chat (digite 'sair' para encerrar)
python -m code.fluxos_intencao.cli_demo --yaml .\code\resources\fluxos.yaml
