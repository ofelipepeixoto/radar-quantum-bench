# Qualidade e liberação do piloto

Este documento define o que a equipe deverá demonstrar para liberar o Radar Quantum Bench. O repositório está na etapa de planejamento. Cada critério abaixo deverá receber um resultado, a versão avaliada e um link para a evidência quando houver implementação.

## Limites da simulação

O servidor aceitará os três circuitos versionados do catálogo, Bell, GHZ e Bernstein-Vazirani, com até quatro qubits. Cada comparação executará o mesmo circuito em duas condições, ideal e com ruído. Um *shot* corresponde a uma medição. Uma repetição corresponde a uma nova execução do circuito com o número de medições escolhido.

| Parâmetro | Padrão | Limite por comparação |
| --- | --- | --- |
| Shots por repetição e condição | 1.024 | Até 4.096 |
| Repetições por condição | 10 | Até 20 |
| Medições avaliadas nas duas condições, sem aquecimento | 20.480 | Até 163.840 |

O ensaio de referência utilizará a configuração padrão definida no [protocolo científico](protocolo-cientifico.md). Guardar outras configurações como experimentos distintos e aplicar o limite de recursos também ao aquecimento. Validar inteiros positivos, parâmetros permitidos e versão do modelo antes de criar o trabalho. Aceitar somente o corpo de requisição previsto. Começar o piloto com um trabalho ativo por executor. Medir tempo e memória no ambiente escolhido, registrar seus tetos antes do piloto e verificar o encerramento de trabalhos que os excedam. Limitar a fila e devolver uma resposta de capacidade esgotada que permita tentar depois.

## Roteiro de testes

| Caso | Como testar | Resultado exigido |
| --- | --- | --- |
| Referência científica | Para cada modelo, conferir a distribuição teórica com um cálculo independente. Incluir um caso com resultado assimétrico para detectar inversão de bits. Validar separadamente o modelo de ruído com parâmetros conhecidos. | Probabilidades somam 1. Ordem dos bits e valores coincidem com as referências dentro da tolerância numérica registrada. |
| Contagens e métricas | Alimentar o comparador com duas distribuições idênticas e duas com suportes disjuntos. Conferir soma das contagens por repetição. | A distância de variação total vale 0 e 1, respectivamente. As contagens são inteiros não negativos e somam os shots solicitados em cada repetição concluída. |
| Reexecução | Repetir um caso com as mesmas sementes, circuito compilado e ambiente fixado. Em seguida, mudar as sementes e conferir a variação com o protocolo estatístico documentado. | O primeiro caso reproduz as contagens no ambiente de referência. O segundo preserva as informações necessárias para avaliar a variação amostral. Tempo de execução é registrado em cada tentativa. |
| Entrada e falha parcial | Testar o valor máximo, um acima dele, valores fracionários e modelo desconhecido. Interromper o executor entre as duas condições e reenviar a mesma solicitação com a mesma chave. | Entrada inválida recebe erro antes da fila. O reenvio referencia o mesmo trabalho. Cada repetição preserva seu estado e resultados parciais aparecem como incompletos. |
| Exportação e acesso | Recalcular as métricas em outro processo a partir do pacote exportado. Alterar uma contagem em uma cópia. Na edição compartilhada, tentar ler ou exportar um experimento de outra equipe por ID. | O pacote válido reproduz os resultados. A cópia alterada falha na conferência de integridade. Somente membros autorizados têm acesso a resultados e exportações. |

Cada exportação deverá incluir manifesto com versão do formato, identificadores de experimento e execução, versões do circuito, simulador e dependências, ambiente, parâmetros de compilação e ruído, shots, sementes por repetição, ordem dos bits, contagens, tempos com unidades e versão das métricas. Incluir hashes SHA-256 dos arquivos no manifesto. Guardar o hash do manifesto junto ao registro da execução para permitir conferência por outra pessoa com acesso ao original.

## Relatório de IA

O programa calculará as métricas antes de chamar o modelo. O modelo receberá somente um conjunto de fatos autorizados da comparação. Cada fato terá um identificador, o valor, a unidade, a condição e a precisão de exibição. O gerador de texto terá acesso apenas de leitura a esses fatos. Disparar uma nova experiência exigirá uma ação do usuário na interface.

| Campos obrigatórios da resposta | Validação |
| --- | --- |
| `estado`, `resumo`, `observacoes`, `limitacoes`, `proximo_teste` | Validar esquema e tipos. `estado` admite `completo`, `parcial` ou `inconclusivo`. `proximo_teste` admite valor nulo. |
| `observacoes[].fato_ids`, `observacoes[].frase_id` | Aceitar somente fatos da comparação e frases compatíveis com eles. Preencher números e unidades no servidor. Verificar direção da diferença e precisão de exibição. |
| `resumo`, `limitacoes`, `proximo_teste` | Selecionar modelos de frase aprovados, com referências para toda afirmação factual. Em caso de dados insuficientes, informar a condição ou repetição ausente. Rotular a sugestão como hipótese. |

Registrar versão do modelo, do esquema e das instruções, IDs das evidências usadas e origem do texto exibido. Preparar casos sintéticos para números trocados, direção invertida, comparação parcial, alegação de resultado físico, indisponibilidade do modelo e texto de usuário que pareça dar ordens ao relator. Exigir zero afirmações factuais sem evidência no conjunto de aceite. Se faltar dado obrigatório, houver divergência ou a chamada expirar, exibir o resumo determinístico calculado dos fatos disponíveis, com a indicação de origem. Conferir que ainda seja possível exportar e repetir o experimento.

## Segurança e recuperação

Construir circuitos de um catálogo fechado e tratar rótulos como texto simples. No piloto local, restringir o serviço à interface de loopback e aceitar requisições de alteração apenas da origem autorizada. Em ambiente compartilhado, aplicar autenticação e conferir a equipe do usuário a cada leitura, exportação e escrita. O executor receberá somente o trabalho autorizado. Credenciais de serviços ficarão no gerenciador de segredos do ambiente, com acesso mínimo. Antes de publicar um artefato, conferir que logs, manifesto, relatórios e pacote de distribuição contenham apenas os dados previstos. Fixar as versões das dependências e identificar a imagem usada pelo digest. As referências de implementação são os guias de [validação de entrada](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html) e [gestão de segredos](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

Antes de cada atualização e diariamente durante o piloto, criar cópia consistente da base de metadados e dos artefatos referenciados. Em ambiente separado, restaurar uma cópia, abrir uma comparação conhecida, conferir os hashes e recalcular suas métricas. Registrar horário, tempo de recuperação e quantidade de trabalhos recuperados. Para reverter uma versão, pausar a entrada de trabalhos, preservar a cópia do estado atual e reativar a imagem anterior identificada pelo digest. Testar a compatibilidade entre a imagem e o esquema de dados. Se a mudança for incompatível, restaurar a cópia anterior em instância separada e reconciliar as execuções criadas desde a cópia antes de retomar a fila.

## Critérios para liberar uma versão

1. **Revisão do código.** Vincular commit, dependências, imagem, migração, contrato de métricas e versão do relator à versão candidata. Guardar o resultado dos testes de referência, validação de entradas e integração.
2. **Ensaio completo.** Outra pessoa deverá executar um dos três modelos, inspecionar as duas condições, baixar os dados e reproduzir as métricas. Repetir o ensaio com falha da IA e com uma execução interrompida.
3. **Decisão de piloto.** Bloquear a distribuição se o ensaio encontrar perda de contagens, acesso indevido, segredo exposto, métrica incorreta, afirmação sem evidência ou falha no teste de restauração. Registrar os critérios aprovados, pendentes, responsáveis e limitações conhecidas.
4. **Reversão.** Se um bloqueio aparecer durante o piloto, suspender novas execuções afetadas e seguir o procedimento de recuperação. Uma correção gera nova candidata. Repetir os testes do componente alterado e o ensaio completo antes de reabrir o piloto.

A revisão de cada artefato distribuído também precisa cumprir o [controle de exposição de componentes privados](protecao-do-produto.md). Incluir o resultado dessa revisão no aceite da versão candidata.
