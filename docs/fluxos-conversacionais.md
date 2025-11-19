# Fluxos Conversacionais 

&emsp;Este documento descreve a defini��o dos fluxos conversacionais para o bot BIBI, com base no arquivo execut�vel **`code/resources/fluxos.yaml`** desenvolvido pelo grupo CuradoBot.

O arquivo cont�m a estrutura de:

- **Intents**: inten��es do usu�rio expressas nas mensagens.
- **Entidades**: informa��es relevantes extra�das da conversa.
- **Slots**: campos obrigat�rios que precisam ser preenchidos em certos fluxos.
- **Templates de resposta**: mensagens que o bot pode utilizar conforme o contexto.
- **A��es**: processos que o bot pode executar.
- **Estados e transi��es**: l�gica que define a jornada conversacional.

---

## 1) Objetivo e escopo
- Guiar o atendimento em **e-commerce de moda** (Curadobia) cobrindo: descoberta, estoque, frete, pagamento, status do pedido, trocas, tamanho/modelagem, styling, materiais/cuidados, como comprar, suporte de login/checkout, B2B, p�s-venda e handoff humano.

## 2) Princ�pios de design
1. **M�quina de estados** com roteamento por **inten��o** + **guardas** (slots).
2. **Fail-safe**: `fallbacks` e **handoff** sob baixa confian�a, sil�ncio, frustra��o ou fora do hor�rio.
3. **Fonte �nica**: pol�ticas (troca/pagamento/frete) v�m da KB; estoque do BD; tamanho modelado por slots.
4. **Tom Curadobia**: leve, consultivo, direto.

---

## 3) Intents

&emsp; As intents representam o prop�sito ou inten��o por tr�s da mensagem do usu�rio.

- **saudacao:** iniciar conversa (oi, ol�, bom dia).
- **agradecimento:** agradecer ou elogiar (obrigada, valeu).
- **despedida:** encerrar conversa.
- **duvida_tamanho:** d�vidas sobre medidas, numera��o, servir/caber.
- **pedido_sugestao:** pedir sugest�es de looks ou combina��es.
- **disponibilidade:** verificar estoque, tamanhos, cores.
- **preco_pagamento:** consultar valores, formas de pagamento.
- **prazo_entrega:** prazo de entrega e rastreio.
- **troca_devolucao:** trocas, devolu��es, produtos com defeito.
- **onde_comprar:** como e onde comprar.
- **cupom_primeira:** cupom de primeira compra.
- **erros_plataforma:** erros ou bugs no sistema.
- **falar_com_humano:** pedir atendimento humano.
- **buscar_produto_por_nome:** procura o produto pelo nome.
- **buscar_produto_por_categoria:** procura o produto pela categoria (blusa, cal�a, saia)
- **status_pedido:** consulta o status do pedido
- **materiais_cuidados:** indica de quais materiais a roupa � feita e quais cuidados tomar.
- **cliente_loja_b2b:** informa��es para clientes b2b
- **pos_venda:** informa��es e ajuda ap�s realiza��o da compra.
- **outros:** fallback para casos n�o mapeados.

## 4) Entidades (slots)
- **Produto**: `produto.nome`, `categoria{vestido,blusa,calca,saia,macaquinho,casaco,acessorio,outro}`, `marca`, `preco.max`, `sku`, `cor`, `tamanho`.
- **Pedido/Contato**: `pedido.id`, `contato.email`, `contato.telefone`.
- **Frete**: `geo.cep`.
- **Tamanho/Styling**: `medidas.busto/cintura/quadril/altura`, `tamanho_ref`, `elasticidade{baixa,media,alta}`, `ocasiao{trabalho,festa_dia,viagem,casual}`, `budget`.
- **Materiais**: `tecido`.

> **Sem�ntica de guardas** no YAML: `has(slot)`/`!has(slot)`.

---

## 5) A��es
As a��es s�o processos autom�ticos disparados pelo bot em resposta �s intents e fluxos.

- **identificar_intencao:** interpretar a mensagem do usu�rio e direcionar para o fluxo correto.
- **consultar_catalogo:** buscar produtos no cat�logo para recomendar ou obter informa��es.
- **verificar_estoque:** checar disponibilidade de produto, tamanho e cor.
- **consultar_preco:** recuperar pre�os e condi��es de pagamento.
- **calcular_prazo_entrega:** calcular prazo de entrega a partir do CEP informado.
- **processar_troca:** abrir processo de troca ou devolu��o.
- **fornecer_link_compra:** compartilhar link direto para finalizar compra.
- **gerar_cupom:** criar cupom promocional.
- **registrar_erro:** registrar problema t�cnico relatado pelo usu�rio.
- **abrir_ticket_humano:** direcionar para atendimento humano.
- **consultar_status_pedido:** verificar status de pedido por ID.
- **calcular_frete:** estimar valor do frete com base no CEP.
- **exibir_resultado:** mostrar informa��es consolidadas ao usu�rio.
- **gerar_sugestoes:** gera sugest�es de looks para o cliente.
- **buscar_produto_por_nome:** busca produto no estoque por nome.
- **buscar_produto_por_categoria:** busca produto no estoque por categoria.
- **estimar_tamanho:** ajuda o cliente a saber qual � o tamanho ideal.
- **sugerir_looks:** sugere looks para o cliente.
- **responder_kb_materiais:** responde d�vidas sobre os materiais que as pe�as s�o confeccionadas.
- **instruir_checkout:** ajuda cliente realizar o check-out.

## 6) Fluxos

&emsp; Cada fluxo � composto por:

- **Estado**: representa o ponto atual da conversa.
- **Slots obrigat�rios**: informa��es que precisam ser coletadas.
- **Perguntas** para preencher slots.
- **A��o final**: processo disparado quando os slots s�o preenchidos.
- **Pr�xima a��o**: transi��o para o pr�ximo estado.
  
### Exemplos de fluxos:

**Fluxo: Pedido de Sugest�o**
- **Estado:** pedido_sugestao
- **Slots obrigat�rios:** produto
- **Pergunta:** �Qual produto ou estilo voc� gostaria que eu sugerisse?�
- **A��o final:** consultar_catalogo
- **Pr�xima a��o:** fornece_sugestoes

**Fluxo: Disponibilidade de Produto**
- **Estado:** disponibilidade
- **Slots obrigat�rios:** produto, tamanho, cor
- **Perguntas:**
- Produto: �De qual produto voc� gostaria de verificar a disponibilidade?�
- Tamanho: �Qual tamanho deseja verificar?�
- Cor: �Qual cor voc� procura?�
- **A��o final:** verificar_estoque
- **Pr�xima a��o:** fornece_info

**Fluxo: Troca e Devolu��o**
- **Estado:** troca_devolucao
- **Slot obrigat�rio:** problema
- **Pergunta:** �O que aconteceu com o produto? (defeito, tamanho errado, arrependimento)�
- **A��o final:** processar_troca
- **Pr�xima a��o:** fornece_info

&emsp; Portanto, cada fluxo foi projetado para oferecer atendimento consultivo e humanizado, garantir respostas r�pidas e contextuais, permitir fallbacks inteligentes para manter a conversa e Integrar com a��es do backend (estoque, pedidos, pagamentos, etc.).

##  Tabela de Fluxos

| Fluxo                  | Estado          | Slots obrigat�rios       | Perguntas principais                                                                 | A��o final            | Pr�xima a��o      |
|-------------------------|-----------------|--------------------------|---------------------------------------------------------------------------------------|-----------------------|------------------|
| Pedido de Sugest�o      | pedido_sugestao | produto                  | Qual produto ou estilo voc� gostaria que eu sugerisse?                                | consultar_catalogo    | fornece_sugestoes |
| Disponibilidade Produto | disponibilidade | produto, tamanho, cor    | Produto: De qual produto? <br> Tamanho: Qual tamanho? <br> Cor: Qual cor?             | verificar_estoque     | fornece_info      |
| Troca e Devolu��o       | troca_devolucao | problema                  | O que aconteceu com o produto? (defeito, tamanho errado, arrependimento)              | processar_troca       | fornece_info      |
| Prazo de Entrega        | prazo_entrega   | cep                      | Qual � o seu CEP para calcular o prazo de entrega?                                    | calcular_prazo_entrega| fornece_info      |
| Status do Pedido        | status_pedido   | pedido_id                | Voc� poderia informar o ID do seu pedido?                                            | consultar_status_pedido | fornece_info    |
| Pre�o e Pagamento       | preco_pagamento | produto                  | De qual produto voc� deseja saber o pre�o ou formas de pagamento?                     | consultar_preco       | fornece_info      |
| Onde Comprar            | onde_comprar    | �                        | Deseja comprar pelo site, Instagram ou WhatsApp?                                     | fornecer_link_compra  | fornece_info      |
| Cupom Primeira Compra   | cupom_primeira  | �                        | Deseja ativar seu cupom de primeira compra?                                          | gerar_cupom           | fornece_info      |
| Erro de Plataforma      | erro_plataforma | descricao_problema       | Pode descrever qual erro ocorreu? (ex.: n�o consigo pagar/logar, travou)              | registrar_erro        | abrir_ticket_humano |
| Atendimento Humano      | falar_com_humano| �                        | Deseja falar com um atendente humano?                                                | abrir_ticket_humano   | fornece_info      |

## 7) Estados e transi��es

### START
- **Entry:** `boas_vindas`.
- **?** `CAPTURA_INTENCAO` (qualquer input).

### CAPTURA_INTENCAO (roteador NLU ? estado)
- **Transi��es principais:**
  - `pedir_sugestao_produto` ? `RECOMENDAR` _(action: `gerar_sugestoes`)_
  - `buscar_produto_por_nome` + `has(produto.nome)` ? `BUSCA_PRODUTO` _(action)_  
  - `buscar_produto_por_categoria` + `has(categoria)` ? `BUSCA_PRODUTO` _(action)_
  - `disponibilidade_estoque` ? `INFO_ESTOQUE` _(action: `consultar_estoque`)_
  - `frete_prazo` + `has(geo.cep)` ? `INFO_FRETE` _(action: `cotar_frete`)_  
  - `frete_prazo` + `!has(geo.cep)` ? `FALLBACK_PEDIR_CEP`
  - `formas_pagamento` ? `INFO_PAGAMENTO`
  - `status_pedido` + `has(pedido.id)` ? `STATUS_PEDIDO` _(action)_
  - `status_pedido` + `!has(pedido.id)` ? `FALLBACK_PEDIR_PEDIDO`
  - `troca_devolucao_politica` ? `POLITICA_TROCA` _(action)_
  - `tamanho_modelagem` ? `TAMANHO_MODELAGEM`
  - `styling_sugestao_look` ? `STYLING`
  - `materiais_cuidados` ? `MATERIAIS` _(action: `responder_kb_materiais`)_
  - `como_comprar` ? `COMO_COMPRAR`
  - `erros_plataforma` ? `SUPORTE_LOGIN`
  - `cliente_loja_b2b` ? `CLIENTE_B2B`
  - `pos_venda` ? `POS_VENDA`
  - `falar_com_humano` ? `FALAR_HUMANO`
  - `despedida`/`agradecimento` ? `ENCERRAMENTO`
  - `nao_entendi`/`any` ? `FALLBACK_PEDIR_REFORMULACAO`

### RECOMENDAR
- **Fluxo curto:** ap�s sugerir, ? `ENCERRAMENTO`.

### BUSCA_PRODUTO
- **Ap�s a��o de busca:** ? `INFO_ESTOQUE` para listar resultados.

### INFO_ESTOQUE / INFO_FRETE / INFO_PAGAMENTO / STATUS_PEDIDO / POLITICA_TROCA / MATERIAIS / COMO_COMPRAR
- **Entry (quando aplic�vel):** `frete_info`, `pagamento_info`, `troca_info`, `materiais_result`, `como_comprar_info`.
- **Sa�da:** ? `ENCERRAMENTO` (ap�s resposta).

### TAMANHO_MODELAGEM ? TAMANHO_MODELAGEM_RESULT
- **Entry:** `tamanho_prompt`.  
- **Regra:** quando `has(tamanho_ref)` **ou** `has(medidas.busto)` ? `estimar_tamanho` ? `TAMANHO_MODELAGEM_RESULT` (template `tamanho_result`) ? `ENCERRAMENTO`.

### STYLING ? STYLING_RESULT
- **Entry:** `styling_prompt`.
- **Regra:** quando `has(categoria)` **ou** `has(ocasiao)` ? `sugerir_looks` ? `STYLING_RESULT` (template `styling_result`) ? `ENCERRAMENTO`.

### SUPORTE_LOGIN
- **Entry:** `suporte_login_passos`.
- **Transi��es:** se `falar_com_humano` ? `FALAR_HUMANO`; caso contr�rio, ? `ENCERRAMENTO`.

### CLIENTE_B2B
- **A��o:** `abrir_chamado` (coleta contato) ? `ENCERRAMENTO`.

### POS_VENDA
- **Regra:** se `has(pedido.id)` ? `consultar_status_pedido` ? `ENCERRAMENTO`; sen�o, ? `FALLBACK_PEDIR_PEDIDO`.

### FALLBACKS
- `FALLBACK_PEDIR_CEP` (template `pedir_cep`) ? quando `has(geo.cep)` ? `INFO_FRETE`.
- `FALLBACK_PEDIR_PEDIDO` (template `pedir_pedido_id`) ? quando `has(pedido.id)` ? `STATUS_PEDIDO`.
- `FALLBACK_PEDIR_REFORMULACAO` (template `nao_entendi_tente`) ? `CAPTURA_INTENCAO`.
- **Fallback global:** `on_unrecognized_intent` ? `FALLBACK_PEDIR_REFORMULACAO`.

### FALAR_HUMANO
- **Entry:** `handoff` ? coleta contato/hor�rio ? `ENCERRAMENTO`.

### ENCERRAMENTO
- **Entry:** `encerrar`.

---

## 8) Templates 

&emsp;Os templates s�o maneiras que o chatbot poder� responder em cada situa��o.

&emsp;Alguns templates s�o:

- **boas_vindas**: "Oi! Eu sou a BIBI da Curadobia. Bora achar seu tcharanz hoje? ?"
- **agradecimento**: "Fico feliz em ajudar! ??"
- **encerrar**: "Foi um prazer ajudar! Se precisar, � s� chamar. ??"
- **pedir_cep**: "Pra calcular o frete, me passa seu CEP? Ex.: 01234-567"
- **pedir_pedido_id**: "Voc� consegue me passar o n�mero do seu pedido (ou e-mail usado na compra)?"
- **outros**: "T� quase l�! Quer me dizer de outro jeitinho ou prefere falar com uma pessoa do time? ??"
- **handoff**: "Pra te ajudar melhor, vou acionar nosso time humano ?? Qual o melhor contato e hor�rio?"
- **fora_horario**: "Nosso time humano atende de 9h �s 18h (seg�sex). Posso abrir um chamado e eles te retornam no pr�ximo expediente."

> Estes textos est�o **id�nticos** aos do YAML para manter consist�ncia.


---

## 9) Pol�ticas de fallback e handoff
- **Tentativas de slot:** 2 por estado de coleta; em falha, oferecer `FALAR_HUMANO`.
- **OOD / n�o reconhecida:** `FALLBACK_PEDIR_REFORMULACAO` (2x) ? `FALAR_HUMANO`.
- **Fora do hor�rio humano:** exibir `fora_horario` + registrar contato.
- **Timeout:** 1 lembrete; depois `ENCERRAMENTO`.

---

## 10) M�tricas de QA
- Cobertura de inten��o = **95%** nos cen�rios.
- Zero diverg�ncias com Pol�ticas.
- % de handoff adequado, tempo mediano por inten��o, taxa de resolu��o no primeiro estado.

> **Valida��o:** `python c�digo/resources/validate_fluxos.py`  
> **Transi��es (CSV):** `python c�digo/resources/export_transicoes.py`

