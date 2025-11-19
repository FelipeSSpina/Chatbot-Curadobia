
# An�lise Sem�ntica Avan�ada � Clusters de Perguntas

**Vers�o:** 1.0  
**Atualizado em:** 2025-09-11  

&emsp;Esta documenta��o descreve o Agrupamento sem�ntico de mensagens de clientes para descobrir **temas recorrentes**, apoiar a **taxonomia de inten��es**, priorizar conte�do e sugerir **regras**/respostas. Todo esse processo foi realizado no notebook `06_analise_semantica_active_learning.ipynb`, dispon�vel no reposit�rio do grupo Curadobot.


# 1. Objetivo

- Reunir mensagens similares (�qual � o tamanho?�, �tem no meu n�?�, �qual o prazo?�) em **clusters interpret�veis**.  
- Oferecer **resumos** por cluster (TF-IDF) e **amostras** representativas para revis�o r�pida.  
- Retroalimentar: cria��o/ajuste de inten��es, regras de pr�-rotulagem e prioriza��o de treinamentos.


# 2. Artefatos do reposit�rio

**Notebook**
```

/code/notebooks/06\_analise\_semantica.ipynb

```
(Executa a pipeline: leitura ? embeddings ? clusteriza��o ? TF-IDF ? exporta��o.)

**Entradas & sa�das**
```

/code/notebooks/dataset/dataset\_unificado.csv       # fonte (mensagens/mensagem\_clean)
/code/notebooks/outputs/runs/clusters\_questions.csv # mensagem + cluster + score
/code/notebooks/outputs/runs/clusters\_summary.json  # algoritmo, k (se KMeans), distribui��o, exemplos
/code/notebooks/outputs/runs/clusters\_top6\_samples.csv # amostras por cluster (curadoria)

```

# 3. Pipeline de clusteriza��o

1. **Sele��o do texto**: `mensagem_clean` (fallback para `mensagem`).  
2. **Embedding**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (mesmo encoder do NLU).  
3. **Clusteriza��o**:
   - Preferencial: **HDBSCAN** (descobre k automaticamente; robusto a ru�do).  
   - Fallback: **KMeans** (quando compiladores nativos n�o est�o dispon�veis no host).
4. **Rotulagem leve**:
   - `TF-IDF` por cluster para termos representativos (12 principais).  
   - Amostras **top-k** por proximidade ao centr�ide (ou probabilidade, se HDBSCAN).
5. **Exporta��o**:
   - `clusters_questions.csv`: `texto, cluster, score, origem, data, remetente�`  
   - `clusters_summary.json`: `{"alg":"kmeans","k":14,"sizes":{...}, "samples":{cluster:[�]}}`


# 4. Execu��o (no notebook)

- As c�lulas carregam `dataset_unificado.csv`, geram embeddings e rodam **HDBSCAN** se dispon�vel; caso contr�rio, ativam o **KMeans**.  
- O script emite **distribui��o de clusters** e salva as amostras/termos principais.

**Exemplo real de distribui��o (KMeans, k=14)**
```

{13:1267, 3:859, 10:426, 9:418, 11:408, 5:399, 6:386, 2:381, 1:354, 0:302, 8:300, 7:195, 12:188, 4:101}

```

**Top termos (amostras reais, TF-IDF)**

Cluster 13  
```

saia, tem, ola, voce, essa, gente, esse, joia, ta, comprar, fazer, ser

```

Cluster 10  
```

curadobia, num, estamos, ola, contato, aqui, ...

```

Cluster 3  
```

nan  (muitos registros ruidosos/curtos; candidatos a filtro)

```


# 5. Interpreta��o e uso pr�tico

- **Rotulagem assistida**: cada cluster gera um lote coeso para revis�o; reduz custo de anota��o.  
- **Sementes de regras**: termos de TF-IDF alimentam dicion�rios/regex iniciais (ex.: �prazo�, �entrega�, �tamanho�, �troca�).  
- **Apoio ao NLU**: clusters dominantes indicam **inten��es** sub-representadas; direcionam o rebalan�o/curadoria do conjunto de treino.  
- **Qualidade de dados**: clusters �vazios/s� stopwords� revelam mensagens inserv�veis (ex.: rea��es/ru�do), guiando limpeza.


# 6. Evid�ncias geradas

- `clusters_questions.csv` � arquivo amplo para explora��o (filtro por `cluster` e `origem`).  
- `clusters_summary.json` � cont�m:
  - algoritmo utilizado;
  - `k` (se KMeans);
  - `sizes` por cluster;
  - **amostras** representativas.
- `clusters_top6_samples.csv` � recorte curto por cluster para inspe��o manual r�pida.


# 7. Integra��o com o restante do sistema

- **NLU**: clusters ? novas **inten��es** (ou **subinten��es**) para o classificador; servir de base para **oversampling**.  
- **Respostas**: clusters de �d�vidas recorrentes� orientam **templates** e **FAQ** com grounding no cat�logo.  
- **Prioridade de backlog**: clusters grandes e com baixa cobertura atual viram **epics** para produto/conte�do.


# 8. Boas pr�ticas e observa��es

- Se `hdbscan` n�o compilar no Windows, o notebook usa **KMeans** automaticamente (mensagem clara no output).  
- Manter uma **lista de stopwords PT** e limpeza (`<num>`, `<user>`, emojis) para reduzir ru�do.  
- Guardar **vers�es** das sa�das em `/code/notebooks/outputs/runs/` com data/hora para auditoria.


# 9. Pr�ximos passos

- Etiquetar alguns clusters manualmente e medir **pureza/coer�ncia**.  
- Implementar m�trica de **cohesion/separation** (silhouette, Davies-Bouldin) no relat�rio.  
- Fechar o ciclo: clusters ? **regras** ? **pr�-rotulagem** ? **re-treino** do NLU ? queda de `nao_entendi`.


