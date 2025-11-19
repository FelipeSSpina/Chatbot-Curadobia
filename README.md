<div align="justify">
<table width="100%">
  <tr>
    <td width="50%" align="center">
      <a href="https://www.curadobia.com.br/curadobia/institucional">
        <img src="assets/imagens/logo_curadobia.png" alt="Curadobia" height="80px">
      </a>
    </td>
    <td width="50%" align="center">
      <a href="https://www.inteli.edu.br/">
        <img src="https://www.inteli.edu.br/wp-content/uploads/2024/06/logo-inteli-3-768x420-1.png" alt="Inteli - Instituto de Tecnologia e Liderança" height="80px">
      </a>
    </td>
  </tr>
</table>


## Projeto: Sistema de processamento de linguagem natural com IA generativa

# Introdução

&emsp;O projeto tem como objetivo o desenvolvimento de um chatbot inteligente e humanizado para o Curadobia, capaz de integrar tecnologia e curadoria de moda em um atendimento automatizado, personalizado e escalável. Baseada em algoritmos de Processamento de Linguagem Natural (PLN), a solução será incorporada ao site da marca para oferecer respostas contextualizadas sobre produtos, sugestões de combinações, informações de modelagem e orientações de compra, sempre preservando o tom de voz próximo, leve e consultivo que caracteriza a empresa. Além de aprimorar a experiência das clientes, o chatbot proporcionará ao time interno dados estratégicos sobre dúvidas recorrentes e oportunidades de melhoria, apoiando a evolução contínua do atendimento.

## Descrição:

&emsp;Desenvolvimento de um chatbot inteligente, baseado em processamento de linguagem natural (PLN), que será integrado ao ambiente digital do Curadobia para oferecer atendimento automatizado, personalizado e humanizado às clientes, fazendo a recomendação de produtos e respondendo clientes.


## Grupo 4 - Curadobot :

#  Integrantes
- [André Hutzler](https://www.linkedin.com/in/andr%C3%A9-hutzler-60aa28277/)  
- [Diogo Burgierman](https://www.linkedin.com/in/diogo-pelaes-a34593279/)
- [Felipe Braga](https://www.linkedin.com/in/felipe-braga-69607126a/)   
- [Felipe Spina](https://www.linkedin.com/in/felipe-sabino-spina-b33372271/)
- [Henrique Burle](https://www.linkedin.com/in/henrique-burle/)   
- [Marina Ladeira](https://www.linkedin.com/in/marinaladeira/)
- [Pedro Auler](https://www.linkedin.com/in/pedro-auler-a3b23021a/)  
- [Raissa Paula](https://www.linkedin.com/in/raissa-paula/)  

###  Professores e Instrutores

## Orientador  
- [ Tomaz Mikio Sasaki](https://www.linkedin.com/in/tmsasaki/)

## Instrutores: 

- [Cristina Gramani - Professora de matemática](https://www.linkedin.com/in/cristinagramani/)
- [ Filipe Gonçalves - Professor de Liderança](https://www.linkedin.com/in/filipe-gon%C3%A7alves-08a55015b/)
- [ Rodolfo Goya - Professor de Programação](https://www.linkedin.com/in/rodolfo-goya-6ab187/)
- [ Fillipe Resina - Professor de Programação](https://www.linkedin.com/in/fillipe-resina-b2211a22/)
- [ Jefferson Silva - Professor de Programação](https://www.linkedin.com/in/jefferson-o-silva/)
- [Pedro Teberga - Professor de Negócios](https://www.linkedin.com/in/pedroteberga/)

## Descrição das pastas

- **Docs:** Pasta contendo o artigo e as documentações dos notebooks desenvolvidos para a solução.
- **Notebooks:** Pasta contendo os notebooks desenvolvidos durante todas as Sprints.
- **Apps:** Pasta contendo o front-end e back-end do chatbot.
- **Slides:** Pasta contendo os slides utilizados durante as reviews.
- **Assets:** Pasta contendo as imagens utilizadas no artigo e no readme.
- **README.md:** arquivo que serve como guia e explicação geral sobre o projeto (o mesmo que você está lendo agora).

## Requisitos

**Requisitos de Software**

- Python 3.10+ (recomendado: 3.11)
- pip atualizado (pip install --upgrade pip)
- Git para clonar o repositório
- VS Code ou outro editor compatível com Python 

**Requisitos de Hardware**

Para executar a aplicação localmente:

- CPU de 4 núcleos ou mais

- 8 GB de RAM (mínimo recomendado)

- 2 GB de espaço livre em disco

- (Opcional) GPU compatível com CUDA para acelerar tarefas de NLP com PyTorch

Em máquinas sem GPU, o projeto funciona normalmente — o arquivo requirements.txt já está configurado para usar Torch CPU no Windows.

**Requisitos de Serviços**

Para executar os notebooks de experimentos, recomenda-se:

- Google Colab Pro+ ou ambiente local com suporte a GPU.

Versão do runtime no Colab:

- Python 3.10+

- GPU: T4 ou A100

- RAM: 25 GB ou mais (Pro+)


##  Configuração para Desenvolvimento

1. Abra o terminal e clone o repositório utilizando o comando:

```bash
git clone https://github.com/Inteli-College/2025-2A-T07-CC11-G04.git
```

2. Instale todas as dependências do projeto com o seguinte comando: 
   
```bash   
pip install -r requirements.txt
```
Isso instalará automaticamente todas as bibliotecas listadas no arquivo requirements.txt, incluindo Torch, Transformers, FastAPI, e outras dependências necessárias para o projeto.

3. Caso queira rodar apenas os notebooks, utilize o Colab Pro+ para que eles funcionem corretamente.


## Como rodar o projeto

&emsp; **Para o back-end:**

1. Abra o terminal e execute o seguinte comando para acessar a pasta correta:

```bash
cd apps\back-fastapi
```

2. Em seguida, utilize esse comando para instalar as dependências:

```bash
pip install -r ....\requirements.txt
```

3. Logo depois, execute esse comando para que o back-end funcione:
  
```bash
uvicorn code.webapi.app:app --host 127.0.0.1 --port 8000 --reload
```

&emsp; **Para o front-end:**

1. Abra o terminal e execute o seguinte comando para acessar a pasta correta:
   
```bash
cd apps\front-next
```

2. Em seguida, utilize esse comando para instalar as dependências:

```bash
npm install
```

3. Logo depois, execute esse comando para que o front-end funcione:

```bash
npm run dev
```

4. Agora você poderá acessar o chatbot por meio do link: http://localhost:3000/

## Tags

**Sprint 1:**

- Pipeline de Processamento e Base de Dados
- Draft do Artigo
- Apresentação da SPRINT 1
  
**Sprint 2:**

- Fluxos Conversacionais e Classificação de Intenções 
- Versão 2 do Artigo
- Apresentação da SPRINT 2

**Sprint 3:**

- Respostas Contextuais e LLMS
- Versão 3 do Artigo
- Apresentação da SPRINT 3
  
**Sprint 4:**

- Gerenciamento de contexto e melhorias
- Primeira versão do artigo completo
- Apresentação da SPRINT 4

**Sprint 5:**

- Correções e Consolidação
- Demonstração do chatbot e Organização do repositório
- Artigo Final
- Apresentação Final


##  Licença

<p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/">
<a property="dct:title" rel="cc:attributionURL"> Grupo 4</a> by <a rel="cc:attributionURL dct:creator" property="cc:attributionName">Inteli, André Hutzler, Diogo Burgierman, Felipe Braga, Felipe Spina, Henrique Burle, Marina Ladeira, Pedro Auler, Raissa Paula, Curadobia</a> is licensed under <a href="https://creativecommons.org/licenses/by/4.0/" rel="license noopener noreferrer" style="display:inline-block;">Attribution 4.0 International</a>.
</p>

<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1">


**Contato:** Em caso de dúvidas ou sugestões, entre em contato com os integrantes do projeto ou com os professores orientadores.

</div>

