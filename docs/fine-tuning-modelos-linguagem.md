# Fine-Tuning � Curadobia

**Vers�o:** 1.1

**Atualizado em:** 2025-09-11

&emsp;Esta documenta��o descreve o desenvolvimento e integra��o de BIBI, o chatbot consultor de moda da Curadobia, capaz de gerar recomenda��es personalizadas de roupas e acess�rios. BIBI combina informa��es do **perfil da cliente** (tamanho, estilo, prefer�ncias) e do **cat�logo de produtos dispon�veis** (estoque, cores, materiais) com modelos de linguagem treinados via fine-tuning para fornecer respostas humanizadas, confi�veis e orientadas � consultoria de moda.

&emsp;O notebook `07_finetuning_llm_consultora.ipynb` detalha o processo de fine-tuning supervisionado do modelo base utilizando LoRA, definindo a personalidade, tom e estilo de respostas de BIBI.


---

# 1. Vis�o Geral

## 1.1 Objetivo

- Transformar consultas de clientes em **recomenda��es de pe�as** coerentes com seu **tamanho** e suas **prefer�ncias de estilo**.
- Transformar mensagens livres (Instagram/WhatsApp/FAQ) em **inten��es estruturadas** como `saudacao`, `como_comprar`, `tamanho_modelagem`, `frete_prazo`, etc. 
- Garantir **grounding** nas informa��es do **cat�logo** (itens, tamanhos e estoque).
- Produzir respostas **humanizadas**, no tom da consultora BIA, com **justificativas** (porqu�/como usar) e **sugest�o de tamanho**.
- Treinar um modelo de linguagem para que possa gerar respostas de forma aut�noma e flex�vel, al�m de templates fixos.

## 1.2 Abordagem

- encoder sem�ntico multil�ngue (Sentence-Transformers) + classificador linear calibrado. 

## 1.3 Resultado

- modelo de inten��es **calibrado**, com **F1 macro � 0.815** no conjunto de teste e mecanismos de **absten��o segura** por confian�a/�gap top-2�.


# 2. Fine-Tuning de LLM (Notebook 07_finetuning_llm_consultora)

## 2.1 Prepara��o dos dados

- Coleta de mensagens de clientes a partir de arquivos CSV de inten��es rotuladas e backups do hist�rico de mensagens.
- Limpeza, deduplica��o e filtragem de pares prompt (descarta respostas vazias ou placeholders).

&emsp; Exemplo de pares coletados:

```bash
Pergunta: "Quais as formas de pagamento?"
Resposta: "Voc� pode pagar via cart�o, PIX ou boleto banc�rio."
```

## 2.2 Formata��o para Supervised Fine-Tuning (SFT)

&emsp;Defini��o de system prompt da BIBI: tom acolhedor, direto, elegante, uso pontual de emojis, respostas curtas e confi�veis.

&emsp;Cada exemplo serializado em JSONL:

```bash
<S>[SYSTEM] SYSTEM_PROMPT [/SYSTEM]
[USER] pergunta [/USER]
[ASSISTANT] resposta [/ASSISTANT]</S>
```

&emsp;Dataset final salvo em sft_train.jsonl.

## 2.3 Sele��o do modelo base

&emsp;Modelos dispon�veis:

- TinyLlama-1.1B-Chat (padr�o, CPU-friendly)

- Mistral-7B-Instruct (opcional, requer GPU ou >28GB RAM)

- Configura��o autom�tica do pad_token e carregamento no device dispon�vel (cuda ou cpu)

- Registro do modelo base em LLM_DIR/base_model_name.txt.

## 2.4 Tokeniza��o e collator

- Tokeniza��o via AutoTokenizer.

- Collator prepara lotes (input_ids e labels) para treino.

## 2.5 Aplica��o de LoRA e treino

- LoRA adapters aplicados para reduzir custo de mem�ria e acelerar treinamento.

- Treino configurado para 10 �pocas com batch size reduzido.

- Tentativa inicial com Trainer Hugging Face; fallback para loop manual CPU-friendly caso accelerate n�o esteja dispon�vel.

- Otimizador: AdamW, gradiente clipado, scheduler linear opcional.

## 2.6 Infer�ncia

- Modelo base + adapter carregados com PeftModel.
- Fun��o generate_reply() gera respostas condicionadas ao system prompt, mantendo persona e restri��es de cat�logo.

&emsp;Exemplo de sa�da:


```bash
Usu�ria: "Quero sugest�es de blusa para trabalho; uso M e curto tons neutros."

BIBI   : "Olhei seu perfil e selecionei blusas que combinam com seu tamanho e estilo minimalista..."

```

# 3. Arquitetura da solu��o (vis�o geral)

1. **Detec��o de inten��o**: usa o classificador de inten��es (encoder) previamente treinado. Quando a inten��o � `pedir_sugestao_produto` ou `tamanho_modelagem`, aciona-se o sistema contextual.
2. **Perfil da cliente**: leitura de prefer�ncias e tamanhos a partir de um JSON (tamanho superior/inferior, tamanhos equivalentes, estilos preferidos, restri��es).
3. **Normaliza��o do cat�logo**: planilhas/CSV exportados do estoque s�o mapeados para um **schema �nico**.
4. **Indexa��o sem�ntica**: cria��o de embeddings com `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` e armazenamento de vetores + metadados.
5. **Recupera��o + reranking**: c�lculo de similaridade da consulta com os itens; ajuste por **compatibilidade de tamanho/estoque** e **prefer�ncias de estilo**.
6. **Gera��o da resposta**: template textual em tom de consultoria, citando pe�a, categoria, cor, material, pre�o, recomenda��o de tamanho e justificativa.
7. **Guardrails**: nunca recomendar itens sem estoque compat�vel; ofertar transfer�ncia para humano em baixa confian�a ou aus�ncia de compatibilidade.


# 4. Artefatos do reposit�rio

## 4.1 C�digo

```

/code/context/normalize\_catalog.py     # normaliza CSV/Excel do estoque para schema padronizado
/code/context/build\_index.py           # gera embeddings do cat�logo e salva �ndice sem�ntico
/code/context/responder.py             # recupera��o + reranking + resposta templated (voz BIA)
/code/context/make\_sample\_profile.py   # gera um perfil de cliente de exemplo (para testes)

```

## 4.2 Dados (entrada/sa�da)

```

/data/catalog/catalog\_curadobia.csv          # cat�logo bruto (CSV/Excel exportado)
/data/catalog/catalog\_normalized.csv         # cat�logo normalizado (sa�da da normaliza��o)
/data/profiles/cliente\_exemplo.json          # perfil de cliente (exemplo)
/models/catalog\_index/{vectors.npy,items.csv,meta.json}   # �ndice sem�ntico do cat�logo

```


# 5. Esquemas de dados

## 5.1 Perfil da cliente (JSON)

```json
{
  "user_id": "demo",
  "tamanho_superior": "M",
  "tamanho_inferior": "38",
  "tamanhos_equivalentes": ["M", "38", "40"],
  "estilos_preferidos": ["alfaiataria", "minimalista"],
  "cores_evitar": ["amarelo"],
  "ocasioes_frequentes": ["jantar", "trabalho"],
  "tecidos_evitar": ["poli�ster"]
}
```

## 5.2 Cat�logo normalizado (CSV)

Colunas esperadas em `/data/catalog/catalog_normalized.csv`:

```
id, brand, name, category, color, material, price, sizes, stock_json, description
```

* `sizes`: lista separada por `;` (ex.: `PP;P;M;G` ou `36;38;40`).
* `stock_json`: JSON em string (ex.: `{"P":3,"M":2,"G":0}`).
* `description`: livre (ex.: modelagem/caimento).


# 6. Execu��o (passo a passo)

> Pr�-requisitos: ambiente virtual Python ativo e depend�ncias instaladas conforme `requirements.txt`.
> Os comandos abaixo assumem terminal PowerShell aberto na raiz do reposit�rio.

## 6.1 Gerar perfil de exemplo

```powershell
python code\context\make_sample_profile.py --out data\profiles\cliente_exemplo.json
```

## 6.2 Normalizar cat�logo

```powershell
python code\context\normalize_catalog.py --src "data\catalog\catalog_curadobia.csv" --out "data\catalog\catalog_normalized.csv"
```

> Observa��o: para arquivos `.xlsx`, � necess�rio `openpyxl` instalado.

## 6.3 Construir �ndice sem�ntico

```powershell
python code\context\build_index.py --catalog "data\catalog\catalog_normalized.csv" --embedder "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" --out "models\catalog_index"
```

## 6.4 Gerar resposta contextual (teste)

```powershell
python code\context\responder.py --index "models\catalog_index" --profile "data\profiles\cliente_exemplo.json" --query "Quero um vestido midi preto para um jantar." --k 5 --debug
```

# 7. L�gica de ranking e gera��o

- **Texto de cada item para embedding**: concatena��o de `brand`, `name`, `category`, `color`, `material`, `description`.

- **Similaridade sem�ntica**: cosseno entre embedding da consulta e embeddings dos itens.

- **Compatibilidade de tamanho/estoque**: pontua��o de 1.0 se qualquer tamanho do perfil (incluindo equivalentes) estiver dispon�vel com estoque > 0; 0.5 se existir na grade com estoque desconhecido; 0.0 caso contr�rio.

- **Prefer�ncias de estilo**: incremento moderado quando termos preferidos aparecem em nome/descri��o; decr�scimo se cor/tecido est�o na lista de evitar.

- **Score final (pondera��es)**:

  ```
  score_total = 0.7 * similaridade + 0.2 * score_tamanho + 0.1 * score_estilo
  ```

- **Template de resposta**: lista em bullet points contendo pe�a, categoria, cor, material, pre�o, motiva��o/ocasi�o e **sugest�o de tamanho**.


# 8. Evid�ncia de execu��o

## 8.1 Comando

```powershell
python code\context\responder.py --index "models\catalog_index" --profile "data\profiles\cliente_exemplo.json" --query "Quero um vestido midi preto para um jantar." --k 5 --debug
```

## 8.2 Sa�da (real)

```
[DEBUG] Top candidatos:
  -> Curadobia Vestido Midi Luna | score=0.633 (sim=0.618, size=1.00, style=0.00)
  -> Curadobia Cal�a Reta Clara | score=0.463 (sim=0.375, size=1.00, style=0.00)
  -> Curadobia Blazer Alfaiataria Ava | score=0.367 (sim=0.209, size=1.00, style=0.20)

Bora achar o look certo pra voc�? Olhei seu perfil e foquei nas op��es que casam com seu tamanho e vibe.

� **Curadobia Vestido Midi Luna** (vestido, preto, viscose) � R$ 299.9
  porqu�: perfeito para jantar � elegante sem esfor�o.
  tamanhos: P, M, G | **eu iria de M**

� **Curadobia Cal�a Reta Clara** (cal�a, off-white, algod�o) � R$ 249.9
  porqu�: combina f�cil com sand�lia ou mule minimalista.
  tamanhos: 36, 38, 40 | **eu iria de 38**

� **Curadobia Blazer Alfaiataria Ava** (blazer, bege, linho) � R$ 399.9
  porqu�: o linho d� caimento fresco e sofisticado.
  tamanhos: PP, P, M | **eu iria de M**

Se necess�rio, ajustar `tamanhos_equivalentes` no perfil ou revisar `sizes`/`stock_json` no cat�logo para obter maior compatibilidade.
```


# 9. Integra��o com o classificador de inten��es

- **Gatilhos de uso**: inten��es `pedir_sugestao_produto` e `tamanho_modelagem`.
- **Condi��es de seguran�a**: aplicar limiares de confian�a no classificador; quando abaixo do limite, encaminhar para humano antes de consultar o cat�logo.
- **Consumo como m�dulo**: o conte�do de `responder.py` pode ser refatorado em fun��es e exposto via servi�o, mantendo o mesmo �ndice e esquema de dados.


# 10. Boas pr�ticas e guardrails

- **Calibra��o de probabilidades** para evitar overconfidence.
- **Threshold + gap top-2** para reduzir erros de rota.
- **Auditoria** cont�nua de confus�es frequentes (top_confusoes em notebooks).
- **Atualiza��es:** re-treinar com dados novos (drift), preservando valida��o consistente
- **Grounding**: toda recomenda��o deve ser derivada do **cat�logo normalizado**; evitar assumir tamanhos/estoque que n�o constem do `stock_json`.
- **Privacidade**: perfil de cliente sem PII sens�vel; armazenar tamanhos/estilos com consentimento e possibilidade de remo��o.
- **Falas respons�veis**: nunca afirmar disponibilidade sem checar `stock_json`; oferecer alternativas ou suporte humano quando n�o houver compatibilidade.

# 11. Limita��es e pr�ximos passos

- **Convers�o de PDF de estoque**: preferir exporta��o para Excel/CSV para reduzir perda de dados.
- **Equival�ncia de tamanhos por marca/modelagem**: criar tabela de mapeamento mais robusta quando houver inconsist�ncias.
- **Avalia��o offline**: adicionar script de `hit@k` e verifica��o de groundedness (ex.: `/code/context/eval_hitk.py`) com conjunto de consultas rotuladas.
- **Gera��o LLM**: quando o adapter LoRA estiver dispon�vel, substituir o template por gera��o condicionada ao mesmo contexto (mantendo todos os guardrails).



