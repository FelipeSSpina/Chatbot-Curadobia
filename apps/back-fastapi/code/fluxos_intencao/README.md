# Fluxos de Inten��o � Curadobia 

Este m�dulo implementa os **fluxos conversacionais** (FSM) e integra o **classificador de inten��es** treinado no Item 2.  
Aqui est�o: o `fluxos.yaml`, o validador de schema, a exporta��o de transi��es, o motor de estados e o CLI de teste.

---

## Estrutura relevante

code/
+- fluxos_intencao/
� +- actions.py # A��   es de cada estado (respostas, side effects)
� +- cli_demo.py # CLI para teste manual do fluxo + NLU
� +- config.py # Config central (caminhos, thresholds)
� +- db.py # (Reservado) persist�ncia/telemetria simples
� +- engine.py # Motor do fluxo (FSM)
� +- nlu.py # Carrega artefatos do modelo e prediz inten��es
� +- service.py # Orquestra NLU + Engine (camada de servi�o)
� +- yaml_loader.py # Loader/validador do YAML em estrutura Python
� +- README.md
+- notebooks/
� +- modelos/ # Artefatos do modelo v1 (Item 2)
� +- classifier.pkl
� +- label_encoder.pkl
� +- config.json
� +- embedding_model_name.txt
+- resources/
+- fluxos.yaml # Especifica��o dos fluxos (Item 3)
+- fluxos.schema.json # JSON Schema para validar o YAML
+- export_transicoes.py
+- validate_fluxos.py
