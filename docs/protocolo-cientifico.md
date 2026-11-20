# Protocolo científico do Radar Quantum Bench

Especificação proposta para o MVP. A pergunta do primeiro ensaio é simples: quanto a distribuição de resultados de um circuito muda quando cada bit medido tem 2% de chance de ser lido ao contrário? As previsões abaixo servem para testar o software. As contagens e os tempos virão de execuções futuras.

## 1. Circuitos e referência ideal

Inicializar todos os qubits no estado zero. Medir os qubits de dados na base Z, cada `qᵢ` em `cᵢ`. Exibir os bits clássicos do maior índice para o menor. Assim, `110` significa `c₂=1`, `c₁=1` e `c₀=0`. Incluir zeros à esquerda. A convenção e o mapa físico após compilação devem acompanhar as contagens. [Ordem dos bits no Qiskit](https://quantum.cloud.ibm.com/docs/en/qiskit/bit-ordering)

| Circuito | Preparação e portas, em ordem | Bits medidos | Distribuição ideal |
| --- | --- | --- | --- |
| Bell | H em q₀. CX de q₀ para q₁. | q₀, q₁ | `00` e `11`, com 50% cada |
| GHZ | H em q₀. CX de q₀ para q₁. CX de q₁ para q₂. | q₀, q₁, q₂ | `000` e `111`, com 50% cada |
| Bernstein-Vazirani | X em q₃, seguido de H nos quatro qubits. Para o segredo `110`, aplicar CX de q₁ para q₃ e de q₂ para q₃. Aplicar H nos três qubits de dados. | q₀, q₁, q₂. q₃ é auxiliar. | `110`, com 100% |

Todos os demais resultados têm probabilidade ideal zero. O segredo de Bernstein-Vazirani foi escolhido para que uma inversão da ordem de leitura produza `011`, um erro fácil de detectar. As contagens de Bell e GHZ em Z verificam as distribuições previstas. Certificar emaranhamento exigiria medições complementares.

## 2. Duas condições no mesmo simulador

Compilar cada circuito uma vez e reutilizar a mesma versão nas duas condições. Fixar versão e método do simulador, semente de compilação, nível de otimização, máquina e número de threads. Na condição ideal, aplicar erro zero. Na condição com ruído, aplicar somente erro de leitura simétrico e independente a cada bit medido. A probabilidade de trocar 0 por 1 e a de trocar 1 por 0 valem ambas 0,02. O parâmetro descreve um cenário sintético. [Modelos de ruído e ReadoutError no Qiskit Aer](https://quantum.cloud.ibm.com/docs/en/qiskit/build-noise-models)

Para calcular a referência sem depender do simulador, partir da probabilidade ideal de cada palavra de bits. Se a palavra ideal é `x`, a observada é `y`, há `n` bits medidos e as duas palavras diferem em `d` posições, a probabilidade de observar `y` dado `x` é `e^d × (1−e)^(n−d)`. Multiplicar esse valor pela probabilidade ideal de `x` e somar sobre as palavras ideais. Para `e=0`, usar diretamente a distribuição ideal.

| Circuito | Distribuição prevista com e = 0,02 | Probabilidade de cair no conjunto ideal | Distância à distribuição ideal |
| --- | --- | ---: | ---: |
| Bell | Cada um de `00`, `11` tem probabilidade 0,4804. Cada um de `01`, `10` tem 0,0196. | 0,98² + 0,02² = **96,08%** | 0,0392 |
| GHZ | Cada um de `000`, `111` tem probabilidade 0,4706. Cada uma das outras seis palavras tem 0,0098. | 0,98³ + 0,02³ = **94,12%** | 0,0588 |
| Bernstein-Vazirani | `110` tem probabilidade 0,941192. Por palavra a distância de um, dois ou três bits do segredo, as probabilidades são 0,019208, 0,000392 e 0,000008, respectivamente. | 0,98³ = **94,1192%** | 0,058808 |

Em GHZ, uma troca nos três bits leva de `000` para `111` ou no sentido contrário. Ambos contam como resultado válido. No circuito com o segredo `110`, qualquer troca produz um resultado diferente do segredo.

## 3. Coleta e medição

1. Fazer uma execução de aquecimento por circuito e condição. Identificar os seis aquecimentos no registro e excluí-los das métricas.
2. Coletar 1.024 medições por repetição, dez repetições independentes por condição. Os três circuitos e as duas condições somam **60 execuções registradas e 61.440 medições**. Fixar previamente a lista de sementes de amostragem e usar uma semente distinta por circuito, condição e repetição. Preservar essa lista para a reprodução.
3. Alternar a ordem das condições entre pares de repetições. Registrar a ordem real. Para medir tempo, fixar a concorrência do ensaio em uma execução por vez.
4. Guardar por repetição as contagens inteiras por palavra, o número solicitado e o realizado de medições, a semente, o identificador do circuito e o resultado da execução. Identificar qualquer tentativa repetida após falha. Publicar o número de falhas e considerar apenas execuções completas e únicas no resumo. Marcar um ensaio com menos de dez repetições completas por condição como incompleto.
5. Medir duração com relógio monotônico. Separar tempo de fila, compilação e execução. Informar em milissegundos a mediana e o intervalo interquartil da execução por condição. Apresentar a compilação compartilhada uma única vez. Registrar qubits totais e medidos, profundidade e número de portas de dois qubits antes e depois da compilação. Identificar a máquina, versão do ambiente e número de threads ao apresentar tempos.

## 4. Métricas e limites de interpretação

**Taxa no conjunto ideal.** Somar as contagens das palavras de probabilidade ideal positiva e dividir pelas medições completas. Publicar numerador e denominador. Para cada circuito e condição, mostrar intervalo binomial de Wilson de 95% usando as 10.240 medições agrupadas, sob a hipótese de medições independentes e configuração constante. Preservar os resultados por repetição para identificar variação.

**Distância de variação total (TVD).** Calcular `0,5 × Σ |p_observada(y) − p_ideal(y)|` sobre todas as palavras de bits possíveis. Atribuir zero a palavras sem contagens. Zero significa distribuições iguais e um é a maior distância possível. A referência da tela de comparação é sempre a distribuição ideal. Para testar o simulador com ruído, usar separadamente a previsão analítica da seção 2. Uma amostra finita de Bell ou GHZ pode ter TVD positiva mesmo na condição ideal.

**Exemplo de leitura.** Se Bell devolvesse apenas `00`, sua taxa no conjunto ideal seria 100%, mas a TVD seria 0,5. O gráfico deve mostrar as duas métricas e as contagens. O intervalo de Wilson se aplica apenas à taxa de acerto. Os tempos medem a máquina que executa o simulador. Qualquer conclusão sobre hardware quântico exige outro ensaio, identificando dispositivo, data, calibração disponível e condições de execução. [Modo local e execução em hardware na IBM](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/local-testing-mode)

## 5. Ensaios de aceite

| Ensaio | Critério proposto |
| --- | --- |
| Referência independente | O cálculo analítico usa as fórmulas deste documento. As probabilidades somam 1 para os seis pares de circuito e condição. Para comparar números em ponto flutuante com a tabela, tolerar erro absoluto de até 10⁻¹². |
| Ordem dos bits | No modo ideal, todas as medições de Bernstein-Vazirani retornam `110`. O auxiliar fica ausente da palavra. Testar explicitamente o mapeamento de q₀ a c₀. |
| Contagens | Cada repetição válida soma 1.024 contagens inteiras e não negativas. No modo ideal, Bell e GHZ só produzem as palavras previstas. Suas duas contagens podem diferir entre si. |
| Métricas | Injetar as probabilidades exatas da tabela e recuperar as distâncias previstas. Um caso Bell com todas as contagens em `00` deve produzir taxa 1 e TVD 0,5. Comparar uma distribuição consigo mesma deve produzir TVD zero. |
| Amostragem | Para as 10.240 medições de cada combinação, conferir a frequência de cada palavra contra a previsão analítica correspondente. Fixar antes do ensaio o limite absoluto de 0,0235 por palavra. O limite usa a desigualdade de Hoeffding e uma correção conjunta para as 40 frequências verificadas nos seis pares. Sob o modelo independente, a probabilidade conjunta de falso alarme é no máximo 0,001. Guardar uma falha e investigá-la antes de repetir o teste. |
| Rastreabilidade | Recalcular taxas, TVD e totais a partir das contagens exportadas e obter os valores da interface antes do arredondamento. A reprodução deve carregar o manifesto com a mesma configuração e todas as sementes. Os tempos podem variar mesmo nesse ambiente. |

O manifesto mínimo contém revisão do protocolo, circuito original e compilado com seus hashes, mapa dos bits, definição e parâmetros do ruído, versões exatas do ambiente, identificador da imagem executável, sementes de compilação e amostragem, características da máquina e contagens por repetição. Cada número exibido no relatório deve apontar para a execução, o campo e a regra de cálculo que o produziram.
