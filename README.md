# Radar Quantum Bench

Bancada em português para comparar experimentos quânticos e conferir como cada número foi obtido. O primeiro marco executa o circuito de Bell em Qiskit Aer na CPU, uma vez com leitura ideal e outra com erro de leitura independente de 2% por bit. GHZ e Bernstein-Vazirani continuam no plano.

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

A comparação de Bell já roda localmente. O próximo marco científico acrescenta GHZ e Bernstein-Vazirani ao mesmo protocolo. A conexão física prevista é a IBM Quantum após a validação do piloto.

## Começar o trabalho

A [tarefa do primeiro marco](https://github.com/ofelipepeixoto/radar-quantum-bench/issues/1) descreve o par de execuções de Bell e o que deve ser conferido no arquivo de contagens. A [tarefa de descoberta do ecossistema](https://github.com/ofelipepeixoto/radar-quantum-bench/issues/2) acompanha a escolha da próxima hipótese depois do piloto. O [bloqueio de publicação por exposição de ativos reservados](https://github.com/ofelipepeixoto/radar-quantum-bench/issues/3) tem critérios de implementação e de teste próprios.
