# Testar o Radar Quantum Bench no WSL

Você vai rodar o simulador na CPU do seu PC e abrir a bancada no navegador do Windows. O primeiro teste compara o circuito de Bell em duas condições e gera um pacote ZIP com os resultados.

## 1. Abrir o Ubuntu e conferir o ambiente

No **PowerShell do Windows**, confira se a distribuição Ubuntu aparece com a versão **2** na coluna VERSION.

```powershell
wsl --list --verbose
```

Abra o **Ubuntu** pelo menu Iniciar. Os próximos comandos são para o terminal Ubuntu. Confira a arquitetura e instale as ferramentas de preparação do sistema.

```bash
uname -m
sudo apt update
sudo apt install -y ca-certificates curl git python3-venv
```

Os hashes das dependências científicas foram fixados para Linux `x86_64` e Python 3.12. Essa é a arquitetura esperada na primeira linha. A instalação inicial precisa de internet. [Ambiente Python no Ubuntu](https://documentation.ubuntu.com/ubuntu-for-developers/howto/python-setup/)

Confira o Node e o npm **nesse mesmo terminal**.

```bash
node -p "process.platform + ' ' + process.version"
npm --version
```

A primeira saída deve começar com `linux`. O projeto aceita Node 22.23.4 ou superior e npm 9.6.5 ou superior. Node 24 LTS é uma boa escolha e a versão 24.19 atende. Se o comando faltar ou mostrar `win32`, escolha Linux no guia do Node, instale no Ubuntu e repita a verificação. [Download oficial do Node.js](https://nodejs.org/pt/download)

## 2. Obter o projeto

**Primeira instalação.** Os comandos usam a pasta pessoal do Ubuntu para os arquivos do projeto.

```bash
mkdir -p ~/projetos
cd ~/projetos
git clone https://github.com/ofelipepeixoto/radar-quantum-bench.git
cd radar-quantum-bench
```

**Se você já tem uma cópia**, entre nela e veja o estado atual. Nos passos seguintes, substitua `~/projetos/radar-quantum-bench` pelo caminho da sua cópia se for diferente.

```bash
cd ~/projetos/radar-quantum-bench
git status --short --branch
```

Se estiver em `main` e a saída mostrar apenas a linha do nome da branch, atualize com `git pull --ff-only`. Se aparecerem arquivos alterados, outra branch ou um aviso de histórico divergente, preserve sua cópia. Para testar a versão pública em separado, use outra pasta de destino no comando de clone.

## 3. Preparar o Python e testar a API

Na raiz do projeto, instale o `uv` em um ambiente só para ferramentas. O Python 3.14 que acompanha o Ubuntu 26 pode continuar atendendo o sistema. O `uv` usa ou baixa Python 3.12 para a bancada e instala o pip no ambiente do projeto. [Instalação do uv](https://docs.astral.sh/uv/getting-started/installation/) · [Versões do Python com uv](https://docs.astral.sh/uv/guides/install-python/)

```bash
python3 -m venv ~/.venvs/radar-tools
~/.venvs/radar-tools/bin/python -m pip install uv
if [ ! -e .venv ]; then
  ~/.venvs/radar-tools/bin/uv venv --python 3.12 --seed .venv
fi
source .venv/bin/activate
python --version
```

Confirme `Python 3.12.x`. Se já existia uma `.venv` de outra versão, use uma cópia nova do projeto para conservar o ambiente anterior. Com o ambiente correto ativo, rode os comandos a seguir.

```bash
python -m pip install --require-hashes -r requirements-api.txt
python -m pip check
python -m unittest discover -s tests -v
```

O arquivo da API inclui Qiskit 2.6.2 e Qiskit Aer 0.18.4 nesta versão do projeto. Espere `OK` ao fim dos testes.

## 4. Construir a interface

Execute estes comandos na raiz do projeto.

```bash
npm --prefix web ci
npm --prefix web run check
npm --prefix web run build
test -s web/dist/index.html && echo "Interface pronta"
```

O servidor Python vai servir o conteúdo de `web/dist`. Para usar a bancada compilada, os dois processos abaixo são suficientes.

## 5. Iniciar o servidor e o executor

**Terminal 1 do Ubuntu, servidor.** Deixe esta aba aberta.

```bash
cd ~/projetos/radar-quantum-bench
source .venv/bin/activate
python -m radar_quantum_bench.local serve --data-dir "$PWD/local-data"
```

**Terminal 2 do Ubuntu, executor.** Abra uma segunda aba do Ubuntu e deixe este processo rodando. Os dois terminais devem apontar para o mesmo diretório de dados.

```bash
cd ~/projetos/radar-quantum-bench
source .venv/bin/activate
python -m radar_quantum_bench.local worker --data-dir "$PWD/local-data"
```

O executor aplica por padrão 120 segundos por comparação e 2.048 MiB de memória virtual. O [registro da candidata](marco-candidata.md) explica os ajustes e os recibos operacionais. Se o prazo for excedido, os checkpoints válidos permitem retomar o trabalho.

## 6. Fazer a primeira comparação

1. No Chrome ou Edge do **Windows**, abra [a bancada em localhost](http://localhost:8000/).
2. Selecione **Bell** e clique em **Executar comparação**. O trabalho passa pela fila e as duas condições aparecem na tela.
3. Ao concluir, confira as contagens e as métricas. O ensaio completo tem **20.480 medições**, metade em cada condição. Na leitura ideal aparecem apenas `00` e `11`. Com erro de leitura de 2% por bit, a previsão para a soma de `00` e `11` é **96,08%**. A fração observada varia com a amostra.
4. Em **Leitura dos resultados**, confira o resumo local e abra **Conferir as evidências**. Baixe o relatório em Markdown ou JSON. Esse percurso dispensa modelo de IA. O [guia do relator](relatorios-locais.md) explica a opção de modelo local.
5. Clique em **Baixar pacote ZIP**. Recarregue a página e confira que a comparação permanece disponível no histórico.

**Para parar**, aguarde a conclusão do trabalho, se possível, e use `Ctrl+C` no executor e no servidor. **Para reabrir**, repita o passo 5 e use o mesmo endereço no navegador. O banco e as execuções ficam em `local-data`; mantenha essa pasta para conservar o histórico.

**Para atualizar**, pare os dois processos, confira `git status --short --branch` e atualize uma `main` limpa com `git pull --ff-only`. Ative a mesma `.venv`, instale novamente `requirements-api.txt`, repita o passo 4 e reinicie os processos do passo 5 com o diretório de dados original.

## Se algum passo falhar

| O que você vê | O que conferir |
| --- | --- |
| Porta 8000 ocupada | Inicie o servidor com `python -m radar_quantum_bench.local serve --data-dir "$PWD/local-data" --port 8001`. Abra `http://localhost:8001/` no Windows. O comando do executor é o mesmo. |
| O trabalho continua na fila | Confira se o terminal do executor está aberto e se os dois processos receberam o mesmo caminho em `--data-dir`. Deixe um único executor ativo nesse diretório. |
| O navegador não abre a bancada | No Ubuntu, teste `curl -fsS http://127.0.0.1:8000/health`, ajustando a porta se necessário. O servidor deve responder com `status` igual a `ok`. Se responder, tente também `http://127.0.0.1:8000/` no navegador do Windows. |
| A API responde, mas a interface pede o build | Na raiz, repita o passo 4 e reinicie o servidor para que ele carregue `web/dist`. |
| O Python informa `No module named` | Entre na raiz, ative a `.venv`, confira `python --version` e repita a instalação do passo 3. O comando `which python` deve apontar para `.venv/bin/python`. |
| O pip não encontra uma wheel do Aer ou rejeita o hash | Confira `uname -m`, `python --version` e `python -m pip --version`. Este conjunto de pacotes foi fixado para Linux x86_64 com CPython 3.12. Em outra arquitetura, a instalação precisa de um conjunto de pacotes e hashes próprio. |

## Teste opcional do navegador

Com a interface já compilada, rode estes comandos em outra aba Ubuntu. O Playwright inicia serviços temporários na porta 8765. O teste usa uma pasta própria para preservar seu histórico.

```bash
cd ~/projetos/radar-quantum-bench
source .venv/bin/activate
cd web
npx playwright install --with-deps chromium
npm run test:e2e
```

O primeiro comando do Playwright pode pedir a senha do Ubuntu para instalar bibliotecas do navegador. Se a porta dos testes estiver ocupada, use `RQB_E2E_PORT=8766 npm run test:e2e`. [Instalação de navegadores do Playwright](https://playwright.dev/docs/browsers#install-browsers)
