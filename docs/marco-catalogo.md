# Segundo marco do Radar Quantum Bench

Implementado a partir da main 9d99881dc8d99e29093dcb9a3e3f57733f06321c. A PR de Bell já estava incorporada. Esta entrega acrescenta GHZ e Bernstein-Vazirani ao executor, ao comparador de métricas e aos pacotes de reprodução.

## Condições e coleta

O ambiente usado foi Python 3.12.14, Qiskit 2.6.2 e Aer 0.18.4 em Linux x86_64, com CPU e uma thread. Foram dez repetições de 1.024 medições por condição e por circuito. Os seis aquecimentos ficaram fora do resumo. O GHZ usa H em q0, CX q0 para q1 e CX q1 para q2. O BV usa segredo 110, três dados medidos e um auxiliar. A compilação é reutilizada nas duas condições de cada circuito.

| Circuito | Semente base | Ideal, contagens de maior probabilidade | Com ruído, leituras no conjunto esperado |
| --- | ---: | --- | ---: |
| Bell | 20261120 | 00 = 5.065 e 11 = 5.175 | 9.853 de 10.240, ou 96,2207% |
| GHZ | 20261220 | 000 = 5.135 e 111 = 5.105 | 9.673 de 10.240, ou 94,4629% |
| Bernstein-Vazirani | 20261320 | 110 = 10.240 | 9.667 de 10.240, ou 94,4043% |

Cada repetição soma 1.024 contagens. As frequências de todas as palavras passaram pela tolerância pré-definida de 0,0235 em relação à referência analítica. Os arquivos completos estão em [Bell](../examples/catalogo/bell.json), [GHZ](../examples/catalogo/ghz.json) e [Bernstein-Vazirani](../examples/catalogo/bv.json). Os tempos registrados medem a chamada local ao simulador e a recuperação das contagens. Os gráficos e o piloto com laboratórios serão construídos nos próximos marcos.

## Verificações da entrega

A suíte local tem 33 testes. Ela cobre referência independente, mapeamento de bits, contagem e suporte do circuito ideal, amostras com ruído, intervalos, histórico de tentativas, interrupção e retomada, campos JSON duplicados, contagens inválidas e troca de circuitos entre arquivos. A verificação dos pacotes confere inventário, hashes, fontes, circuitos, métricas e a amostra legada. Os testes usam apenas dados de simulação.

Os ZIPs novos incluem o guia e todos os arquivos de que sua suíte depende. Cada um foi extraído numa pasta temporária limpa, e o comando de testes documentado foi executado dessa pasta. As 20 repetições de GHZ e as 20 de BV foram reexecutadas com as sementes publicadas e produziram as mesmas contagens. O verificador da nova versão também aprovou o pacote Bell original. A execução automática no GitHub repete os testes e as verificações dos pacotes.

O [ZIP original de Bell](../artifacts/Radar-Quantum-Bench-Bell.zip) tem 24.280 bytes e SHA-256 aa9c5b4ed43adadca2712d2580ab21c2159ba43bac49daae1c10adcf30a48288. O registro de todos os pacotes está em [SHA256SUMS](../artifacts/SHA256SUMS).

## Próxima entrega preparada

O próximo trabalho é integrar o executor a uma API local. A entrada deverá aceitar um circuito do catálogo, registrar uma chave de idempotência e devolver o ID para acompanhamento. SQLite guardará o trabalho, as tentativas e o vínculo com os artefatos. O aceite inclui reabrir um trabalho após reinício e repetir apenas uma condição interrompida, sem duplicar contagens. [Arquitetura prevista](arquitetura.md)
