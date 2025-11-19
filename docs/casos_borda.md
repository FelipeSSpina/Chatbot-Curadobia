# Casos de Borda � Curadobia 

Este documento consolida as **situa��es excepcionais** e como o fluxo deve reagir, em alinhamento ao YAML execut�vel (`c�digo/resources/fluxos.yaml`) e �s Pol�ticas Curadobia. Cada caso indica **estado/a��o** sugeridos.

---

## 1) Dados insuficientes ou inv�lidos

### CEP ausente/irregular
- **Sinal:** CEP ausente, com letras, d�gitos a menos/mais ou m�scara incorreta.
- **A��o/Estado:** `FALLBACK_PEDIR_CEP` (template `pedir_cep`) ? normalizar (#####-###), aceitar tamb�m �########�.
- **Regra:** at� **2 tentativas**; se falhar, oferecer `FALAR_HUMANO`.

### N�mero do pedido ausente/inv�lido
- **Sinal:** string muito curta, sem padr�o interno, sem correspond�ncia no BD.
- **A��o/Estado:** `FALLBACK_PEDIR_PEDIDO` ? se continuar inv�lido, ir para `FALAR_HUMANO`.

### Slots faltantes (tamanho/styling)
- **Sinal:** inten��o reconhecida, mas sem `tamanho_ref` nem `medidas.*`, ou sem `categoria/ocasiao`.
- **A��o/Estado:** permanecer em `TAMANHO_MODELAGEM`/`STYLING` pedindo slots; ap�s 2 tentativas sem slots, oferecer `FALAR_HUMANO`.

---

## 2) Problemas de cat�logo e log�stica

### Produto fora de estoque
- **Sinal:** `consultar_estoque` retorna 0.
- **A��o/Estado:** em `INFO_ESTOQUE`, ofertar **similares** (mesma categoria/cor/pre�o) ou **notifica��o de reposi��o**; se for essencial, `FALAR_HUMANO`.

### Nenhum resultado de busca
- **Sinal:** busca por nome/categoria vazia.
- **A��o/Estado:** sugerir **categorias populares** (templates breves) e **reformular** ? `FALLBACK_PEDIR_REFORMULACAO`.

### Frete indispon�vel para CEP
- **Sinal:** transportadora n�o atende CEP.
- **A��o/Estado:** explicar limita��o e abrir op��o `FALAR_HUMANO` para alternativas.

---

## 3) Falhas t�cnicas e limites

### Erros de plataforma (login/checkout)
- **Sinal:** usu�rio relata erro/autentica��o falha.
- **A��o/Estado:** `SUPORTE_LOGIN` (template `suporte_login_passos`); se persistir, `FALAR_HUMANO`.

### Timeout / sil�ncio do usu�rio
- **Sinal:** sem mensagem ap�s **N** segundos (config app).
- **A��o/Estado:** repetir prompt do estado atual **1 vez**; em seguida, `ENCERRAMENTO` gentil.

### Falha de ferramenta/BD
- **Sinal:** exce��o em `consultar_estoque`, `cotar_frete`, etc.
- **A��o/Estado:** responder com mensagem emp�tica e **fallback para humano**; logar erro com `corr_id`.

---

## 4) Inten��o, linguagem e seguran�a

### Repetidas n�o reconhecidas / fora do dom�nio (OOD)
- **Sinal:** 2+ mensagens sem mapear inten��o �til.
- **A��o/Estado:** `FALLBACK_PEDIR_REFORMULACAO` ? sugerir t�picos suportados ? `CAPTURA_INTENCAO`; se persistir, `FALAR_HUMANO`.

### Mudan�a brusca de inten��o
- **Sinal:** o usu�rio troca de tema subitamente.
- **A��o/Estado:** roteamento **sempre permitido** em `CAPTURA_INTENCAO` (sem prender em estado anterior).

### Linguagem inadequada/abuso
- **Sinal:** ofensas, palavr�es.
- **A��o/Estado:** mensagem curta, profissional, oferecer `FALAR_HUMANO` se o usu�rio quiser continuar.

### Crise/urg�ncia
- **Sinal:** �preciso hoje�, �cancelar agora�.
- **A��o/Estado:** priorizar `FALAR_HUMANO` com coleta de contato e janela de hor�rio.

### Multi-idioma
- **Sinal:** usu�rio alterna para espanhol/ingl�s.
- **A��o:** responder no idioma detectado **se** suportado; caso contr�rio, oferecer ajuda em PT-BR + humano.

### Imagem enviada
- **Sinal:** foto de corpo/pe�a para tamanho/styling.
- **A��o:** explicar limites; pedir **medidas ou tamanho_ref** e **categoria**; seguir fluxo normal.

### LGPD / Dados sens�veis
- **Sinal:** documentos, cart�es, senhas.
- **A��o:** **n�o coletar**; orientar canais oficiais; registrar recusa educadamente.

---

## 5) Handoff e hor�rio

### Pedir humano explicitamente
- **A��o/Estado:** `FALAR_HUMANO` (template `handoff`) com coleta de **contato** e **hor�rio**.

### Fora do hor�rio humano
- **A��o/Estado:** exibir `fora_horario` + abrir chamado; confirmar janela de retorno.

---

## 6) Crit�rios de corte (loop-guard)
- **Tentativas de slot:** 2 por estado de coleta (`FALLBACK_*`, `TAMANHO_MODELAGEM`, `STYLING`).
- **Reformula��es:** 2 seguidas em `FALLBACK_PEDIR_REFORMULACAO` ? `FALAR_HUMANO`.
- **Tempo de inatividade:** 1 lembrete, depois `ENCERRAMENTO`.

---

## 7) Telemetria m�nima (para QA)
- `intent`, `state_from ? state_to`, `has_slots`, `tool_ok`, `handoff`, `elapsed_ms`, `corr_id`.

> Todos os casos aqui mapeados est�o cobertos por estados/templates/fallbacks do YAML vigente.

