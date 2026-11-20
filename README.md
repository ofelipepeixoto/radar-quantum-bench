# Radar Quantum Bench

Planejamento de uma bancada de experimentos quânticos em português. A primeira versão permitirá a um professor rodar o mesmo circuito em duas condições, conferir quanto a distribuição de resultados mudou e entregar os dados a um colega para repetir a análise.

**Fase atual: planejamento do MVP.** Este repositório reúne o desenho do produto e os critérios para construir e validar o protótipo. As previsões numéricas do protocolo são teóricas. O próximo marco é obter o primeiro par de execuções do circuito de Bell em um simulador local.

## O primeiro experimento

A teoria prevê que um par de Bell medido na base Z devolva `00` ou `11`, cada um com probabilidade de 50%. Com 2% de erro independente de leitura por bit, a frequência teórica de bits iguais cai para 96,08%. O produto deverá mostrar a distribuição completa, as medições brutas, o tempo de execução e a incerteza. Cada frase numérica do relatório deverá levar ao dado que a sustenta.

## Documentação

| Para quem quer | Documento |
| --- | --- |
| Entender o produto, as entregas, a equipe e o custo | [Plano do MVP](docs/plano-do-mvp.md) |
| Implementar e validar Bell, GHZ e Bernstein-Vazirani | [Protocolo científico](docs/protocolo-cientifico.md) |
| Definir API, fila, dados e pacote de reprodução | [Arquitetura e contratos](docs/arquitetura.md) |
| Escolher bibliotecas, repositórios, APIs e sites oficiais | [Guia de integrações quânticas](docs/integracoes.md) |
| Desenhar as telas e conduzir o piloto com professores | [Piloto e telas](docs/piloto-e-telas.md) |
| Verificar os relatórios de IA e preparar a primeira versão | [Qualidade e liberação](docs/qualidade-e-release.md) |

A sequência proposta começa com Qiskit Aer no computador do laboratório. A primeira conexão física prevista é a IBM Quantum, depois que outra pessoa conseguir reproduzir uma comparação a partir do pacote exportado.
