# Detecção de Ambiguidades — Sprint 4

## Sumário
1. Visão geral  
2. Como funciona  
3. Fluxo  
4. Interfaces  
5. Exemplos  
6. Métricas  
7. Como reproduzir  
8. Decisões  
9. Limitações  
10. Próximos passos  

---

## 1. Visão geral
Formalizamos um detector de **ambiguidades** para mensagens vagas ou multi-intenção. Ele trabalha junto do **gating por confiança/gap** e dos **fallbacks**.  
Módulos: `code/ambiguity/detector.py` (detector) e `code/ambiguity/clarify.py` (perguntas de esclarecimento). Integrações: `code/webapi/app.py` e `code/fluxos_intencao/chat_web.py`.

Destaques:
- Low-signal por **substring e regex**.  
- Combinação de critérios via modo **any** (padrão) ou **score** (pesos).  
- Telemetria: `metrics` + `triggered_rules` e `reason` padronizado.  
- Clarificação com chaves específicas por motivo; rotação de mensagens.  
- Limite de tentativas com `clarify_count` e escala para **atendimento**.

---

## 2. Como funciona
Entrada: `conf` (confiança do top-1), `gap` (p1−p2), `text` e `intents` (top-k).

Regras que marcam **ambíguo**:
- **Baixa confiança**: `conf < MIN_CONF` (padrão 0.50).  
- **Gap pequeno**: `gap < MIN_GAP` (padrão 0.20).  
- **Frases de baixo sinal** (LOW_SIGNAL): “preciso de ajuda”, “me ajuda”, “não sei”, “tô em dúvida”, etc. (também regex).

Resultado:  
`AmbiguityResult(ambiguous: bool, reason: str, details: dict, metrics: dict, triggered_rules: list)`.

Se ambíguo, geramos pergunta com `clarify(...)` e registramos evento/estado.

---

## 3. Fluxo
classify_intent → normalizar label → coerções (guards) → AmbiguityDetector (scores + LOW_SIGNAL)  
→ se **ambíguo**: salvar `reason`/métricas e `clarify_count` → `clarify(key)` específico → reclassificar  
→ se **não ambíguo**: segue para `generate_response`.

---

## 4. Interfaces
- `code/ambiguity/detector.py`  
  - `AmbiguityDetector(confidence_threshold=0.50, gap_threshold=0.20, low_signal_phrases={...}, mode="any"|"score")`  
  - `from_scores(conf, gap, text, intents) -> AmbiguityResult`  
  - `from_prediction(text, pred) -> AmbiguityResult`  
  - Atualizações em runtime: `update_thresholds(...)`, `update_weights(...)`, `add_low_signal_phrases(...)`, `add_low_signal_regex(...)`, `replace_low_signal(...)`.

- `code/ambiguity/clarify.py`  
  - `clarify(key: str, *, top1=None, top2=None, strategy=None| "round_robin" | "random", seed=None, state=None, order=0)`  
  - `scripted_loop(key: str) -> list[str]`  
  - Chaves: `nao_entendi`, `ambigua_gap_top2`, `ambigua_low_signal`, `multi_intencao`, `atendimento`, `ambigua_generica`, etc.  
  - Placeholders `{top1}`/`{top2}` e ≥2 variações por chave (rotação opcional por `state`).

- Integrações  
  - `code/webapi/app.py` e `code/fluxos_intencao/chat_web.py`:  
    - Persistem `slots.ambiguity.reason`, `slots.clarify_count` e registram eventos.  
    - Seleção do template de clarificação conforme `reason`.  
    - Após `AMB_MAX_CLARIFY`, usam `clarify("atendimento")`.

---

## 5. Exemplos
    from code.ambiguity.detector import AmbiguityDetector
    from code.ambiguity.clarify import clarify

    # Detector modo padrão (any)
    det = AmbiguityDetector(confidence_threshold=0.50, gap_threshold=0.20)

    pred = {"conf": 0.92, "gap": 0.05, "top3": [("pedido_sugestao", 0.52), ("frete_prazo", 0.47)]}
    res = det.from_prediction("quero algo legal", pred)
    if res.ambiguous:
        # motivo: small_gap_top2 -> pergunta focada
        print(clarify("ambigua_gap_top2", top1="pedido_sugestao", top2="frete_prazo"))

    # Detector em modo score (tuning)
    det2 = AmbiguityDetector(mode="score", min_score=1.0, weights={"conf": 1.0, "gap": 1.0, "low": 1.0})
    res2 = det2.from_scores(0.41, 0.30, "não sei ainda",
                            [("pedido_sugestao", 0.41), ("formas_pagamento", 0.34)])
    print(res2.reason, res2.metrics)

---

## 6. Métricas
- % de mensagens marcadas como ambíguas.  
- % resolvida após **1** clarificação.  
- Queda nas respostas “não entendi”.  
- Tempo médio até resolução após a 1ª clarificação.  
- Distribuição por **reason** (`low_signal_phrase`, `small_gap_top2`, etc.) e por **intent**.

---

## 7. Como reproduzir

A) Detector (CLI rápido)  
    python -m code.ambiguity.detector
    # modo score:
    AMB_MODE=score AMB_MIN_SCORE=1.0 AMB_WEIGHTS='{"conf":1,"gap":1,"low":1}' python -m code.ambiguity.detector

B) Gradio (`code/fluxos_intencao/chat_web.py`)  
1) Rodar: `python code/fluxos_intencao/chat_web.py`  
2) Enviar: “não sei”, “me ajuda”, “quero algo para sair…”  
3) Conferir pergunta de clarificação e, no SQLite, `slots.ambiguity.reason` e `slots.clarify_count`.

C) FastAPI (`code/webapi/app.py`)  
1) Rodar: `uvicorn code.webapi.app:app --host 127.0.0.1 --port 8000`  
2) POST `/api/chat` com `session_id` fixo e mensagens de teste.  
3) Resposta: pergunta de clarificação; após N → “atendimento”.  
4) Logs/eventos: `fallback_events` e `ambiguity` no estado da sessão.

Snippets de inspeção (Python REPL):  
    from code.context.session import SessionManager
    sm = SessionManager()
    print([t for t in sm.history("web-session") if (t["role"] == "meta")][-3:])

---

## 8. Decisões
- Padrão **any** para manter comportamento legado; **score** para calibração futura.  
- Rotação (`round_robin`) nas falas de clarificação para evitar loops.  
- Thresholds alinhados ao pipeline (`MIN_CONF=0.50`, `MIN_GAP=0.20`).  
- Textos centralizados em `clarify.py` para revisão de conteúdo.

---

## 9. Limitações
- Regex muito ampla pode gerar falsos positivos (curadoria necessária).  
- Modo `score` exige ajuste de pesos por domínio/dataset.  
- Detecção de low-signal é heurística; melhora com dados reais.

---

## 10. Próximos passos
- Dashboards: taxa por **reason**, por **intent** e por **etapa** do funil.  
- A/B de **templates** (CTR de desambiguação) e de **thresholds**.  
- Dataset de ambiguidades reais → classificador leve de **low-signal**.  
- Ajuste de `AMB_MAX_CLARIFY` (ENV) conforme métricas de satisfação.
