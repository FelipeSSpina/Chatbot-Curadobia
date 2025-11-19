# Fallbacks Inteligentes — Sprint 4

## Sumário
1. Visão geral  
2. Como funciona  
3. Fluxos e algoritmos  
4. Interfaces e assinaturas  
5. Exemplos (comandos/prints)  
6. Métricas e avaliação  
7. Como reproduzir  
8. Decisões de projeto  
9. Limitações  
10. Próximos passos

---

## 1. Visão geral
Unificamos o mecanismo de **fallbacks** (baixa confiança, catálogo vazio/irrelevante e erros de I/O) e o alinhamos ao **gating** global do pipeline.  
Código relevante:  
- Heurísticas e textos: `code/fallbacks/manager.py`  
- Respostas + fallback de catálogo: `code/fluxos_intencao/chatbot.py`  
- Integração FastAPI: `code/webapi/app.py`  
- Integração Gradio: `code/fluxos_intencao/chat_web.py`  

Ponto crítico desta sprint: o classificador às vezes emite `pedir_sugestao_produto`. Padronizamos com `_normalize_intent_label(...) → "pedido_sugestao"` para o bloco de recomendação/fallback disparar corretamente.

---

## 2. Como funciona
1) Após `classify_intent`, normalizamos a label (ex.: `pedir_sugestao_produto` → `pedido_sugestao`).  
2) Aplicamos **gating** configurável (padrão: `MIN_CONF=0.50`, `MIN_GAP=0.20`).  
3) Se cair no gating, disparamos **clarificação** (ambiguidade) ou **fallback de baixa confiança**.  
4) Em **recomendação de produtos**, calculamos `score_total` e, se não houver itens bons, usamos **fallback de catálogo** com alternativas textuais.  
5) Falhas de API/timeout usam mensagens neutras com retry/opção de ajuda humana.  
6) Tudo é registrado via `SessionManager.log_event(..., role="meta")` **e** eventos padronizados (`FALLBACK.build_event(...)`) para telemetria.

---

## 3. Fluxos e algoritmos
**Predição → normalizar label → (gating por conf/gap)**  
- OK → segue fluxo normal  
- NOK → `clarify()` / `FALLBACK.build_reply_low_confidence()`

**Consulta catálogo → `rank_catalog(query, profile_json)`**  
- `score_total ≥ min_score` → recomendações  
- `score_total < min_score` → `FALLBACK.build_reply_no_products(query, alternativas, items_meta, profile)`

**I/O/API error/timeout**  
- `FALLBACK.build_reply_api_issue()` / `FALLBACK.build_reply_timeout()`

> Observação: `_normalize_intent_label` mapeia `pedido_sugestao_produto` para `pedido_sugestao`, garantindo que o bloco de recomendação (e seu fallback) execute sempre que for um pedido de sugestão.

**Fallback de catálogo**:  
- Sinaliza ausência/baixa relevância com `FALLBACK.need_product_fallback(...)`.  
- Usa o texto obrigatório: **“Não tenho exatamente isso, mas veja estas opções similares...”**.  
- `alternatives` vêm dos itens mais próximos por embedding (mesmo com similaridade baixa), formatados como “Marca Nome — Categoria”.  
- Aproveita metadados (`items_meta`) e **perfil** para contextualizar (“baseado no seu perfil: tam M, cor preto...”).

---

## 4. Interfaces e assinaturas

### `code/fallbacks/manager.py`
- **Thresholds alinhados ao global** (com ENV):
  - `FALLBACK_MIN_CONF` e `FALLBACK_MIN_GAP` (fallback para `AMB_MIN_CONF`/`AMB_MIN_GAP`; default 0.50/0.20)
- **Inspeção**:
  - `get_thresholds() -> Dict[str, float]`
- **Gating de confiança**:
  - `need_low_confidence(*, confidence: float, gap_top2: float) -> bool`
- **Catálogo**:
  - `need_product_fallback(scored_candidates: Sequence[Mapping], *, min_score: float=0.35, min_count: int=1) -> bool`
  - `build_reply_no_products(query: str|None=None, alternatives: list[str]|None=None, *, items_meta: Sequence[Mapping]|None=None, profile: Mapping|None=None, state: MutableMapping|None=None, seed: int|None=None) -> str`
- **Baixa confiança**:
  - `build_reply_low_confidence(top_intents: Sequence[tuple[str,float]]|None, *, state: MutableMapping|None=None, seed: int|None=None) -> str`
- **Erros/tempo**:
  - `need_api_retry(status_code: int|None, *, retriable=(408,429,500,502,503,504)) -> bool`
  - `build_reply_api_issue() -> str`
  - `build_reply_timeout() -> str`
- **Telemetria**:
  - `build_event(*, reason: str, intent: str, confidence: float, gap: float, extra: Mapping|None=None) -> Dict[str, Any]`  
    (inclui `ts` e `thresholds` atuais)
  - `record_event(session, state, kind, reason, payload=None) -> None` (azuleja com `SessionManager.log_event` quando disponível)

### `code/fluxos_intencao/chatbot.py`
- `_normalize_intent_label(label) -> str`  
- `rank_catalog(query, k=5, profile_json=None) -> DataFrame`  
- `generate_response(intent, user_text, meta=None, profile_json=None) -> str`  
  - Para `intent ∈ {"tamanho_modelagem","pedido_sugestao"}`, se `need_product_fallback(...)` for `True` → chama `build_reply_no_products(...)`.

### Integrações (`app.py` / `chat_web.py`)
- Ao disparar clarificação/fallback, os fluxos adicionam eventos padronizados em `state.slots["fallback_events"]` via `FALLBACK.build_event(...)`.  
- Quando há clarificação, persistimos `state.slots["clarify_count"]` e `state.slots["clarify_last_ts"]` para auditoria.

---

## 5. Exemplos (comandos/prints)

**A) Baixa confiança / gap pequeno**  
Entrada: “quero uma coisa legal para sair” (vaga).  
Saída típica:  
> “Fiquei em dúvida sobre o tema. Posso seguir por *pedido_sugestao* ou *frete_prazo*?”

**B) Fallback de catálogo (caso do barema)**  
Entrada: “quero um vestido vitoriano lilás de 1890”.  
Resposta (exemplo):  
> **Não tenho exatamente isso para “vestido vitoriano lilás de 1890”, mas veja estas opções similares...**  
> Ainda não achei uma boa combinação *(baseado no seu perfil: tam M, cor preto)*. Quer ver opções próximas como **vintage, midi**?  
> - Marca A Vestido X — vintage  
> - Marca B Vestido Y — midi  
>  
> Se quiser, eu já refino por tamanho, modelo ou preço.

**C) Erro/timeout**  
- 502/503/504 → “Uuups, meu acesso aos estoques deu uma travadinha...”  
- Timeout → “Demorou mais que o normal... Quer que eu continue buscando aqui ou prefere que eu peça pro time te chamar?”

---

## 6. Métricas e avaliação
- Taxa de fallbacks por 100 conversas (baixa confiança; catálogo).  
- Recuperação pós-fallback (% de sessões que seguem sem humano).  
- Tempo até resolução após clarificação.  
- Precisão percebida (NPS/CSAT curto sobre as sugestões similares).  
- Cobertura de alternativas (quantas vezes sugerimos ≥3 similares).

**Eventos estruturados** (via `SessionManager.log_event` e/ou `FALLBACK.build_event`):  
- `low_confidence`, `ambiguity_triggered`, `clarify`/`clarify_escalate` (inclui `clarify_count`/`clarify_last_ts`),  
- `fallback_no_products` (inclua `avg_score`, `similares`),  
- `api_retry`, `timeout`.

---

## 7. Como reproduzir

**Gradio (`code/fluxos_intencao/chat_web.py`)**  
1) Rodar a UI.  
2) Enviar “jaqueta jeans” → deve recomendar.  
3) Enviar “vestido vitoriano lilás de 1890” → deve cair em **opções similares**.  
4) Conferir no SQLite (`outputs/cache/sessions.db`) eventos `fallback_no_products` e `low_confidence`.

**FastAPI (`code/webapi/app.py`)**  
- `POST /api/chat` com `{"session_id":"web-session","message":"vestido vitoriano lilás de 1890"}`.  
- Resposta deve conter o texto de **opções similares**.  
- `fallback_events` no payload do `ChatResponse` carregam `thresholds`, `reason`, `clarify_*` (quando aplicável).

---

## 8. Decisões de projeto
- **Thresholds configuráveis e alinhados** ao detector de ambiguidade (`MIN_CONF=0.50`, `MIN_GAP=0.20`) via ENV.  
- **Normalização de labels** para robustez às variações do classificador.  
- **Mensagens rotacionadas** (round-robin/aleatório) para reduzir repetição.  
- **Telemetria padronizada** via `FALLBACK.build_event(...)` + `SessionManager.log_event(...)`.  
- **Contexto de perfil** nas mensagens de catálogo vazio.

---

## 9. Limitações
- Catálogo raso → “opções similares” podem soar genéricas.  
- Dependência do embedder atual (melhora com fine-tuning de embeddings).  
- Retry/backoff ainda é responsabilidade do caller de I/O externo.  
- `items_meta` precisa de curadoria (categorias/nomes coerentes) para boas mensagens.

---

## 10. Próximos passos
- Diversificar texto por **canal** (web/WhatsApp) e por **intenção**.  
- Ajustar `min_score` **por categoria** (ex.: vestidos vs. alfaiataria).  
- A/B de **clarificação** vs. **sugestão direta de filtros**.  
- Integrar `SessionManager.seen_products` para **evitar repetição** dos mesmos itens nas alternativas.  
- Expor painéis de telemetria (taxa de fallback, `clarify_count`, `avg_score`) para calibração contínua.
