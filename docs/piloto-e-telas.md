# Radar Quantum Bench | Telas e piloto com laboratórios

O primeiro uso está completo quando uma pessoa consegue comparar um circuito em condições ideais e com ruído, explicar uma diferença observada e entregar a outra pessoa os dados para conferir a conclusão. O teste se destina a professores, estudantes de pós-graduação e pesquisadores que hoje fazem essa tarefa em notebooks e planilhas.

## Da pergunta ao resultado

| Tela | O que a pessoa vê e faz | Como verificar |
|---|---|---|
| Experimentos | Escolhe uma das três perguntas do catálogo. Cada cartão traz o circuito, o que ele mede e a distribuição teórica esperada. | Uma pessoa nova consegue descrever com as próprias palavras o que vai comparar. |
| Nova comparação | Confere o circuito escolhido, o modelo de ruído e o número de medições por repetição (*shots*). Um resumo mostra quais condições são iguais nos dois casos. Sementes, parâmetros de ruído e repetições ficam nos detalhes. | O formulário explica valores inválidos junto ao campo, mantém os demais valores e permite revisar a configuração antes de executar. |
| Execução | Acompanha as condições “Ideal” e “Com ruído”, cada uma com seu próprio estado. A página mostra o identificador da comparação e permite voltar ao histórico durante o processamento. | Reabrir a comparação recupera seu estado. Uma atualização de página ou um segundo clique durante o envio preserva o mesmo pedido. |
| Comparação e relatório | Compara teoria, ideal e com ruído no mesmo eixo. Pode trocar o gráfico por uma tabela, abrir as contagens por repetição e seguir cada afirmação numérica do relatório até a métrica que a sustenta. | A soma das contagens corresponde às medições concluídas em cada repetição. O leitor identifica a condição, a unidade e o denominador de cada valor. |
| Histórico e reprodução | Encontra o experimento por nome, data ou identificador. Pode exportar os dados, repetir a configuração com as sementes registradas ou criar uma cópia com novas sementes. | A nova execução ganha identificador próprio e aponta para a comparação original. O histórico preserva ambas. |

Por exemplo, para um par de Bell medido na base computacional, o cartão pode perguntar “Com que frequência os dois bits medidos são iguais?”. O comparador mostra os quatro resultados, inclusive os que tiverem contagem zero. A teoria prevê 50% para 00 e 50% para 11 no circuito ideal. As frequências de uma amostra podem diferir desses valores. A tela informa o número de medições e mantém essa distinção ao apresentar o efeito do ruído.

## Estados que precisam de desenho

| Situação | Comportamento esperado |
|---|---|
| Primeiro acesso | O catálogo é o ponto de partida. No histórico vazio, a ação disponível é “Escolher experimento”. |
| Em fila ou em execução | Mostrar o estado de cada condição. Tempo em fila e tempo de execução têm rótulos e unidades separados. Exibir previsão de término só depois que houver uma estimativa validada. |
| Conexão interrompida | Informar que a atualização da tela foi interrompida, manter o identificador e oferecer “Consultar andamento”. A consulta recupera o estado existente. |
| Uma condição falhou | Preservar os dados da condição concluída. Oferecer nova tentativa da condição pendente com a mesma configuração e registrar a tentativa. Aguardar o par completo para a conclusão comparativa. |
| Incompatibilidade | Se o circuito, o número de medições ou outro parâmetro que deveria permanecer igual divergir, exibir os valores lado a lado e pedir uma execução pareada antes de atribuir diferenças ao ruído. |
| Relatório de IA indisponível | Entregar as contagens, as métricas e a exportação. Oferecer “Gerar explicação novamente” sem executar o circuito outra vez. |
| Resultado completo | Oferecer “Conferir os dados” e “Exportar”. Registrar no pacote a versão do circuito, o simulador, os parâmetros, as sementes e os resultados brutos. |

## Aceite de acessibilidade

- Percorrer o caminho do catálogo à exportação só com teclado. A ordem do foco acompanha a leitura, o foco continua visível e o fechamento de um painel devolve o foco ao controle que o abriu.
- Fazer uma leitura com leitor de tela em português. Os campos têm rótulos, os erros indicam a correção e as mudanças de estado são anunciadas uma vez por transição, sem mover o foco.
- Testar a ampliação de 200% e uma largura de 320 pixels CSS. Texto, ações e mensagens devem permanecer acessíveis. Quando uma tabela precisar de rolagem horizontal, limitar a rolagem à sua região e identificá-la com um título.
- Conferir contraste de pelo menos 4,5:1 para texto normal e 3:1 para texto grande. Combinar cor com rótulo ou padrão para distinguir as séries. Evitar depender do ponteiro para revelar um número.
- Disponibilizar uma tabela junto de cada gráfico, com a mesma ordem de resultados, unidades, valores e denominadores. A explicação de incerteza deve ser acessível junto à métrica.

Os testes manuais complementam a verificação automática. Registrar a tarefa, o dispositivo, o navegador, o recurso de acessibilidade, o resultado e uma evidência de cada falha. [Referência de acessibilidade da W3C](https://www.w3.org/WAI/WCAG22/quickref/)

## Piloto pareado com o notebook habitual

**Pergunta.** A plataforma reduz o esforço para produzir e conferir uma comparação, mantendo a interpretação correta? Recrutar cinco participantes de dois laboratórios com diferentes níveis de experiência. Pedir que tenham acesso a um notebook que já usem para essa finalidade. Registrar familiaridade e frequência de uso de cada ferramenta.

1. **Preparar duas tarefas equivalentes.** Usar o mesmo circuito, número de medições, repetições, modelo de ruído, pergunta e formato de entrega. Preparar duas listas fixas de sementes, A e B. Fornecer os mesmos insumos e a mesma definição da métrica nos dois métodos. Salvar uma referência para cada lista.
2. **Alternar a ordem.** Três pessoas começam no notebook e duas na plataforma. Distribuir A e B entre as ordens para que cada lista apareça nos dois métodos. Cada pessoa realiza uma tarefa por método. Anotar a ordem e qualquer ajuda recebida.
3. **Cronometrar a tarefa inteira.** Começar com ambos os ambientes disponíveis e a leitura do enunciado concluída. Encerrar quando houver um pacote ou arquivo compartilhável com a configuração, as contagens e uma interpretação. Registrar interrupções, tempo de execução do simulador e tempo total. Usar o mesmo computador para as duas tarefas de cada participante.
4. **Verificar a compreensão.** Pedir que a pessoa aponte um valor medido, o valor teórico correspondente e uma limitação da conclusão. Registrar se ela consegue distinguir flutuação amostral de uma diferença observada entre condições.
5. **Entregar o material a um colega.** Sem instruções orais do autor, o colega deve identificar a configuração e recalcular uma métrica a partir das contagens exportadas. Confrontar o cálculo com a precisão publicada. Como teste separado, o colega deve conseguir iniciar uma nova execução com o manifesto e identificar as sementes e versões utilizadas.

| Evidência | Critério proposto para o primeiro piloto |
|---|---|
| Conclusão sem ajuda | Pelo menos quatro de cinco participantes exportam uma comparação em até dez minutos na plataforma, sem intervenção do facilitador. |
| Esforço relativo | Registrar a diferença de tempo por pessoa e a mediana das diferenças. Uma mediana favorável à plataforma justifica repetir o teste com mais laboratórios. |
| Interpretação | Pelo menos quatro de cinco identificam corretamente a referência teórica, a medida observada e sua limitação. |
| Conferência independente | Cada pacote exportado na plataforma no piloto permite ao colega recalcular a métrica escolhida dentro do arredondamento exibido. Uma discrepância bloqueia o aceite de rastreabilidade. |
| Interesse em continuar | Procurar pelo menos um laboratório disposto a repetir o uso com uma turma ou projeto real, com responsável, data e autorização para discutir o custo. |

Esses números são metas de decisão. Registrar os cinco resultados individuais e suas limitações. Uma amostra desse tamanho orienta a próxima mudança no produto. Para estimar o efeito com maior precisão, será preciso repetir a comparação com mais participantes.

## Perguntas para a entrevista

**Antes da tarefa**

1. Quando foi a última vez que você explicou ou refez um experimento quântico de outra pessoa? Mostre o material que recebeu, se puder.
2. Onde estavam os parâmetros, as versões, as contagens e a explicação? Quanto tempo levou para encontrar o necessário?
3. Quem precisava conferir o resultado, o que pediu para ver e como a equipe soube que a entrega estava concluída?

**Depois da tarefa**

1. Qual conclusão você tiraria destes resultados? Em qual número se baseou?
2. Se a comparação fosse enviada para uma pessoa nova amanhã, o que ainda faltaria para ela conseguir conferir o trabalho?
3. Em qual atividade real você usaria o produto nas próximas semanas? Quem mais precisaria participar?
4. Qual parte do processo atual seria substituída? Quem avaliaria uma licença, com qual verba e em que período a decisão costuma acontecer?

## Hipótese comercial e decisão

A hipótese inicial é uma licença por laboratório ou turma, incluindo histórico, comparações e exportação para os participantes. O provável comprador é o coordenador do laboratório ou o professor responsável pela disciplina. Na entrevista, identificar também quem aprova gastos. Depois da demonstração, oferecer um piloto de duração e preço definidos para uma atividade que o participante já tenha no calendário. Registrar a proposta, a decisão e o motivo. Usar custos medidos e orçamento declarado para formular o preço a testar.

Se a equipe obtiver bons resultados técnicos e ninguém assumir um próximo uso concreto, revisar a escolha do comprador e o problema que vale pagar para resolver. Se houver demanda, mas a conferência das métricas falhar, corrigir a exportação e repetir essa etapa antes de ampliar o piloto.
