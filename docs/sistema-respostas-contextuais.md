
# Sistema de Respostas Contextuais � Curadobia

**Vers�o:** 1.1  
**Atualizado em:** 2025-09-11

&emsp;Esta documenta��o descreve a Gera��o de recomenda��es de moda **personalizadas** a partir do **perfil da cliente** (tamanhos/estilos) e do **cat�logo normalizado**, com recupera��o sem�ntica, reranking por compatibilidade e resposta em tom de consultoria (�BIA�). Todo o processo est� dispon�vel no notebook `05-criacao-dataset-instrucoes.ipynb`, dispon�vel no reposit�rio do grupo.


# 1. Fluxo de alto n�vel

-  **Perfil**: JSON com tamanhos, equival�ncias e prefer�ncias.
-  **Cat�logo**: CSV/Excel normalizado para schema �nico (grade e estoque).
-  **Indexa��o**: embeddings dos itens e cria��o de �ndice vetorial.
-  **Busca + Reranking**: similaridade da consulta + ajuste por **tamanho** e **estilo** + guardrails de estoque.
-  **Resposta**: texto humanizado com **motivo da indica��o** e **tamanho sugerido**.
-  **Integra��o**: usado quando a inten��o detectada for `pedir_sugestao_produto` ou `tamanho_modelagem`.


# 2. Artefatos do reposit�rio

**C�digo**

```
/code/context/normalize_catalog.py      # mapeia CSV/Excel do estoque ? schema padronizado
/code/context/build_index.py            # gera embeddings e �ndice (vetores + metadados)
/code/context/responder.py              # recupera��o, reranking e gera��o da resposta
/code/context/make_sample_profile.py    # cria perfil-exemplo (para testes)
/code/fluxos_intencao/chatbot.py        # CLI do bot, integrando NLU + recomenda��es
```

**Notebooks**

```
/code/notebooks/05_sistema_respostas_contextuais.ipynb
```

(Valida end-to-end: cat�logo ? �ndice ? ranking contextual ? m�tricas, gr�ficos e amostras.)

**Dados e sa�das**

```
/data/catalog/catalog_curadobia.csv             # cat�logo bruto (ou Excel)
/data/catalog/catalog_normalized.csv            # cat�logo normalizado
/data/profiles/cliente_exemplo.json             # perfil de exemplo

/code/notebooks/outputs/models/catalog_index/   # �ndice sem�ntico (vectors.npy, items.csv, meta.json)
/code/notebooks/outputs/runs/context_ranking_samples.csv
```

# 3. Esquemas de dados

## 3.1 Perfil (JSON)

```json
{
  "user_id": "demo",
  "tamanho_superior": "M",
  "tamanho_inferior": "38",
  "tamanhos_equivalentes": ["M","38","40"],
  "estilos_preferidos": ["alfaiataria","minimalista"],
  "cores_evitar": ["amarelo"],
  "ocasioes_frequentes": ["jantar","trabalho"],
  "tecidos_evitar": ["poli�ster"]
}
```

## 3.2 Cat�logo normalizado (CSV)

```
id,brand,name,category,color,material,price,sizes,stock_json,description
```

  * `sizes`: `PP;P;M;G` ou `36;38;40`.
  * `stock_json`: `{"P":3,"M":2,"G":0}` (string JSON).
  * `description`: livre (modelagem/caimento/tecido/ocasi�o).


# 4. Execu��o (PowerShell)

> Requisitos: venv ativo e `requirements.txt` instalado.

## 4.1 Perfil de exemplo

```powershell
python code\context\make_sample_profile.py --out data\profiles\cliente_exemplo.json
```

## 4.2 Normaliza��o do cat�logo

```powershell
python code\context\normalize_catalog.py ^
  --src data\catalog\catalog_curadobia.csv ^
  --out data\catalog\catalog_normalized.csv
```

## 4.3 �ndice sem�ntico

```powershell
python code\context\build_index.py ^
  --catalog data\catalog\catalog_normalized.csv ^
  --embedder "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" ^
  --out code\notebooks\outputs\models\catalog_index
```

## 4.4 Resposta contextual (teste) 

```powershell
python code\context\responder.py ^
  --index code\notebooks\outputs\models\catalog_index ^
  --profile data\profiles\cliente_exemplo.json ^
  --query "Quero um vestido midi preto para um jantar." ^
  --k 5 --debug
```

## 4.5 Chatbot (CLI)

```powershell
python code\fluxos_intencao\chatbot.py
```

  * Usa o classificador em `/code/notebooks/outputs/models/intents_calibrated`.
  * Aciona a recomenda��o contextual quando apropriado.


# 5. Ranking e gera��o

  - **Texto indexado do item**: `brand + name + category + color + material + description`.
  - **Similaridade**: cosseno entre embedding da consulta e o vetor do item.
  - **Compatibilidade de tamanho**:
      * 1.0 se `tamanhos_equivalentes` n `sizes` tem estoque (`stock_json[tam] > 0`);
      * 0.5 se o tamanho existe sem informa��o de estoque;
      * 0.0 caso contr�rio.
  - **Prefer�ncias de estilo**:
      * incremento moderado quando termos de `estilos_preferidos` aparecem;
      * penaliza��o leve para `cores_evitar`/`tecidos_evitar`.
  - **Score final**:
    ```
    score_total = 0.7 * similaridade + 0.2 * score_tamanho + 0.1 * score_estilo
    ```
  - **Resposta (voz BIA)**:
      * bullets com pe�a, categoria, cor, material, pre�o;
      * **tamanho sugerido** (derivado da compatibilidade);
      * **porqu�** (ocasi�o/estilo/caimento);
      * oferta de montar look e/ou transferir para humano.


# 6. Evid�ncias (sa�das reais)

**Amostra de ranking (top-3 por consulta)**

```
query: Quero um vestido midi preto para um jantar.
1) Vestido Midi Luna     | score=0.6327 (sim=0.6181, tam=1.00, estilo=0.00)
2) Cal�a Reta Clara      | score=0.4626 (sim=0.3752, tam=1.00, estilo=0.00)
3) Blazer Alfaiataria Ava| score=0.3665 (sim=0.2093, tam=1.00, estilo=0.20)
```

**Resposta gerada (resumo)**

```
Bora achar o look certo pra voc�? Olhei seu perfil e foquei nas op��es que casam com seu tamanho e vibe.

� Curadobia Vestido Midi Luna (vestido, preto, viscose) � R$ 299,90
  porqu�: perfeito para jantar � elegante sem esfor�o.
  tamanhos: P, M, G | eu iria de M
(...)
```

**Grounding**: todos os itens citados est�o em `/code/notebooks/outputs/models/catalog_index/items.csv`.


# 7. Integra��o com NLU/fluxo

  - **Entrada**: texto do usu�rio.
  - **Classificador**: retorna inten��o + confian�a; thresholds/gap aplicados.
  - **Gatilho**: `pedir_sugestao_produto` ou `tamanho_modelagem` ? chama `responder.py`.
  - **Fallback**: sem estoque compat�vel ou confian�a baixa ? encaminhar humano.


# 8. Boas pr�ticas e limites

  -  Regerar �ndice sempre que o cat�logo mudar.
  - N�o prometer disponibilidade sem checar `stock_json`.
  - Registrar consultas e cliques (para futura **avalia��o de hit@k** e aprendizado de prefer�ncias).
  - Expans�o de equival�ncias de tamanho por marca/modelagem conforme hist�rico.


# 9 Pr�ximos passos

  - `hit@k` com conjunto de consultas rotuladas.
  - Regras de estilo mais ricas (sin�nimos/embedding de atributos).
  - Gera��o por LLM com **adapter LoRA** reaproveitando o mesmo contexto (mantendo os guardrails).


