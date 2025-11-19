# Inten��es, Entidades e Estados 

## Inten��es (r�tulos)
- saudacao
- despedida
- agradecimento
- nao_entendi
- falar_com_humano
- pedir_sugestao_produto
- buscar_produto_por_nome
- buscar_produto_por_categoria
- disponibilidade_estoque
- frete_prazo
- formas_pagamento
- status_pedido
- troca_devolucao_politica
- tamanho_modelagem
- styling_sugestao_look
- materiais_cuidados
- como_comprar
- erros_plataforma
- cliente_loja_b2b
- pos_venda

## Entidades (slots)
- produto.nome (string)
- categoria (enum: vestido, blusa, calca, saia, macaquinho, casaco, acessorio, outro)
- marca (string)
- preco.max (number)
- pedido.id (string)
- geo.cep (string)
- contato.email (string)
- contato.telefone (string)
- medidas.busto/cintura/quadril/altura (number)
- tamanho_ref (string)
- tecido (string)
- elasticidade (enum: baixa, media, alta)
- ocasiao (enum: trabalho, festa_dia, viagem, casual)
- budget (number)
- sku (string)
- cor (string)
- tamanho (string)

## Estados (m�quina de estados)
- START
- CAPTURA_INTENCAO
- RECOMENDAR
- BUSCA_PRODUTO
- INFO_ESTOQUE
- INFO_FRETE
- INFO_PAGAMENTO
- STATUS_PEDIDO
- POLITICA_TROCA
- TAMANHO_MODELAGEM
- TAMANHO_MODELAGEM_RESULT
- STYLING
- STYLING_RESULT
- MATERIAIS
- COMO_COMPRAR
- SUPORTE_LOGIN
- CLIENTE_B2B
- POS_VENDA
- FALLBACK_PEDIR_CEP
- FALLBACK_PEDIR_PEDIDO
- FALLBACK_PEDIR_REFORMULACAO
- FALAR_HUMANO
- ENCERRAMENTO

