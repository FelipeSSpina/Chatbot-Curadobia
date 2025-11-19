# Cache de Intenções e Contexto — Sprint 4

## Sumário
1. Visão geral  
2. Novidades da sprint  
3. Como funciona  
4. Fluxos e modelo de dados  
5. Interfaces  
6. Exemplos (uso real)  
7. Métricas (o que acompanhamos)  
8. Como reproduzir  
9. Decisões  
10. Limitações  
11. Próximos passos  
12. Apêndice A — requirements.txt estável

---

## 1. Visão geral
Implementamos uma camada de **cache de sessão** e **memória de preferências** para manter intenções, slots (ex.: CEP) e preferências (ex.: tamanho, cor, marca) e alimentar a resposta (ranking/templating).  
Arquivos principais:  
• `code/context/cache.py` — persistência em SQLite (sessions/turns/kv/events)  
• `code/context/session.py` — alto nível (snapshots de slots/perfil, API usada pelo FastAPI e Gradio)

---

## 2. Novidades da sprint
• **Conexão SQLite persistente** (RLock, WAL/NORMAL) → menos overhead por chamada.  
• **Histórico/eventos em ordem cronológica** (ORDER BY id ASC).  
• **Expiração KV na mesma transação** e **export de prefs em consulta única**.  
• **Snapshots** de `slots` e `profile` em `sessions.metadata_json`; merge do histórico só como fallback.  
• Persistência de **clarify_count** e **clarify_last_ts** no snapshot (telemetria).  
• `SessionManager.close()` para teardown de testes.  
• `SessionManager` **oculta o campo `id`** de itens de `history/events` para manter compatibilidade com consumidores antigos (o `export()` preserva).

---

## 3. Como funciona
• Cada conversa usa um `session_id` estável (persistido no front e enviado em todas as requisições).  
• Ao receber mensagem:  
  1) `SessionManager.load()` carrega a sessão e **lê snapshots** de `slots/profile` (ou faz merge do histórico se ainda não existirem).  
  2) Extraímos preferências/slots do texto (CEP/tamanho/cor/marca) e **lembramos via KV** quando apropriado.  
  3) Classificamos intenção + guard-rails/ambiguidade → podemos atualizar `slots` (ex.: `need_cep`, `clarify_count`).  
  4) Geramos a resposta (`profile_json` = base + prefs + slots conhecidos).  
  5) `append_turn()` persiste o turno e **atualiza snapshots** de `slots/profile` em `metadata_json`.  
• TTL padrão de **1h** para expurgo de sessões (ajustável via ENV `BIA_CACHE_TTL`).

---

## 4. Fluxos e modelo de dados
**Tabelas lógicas (SQLite)**  
• sessions(id, user_id, ttl_seconds, created_at, updated_at, metadata_json)  
• turns(id, session_id, ts, role, text, intent, confidence, gap_top2, slots_json, profile_json)  
• kv(id, session_id, key, value_json, updated_at, expires_at)  
• events(id, session_id, ts, kind, reason, payload_json)

**Fluxo resumido**  
load → (prefs/slots) → classificar (+coerções) → (ambiguity?) → responder → append_turn → save

**Snapshots**  
• `sessions.metadata_json` contém:  
  – `slots_snapshot`: último estado de slots  
  – `profile_snapshot`: último estado de perfil  
  – `clarify_count`, `clarify_last_ts` (telemetria de ambiguidade)

---

## 5. Interfaces
**SessionCache (baixo nível)**  
• `upsert_session(session_id, user_id=None, **metadata)`  
• `update_metadata(session_id, metadata: dict)`  
• `append_turn(session_id, role, text, intent=None, confidence=None, gap_top2=None, slots=None, profile=None)`  
• `history(session_id, limit=50)` → ordem cronológica  
• `log_event(session_id, kind, reason, payload=None)`  
• `load_events(session_id, kind=None, limit=100)` → ordem cronológica  
• `upsert_kv(session_id, key, value, ttl_sec=None)` / `get_kv(session_id, key, default=None)` / `delete_kv(...)` / `keys_by_prefix(...)`  
• `list_recent_sessions(limit=50)`  
• `purge_expired() -> (removed_sessions, removed_kv)`  
• `clear_session(session_id)` / `delete_session(session_id)`  
• `export_session(session_id) -> {session, turns, prefs, events}`  
• `close()`

**SessionManager (alto nível)**  
• `load(session_id, user_id=None) -> SessionState` (usa snapshots; esconde `id` de history/events)  
• `append_turn(state, role, text, intent=None, confidence=None, gap_top2=None, refresh=True)`  
• `set_slot(state, key, value, persist_snapshot=False)`  
• `set_profile(state, profile_dict, persist=True, persist_snapshot=True)`  
• `get_slot(...)`, `get_profile(...)`  
• `remember_pref(session_id, "pref:chave" | "chave", value, ttl_sec=None)`  
• `get_pref(session_id, key, default=None)`  
• `log_event(state, kind, reason, payload=None)`, `record_fallback_event(...)`  
• `clear(session_id)`, `delete(session_id)`, `recent(limit)`, `export(session_id)`, `purge()`, `close()`

---

## 6. Exemplos (uso real)

**6.1 Guardar turnos, preferências e CEP**

    from code.context.session import SessionManager
    sm = SessionManager(ttl_seconds=3600)

    st = sm.load("web-session", user_id="cliente-123")
    # slots em memória
    st.slots["cep"] = "01310200"
    # prefs persistentes (KV, sem TTL)
    sm.remember_pref("web-session", "tamanho_sup", "M", ttl_sec=None)

    # registrar predição/turno do usuário
    sm.append_turn(
        st, role="user", text="qual o prazo de entrega?",
        intent="frete_prazo", confidence=0.91, gap_top2=0.88
    )
    # turno do bot
    sm.append_turn(
        st, role="bot",
        text="Com base no seu CEP **01310200**, 3–7 dias úteis (simulado).",
        intent="frete_prazo"
    )
    # evento estruturado
    sm.log_event(st, kind="pred_debug", reason="post_classify",
                 payload={"intent":"frete_prazo","conf":0.91})

**6.2 Export para auditoria (histórico + prefs + eventos)**

    from code.context.session import SessionManager
    sm = SessionManager()
    data = sm.export("web-session")
    print("PREFS:", data["prefs"])            # tamanho_sup, cor, marca, cep (se informados)
    print("EVENTS (últimos 3):", data["events"][-3:])
    print("HISTORY (últimos 2):", data["turns"][-2:])

---

## 7. Métricas (o que acompanhamos)
• **Reutilização de slots** (ex.: frete usa CEP lembrado sem pedir novamente).  
• **Resolução em 1 turno** (menos voltas de clarificação).  
• **Redução de chamadas redundantes** ao ranking/índices quando a intenção muda pouco.  
• **Comprimento médio de histórico** por sessão (TTL respeitado).  
• **Taxa de fallbacks** (baixa confiança / catálogo vazio) registrada em `events`.  
• **Ambiguidade**: `clarify_count` e latência entre perguntas (via `clarify_last_ts`).

---

## 8. Como reproduzir
1) Inicie o Gradio ou o front.  
2) Troque algumas mensagens (declare tamanho/cor, peça sugestão, informe CEP).  
3) Inspecione o cache via Python REPL:

    from code.context.session import SessionManager
    sm = SessionManager()
    print(sm.export("web-session"))

Esperado: histórico dos turnos, prefs (tamanho/cor/marca/cep) e eventos (ex.: `pred_debug`, `cep_collected`, `fallback_no_products`).

---

## 9. Decisões
• SQLite local com colunas `*_json` para flexibilidade e baixo acoplamento.  
• TTL padrão de 1h (parametrizável) para equilíbrio entre utilidade e privacidade.  
• Preferências em **KV por sessão**, independentes do `profile` base; no runtime, unificamos `profile_base + prefs + slots`.  
• Snapshots de `slots/profile` em `sessions.metadata_json` para evitar merges caros a cada `load()`.

---

## 10. Limitações
• Sem deduplicação automática de intenções semelhantes no histórico.  
• TTL único por instância do cache.  
• Métricas agregadas (cross-sessões) ficam fora desta camada.  
• Consumidores que precisem do `id` de turns/events devem usar `export_session()` (o `load()` oculta por compatibilidade).

---

## 11. Próximos passos
• Endpoint `/api/history` para reidratar histórico no front principal (Next.js).  
• Persistir e consultar `seen_products` para evitar repetição de itens.  
• Job periódico `purge_expired()` integrado ao servidor.  
• Capturar **CEP isolado** (mensagem que é apenas `\d{5}-?\d{3}`) como atalho para fechar o slot.  
• Opcional: snapshots por “checkpoint” (a cada N turnos) em vez de todo `append_turn`.

---

## 12. Apêndice A — requirements.txt estável
pyyaml==6.0.2  
jsonschema==4.25.1  
pandas==2.3.2  
numpy==1.26.4  
scipy==1.10.1  
scikit-learn==1.6.1  
joblib==1.5.2  
tqdm==4.67.1  
sentence-transformers==2.7.0  
transformers==4.44.2  
sentencepiece==0.2.0  
torch==2.3.1  
peft==0.11.1  
accelerate==0.33.0  
datasets==2.20.0  
rich==13.7.1  
gradio==4.44.1  
httpx==0.27.2  
openpyxl==3.1.5  
matplotlib==3.10.0
