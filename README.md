# Radar Quantum Bench

Bancada em português para comparar experimentos quânticos e conferir como cada número foi obtido. O catálogo executa Bell, GHZ e Bernstein-Vazirani em Qiskit Aer na CPU. Cada circuito é comparado sob leitura ideal e sob erro de leitura independente de 2% por bit.

## Rodar Bell

Na raiz do repositório, use Python 3.12 em Linux x86_64 ou WSL2 x86_64. O arquivo de dependências fixa as versões e os hashes dos pacotes binários testados. A instalação inicial exige acesso aos pacotes. A simulação e a conferência rodam localmente.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m radar_quantum_bench run --output resultado-bell.json
python -m radar_quantum_bench verify resultado-bell.json
python -m radar_quantum_bench pack resultado-bell.json reproducao-bell.zip
python -m radar_quantum_bench check-package reproducao-bell.zip
python -m unittest discover -s tests -v
```

O circuito usa H em q₀ e CX de q₀ para q₁. As duas condições usam o mesmo circuito compilado. Em cada condição, são dez repetições de 1.024 medições, com sementes distintas. Os dois aquecimentos ficam registrados separadamente. A ordem de exibição é `c1c0`. Após uma interrupção, execute o comando `run` com o mesmo arquivo e acrescente `--resume`. Cada tentativa fica no histórico. Para experimentar outra semente base, use `--seed` e um novo arquivo.

## Resultado da coleta de referência

| Condição | 00 | 01 | 10 | 11 | Bits iguais | IC de Wilson 95% | Distância à distribuição ideal |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Ideal | 5.065 | 0 | 0 | 5.175 | 100% | 99,96% a 100% | 0,005371 |
| Erro de leitura de 2% por bit | 4.878 | 188 | 199 | 4.975 | 96,22% | 95,83% a 96,57% | 0,037793 |

A teoria prevê 96,08% de bits iguais com esse ruído. A condição ideal prevê 50% para cada uma das palavras `00` e `11`. A diferença entre as frequências observadas de ambas explica a pequena distância positiva na primeira linha. A mediana do tempo de execução na máquina da coleta foi 0,659 ms no ideal e 0,828 ms com ruído. Esses tempos incluem a chamada local ao simulador e a recuperação das contagens.

O [JSON medido](examples/bell.json) inclui sementes, contagens por tentativa, referências teóricas, versões, circuitos OpenQASM, hashes e tempos. A coleta usou Qiskit 2.6.2, Aer 0.18.4 e semente base `20261120`. Para conferir as métricas da amostra basta a biblioteca padrão do Python:

```bash
python3.12 -m radar_quantum_bench verify examples/bell.json
```

O comando `pack` inclui as fontes, os testes, o arquivo de dependências, as medições, os circuitos e um guia de reprodução. Para comparar ambientes, confira primeiro o conteúdo e as versões, depois as contagens por semente. A coleta é uma simulação científica local na base Z.

## Catálogo de três circuitos

O segundo marco acrescenta GHZ e Bernstein-Vazirani. Na raiz do projeto, com o ambiente ativado, execute:

```bash
python -m radar_quantum_bench run --circuit ghz --output resultado-ghz.json
python -m radar_quantum_bench run --circuit bv --output resultado-bv.json
python -m radar_quantum_bench verify resultado-ghz.json
python -m radar_quantum_bench pack resultado-ghz.json reproducao-ghz.zip
```

São dez repetições de 1.024 medições em cada condição por circuito. Os seis conjuntos somam 61.440 medições avaliadas. Os seis aquecimentos são excluídos. O BV mede os três qubits de dados e usa um quarto qubit auxiliar. O resultado ideal é `110`, exibido na ordem `c2c1c0`. As sementes padrão diferem entre os circuitos.

| Circuito | Resultado no conjunto esperado, ideal | Resultado no conjunto esperado, com ruído | Previsão teórica com ruído |
| --- | ---: | ---: | ---: |
| Bell | 100% | 96,2207% | 96,08% |
| GHZ | 100% | 94,4629% | 94,12% |
| Bernstein-Vazirani | 100% | 94,4043% | 94,1192% |

A [coleta do catálogo](examples/catalogo) registra as contagens completas, os tempos, as versões e as sementes. O [registro do segundo marco](docs/marco-catalogo.md) informa o que foi verificado e o próximo trabalho previsto.

## Baixar os pacotes de reprodução

| Experimento | Pacote com código, testes, dados e guia |
| --- | --- |
| Bell, primeiro marco | [Radar-Quantum-Bench-Bell.zip](artifacts/Radar-Quantum-Bench-Bell.zip) |
| GHZ | [Radar-Quantum-Bench-GHZ.zip](artifacts/Radar-Quantum-Bench-GHZ.zip) |
| Bernstein-Vazirani | [Radar-Quantum-Bench-BV.zip](artifacts/Radar-Quantum-Bench-BV.zip) |

O ZIP de Bell preserva exatamente a versão entregue no primeiro marco. Os novos pacotes incluem a amostra Bell antiga para conferir compatibilidade. Os [SHA-256 publicados](artifacts/SHA256SUMS) permitem conferir os downloads:

```bash
cd artifacts
sha256sum -c SHA256SUMS
```

Resultados novos usam o formato 2. O verificador também lê o formato 1 de Bell. A revisão do catálogo fixa os circuitos OpenQASM e a compilação de referência na versão testada. Uma mudança de compilador passa por atualização explícita dessa referência. Uma coleta interrompida só é retomada pelas mesmas fontes e pelo mesmo ambiente que a iniciaram.

## Documentação

| Para quem quer | Documento |
| --- | --- |
| Entender o produto, as entregas, a equipe e o custo | [Plano do MVP](docs/plano-do-mvp.md) |
| Implementar e validar Bell, GHZ e Bernstein-Vazirani | [Protocolo científico](docs/protocolo-cientifico.md) |
| Definir API, fila, dados e pacote de reprodução | [Arquitetura e contratos](docs/arquitetura.md) |
| Escolher bibliotecas, repositórios, APIs e sites oficiais | [Guia de integrações quânticas](docs/integracoes.md) |
| Avaliar licenças, dependências e a necessidade de manter um fork | [Projetos existentes e decisões de reuso](docs/reuso-e-forks.md) |
| Planejar os 12 produtos e escolher qual oportunidade testar depois do Bench | [Plano paralelo do ecossistema](docs/ecossistema-quantico.md) |
| Desenhar as telas e conduzir o piloto com professores | [Piloto e telas](docs/piloto-e-telas.md) |
| Proteger componentes privados e definir o que bloqueia a publicação | [Proteção do produto](docs/protecao-do-produto.md) |
| Verificar os relatórios de IA e preparar a primeira versão | [Qualidade e liberação](docs/qualidade-e-release.md) |

As três comparações já rodam localmente. O próximo marco integra a execução a uma API local com fila, histórico e exportação. A conexão física prevista é a IBM Quantum após a validação do piloto.

## Começar o trabalho

A [tarefa do primeiro marco](https://github.com/ofelipepeixoto/radar-quantum-bench/issues/1) descreve o par de execuções de Bell e o que deve ser conferido no arquivo de contagens. A [tarefa de descoberta do ecossistema](https://github.com/ofelipepeixoto/radar-quantum-bench/issues/2) acompanha a escolha da próxima hipótese depois do piloto. O [bloqueio de publicação por exposição de ativos reservados](https://github.com/ofelipepeixoto/radar-quantum-bench/issues/3) tem critérios de implementação e de teste próprios.
