# Plano de construção do Radar Quantum Bench

**Decisão de produto.** Construir primeiro uma bancada local de comparação para professores e laboratórios de computação quântica. A primeira promessa é concreta: um pesquisador roda duas condições, outra pessoa abre o pacote e confere os números sem pedir o notebook original. O tempo para chegar a essa entrega e a capacidade de reproduzi-la vão orientar a decisão comercial.

**Estágio em 20/11/2026.** Planejamento inicial. Os prazos, custos e metas a seguir são premissas para o piloto. O protocolo já define o que deverá ser medido. Os resultados do software dependerão da implementação.

## Entrega da primeira versão

| Necessidade | Entrega proposta | Evidência exigida |
| --- | --- | --- |
| Começar sem configurar um notebook | Catálogo com os experimentos Bell, GHZ e Bernstein-Vazirani, instruções em português e configurações padrão | Um novo usuário escolhe o circuito e inicia a comparação |
| Isolar uma diferença entre condições | Um circuito compilado por experimento, com leitura ideal ou com 2% de erro de leitura independente por bit | Mapa dos bits, sementes e perfis anotados, mesmas portas nas duas condições |
| Conferir o efeito e seu custo | Distribuições completas, taxa de resultados no conjunto ideal, distância entre distribuições, tempos e recursos | Todos os pontos dos gráficos possuem unidade, denominador e tabela acessível |
| Reproduzir uma conclusão | Histórico, repetição com a mesma semente e exportação legível fora do aplicativo | Um colega recalcula as métricas a partir das contagens brutas e do manifesto |
| Usar IA para interpretar | Explicação em português com referência a cada métrica e, se os dados permitirem, sugestão de próximo teste | Validador confere valores, unidades e direção da mudança. Se a IA falhar, o resultado continua disponível |

Cada circuito terá dez repetições de 1.024 medições por condição. São três circuitos, duas condições, 60 execuções e 61.440 medições avaliadas. Seis execuções de aquecimento ficam identificadas separadamente. Tempos e memória serão medidos na máquina utilizada. A criação de circuitos livres, o serviço compartilhado entre instituições e os testes em equipamentos físicos ficam para uma versão posterior.

## Quem será responsável

Planejar um desenvolvedor de dedicação principal, um revisor com formação em computação quântica para a referência e um professor parceiro para testar o fluxo. A mesma pessoa pode conduzir produto e entrevistas. Revisão física dos circuitos e conferência independente de um pacote precisam de uma segunda pessoa. Recrutar os parceiros durante a primeira semana para que a agenda acadêmica não impeça o piloto.

## Sequência de construção

Estimativa de seis semanas com equipamento disponível e acesso aos participantes. O trabalho segue em partes revisáveis, cada uma com uma entrega que se consegue abrir ou conferir.

| Semana | Entrega e responsável principal | Dependência | Como encerrar |
| --- | --- | --- | --- |
| 1 | Produto entrevista dois professores. Engenharia decompõe Bell e o revisor calcula com papel ou código independente a distribuição esperada. Preparar ambiente Python compatível e versões travadas. | Computador e revisor | Primeira comparação Bell roda pela linha de comando. Confere bits, soma de shots e contagens exportadas. |
| 2 | Engenharia acrescenta GHZ e Bernstein-Vazirani, gerador de sementes, cronômetro, métricas e testes analíticos. | Referência Bell validada | A bateria dos três circuitos produz 60 repetições medidas e dados para o revisor aplicar as tolerâncias publicadas. |
| 3 | Engenharia integra API local, fila SQLite, recuperação após interrupção, histórico e exportação versionada. | Modelo das contagens estável | Submeter duas vezes a mesma chave preserva a comparação. Em diretório limpo, validar o pacote e recalcular duas métricas. |
| 4 | Produto e engenharia entregam catálogo, configuração, andamento e comparação em Astro. Testar navegação, tela estreita, erros e estados parciais. | API e pacote disponíveis | Concluir o fluxo pelo teclado e por leitor de tela, exportando o mesmo conteúdo mostrado no gráfico. |
| 5 | Engenharia liga o relator de IA opcional, testa o resumo local, restauração, limites e distribuição do piloto. Revisor confere versão candidata. | Métricas e interface estáveis | Pacote íntegro em outra máquina, relatório rastreável, recuperação validada após falha e acesso local verificado. |
| 6 | Produto conduz sessões com cinco pessoas em dois laboratórios. Revisor e professor avaliam interpretação, reprodução e interesse em usar de novo. | Versão candidata aceita, horários combinados | Relatório das cinco sessões, comparação com o notebook habitual e decisão registrada sobre prosseguir, corrigir ou encerrar. |

**Primeira tarefa pronta para desenvolvimento.** Implementar Bell com entrada fixa no catálogo, saída em contagens e exportação JSON. Usar apenas Qiskit e Aer localmente. O ensaio deve devolver sempre bits iguais em condições ideais e convergir para a referência de 96,08% com o perfil sintético. O teste verifica também a distribuição completa e a tolerância pré-definida no [protocolo](protocolo-cientifico.md). Essa entrega já permite revisar a parte científica antes de investir nas telas.

## Orçamento e operação

| Item | Premissa para planejar | Como controlar |
| --- | --- | --- |
| Engenharia e produto | Estimativa inicial de 22 a 28 dias de trabalho, distribuídos pelas seis semanas | Registrar esforço por entrega. Reestimar depois do primeiro pacote reproduzível. |
| Revisão científica e sessões | Reservar 2 a 4 dias de especialista, mais a disponibilidade dos participantes | Marcar revisões nas semanas 1, 2 e 5. Confirmar agenda do piloto na semana 1. |
| Simulação local | Com equipamento existente, a configuração proposta dispensa nova contratação de serviço quântico | Medir tempo, memória e concorrência disponíveis. Energia, manutenção e trabalho da equipe compõem o custo. |
| Explicação por IA | Resumo determinístico incluído. Um modelo remoto é opcional por instalação | Estimar chamadas × custo de entrada e saída por chamada, incluindo retentativas. Fixar teto e bloquear chamadas adicionais ao atingi-lo. |
| Demonstração e hardware | Uma página estática com exemplos autorizados pode ser publicada depois. O primeiro teste em QPU terá orçamento próprio | Confirmar quota e forma de cobrança do fornecedor no dia. Informar custo previsto e exigir envio explícito do trabalho. |

Para estimar a proposta comercial de um laboratório, somar dias por função multiplicados pelas diárias acordadas, infraestrutura adicional, horas de suporte e custo observado do relator. Levantar orçamento e responsável pela compra na entrevista. O primeiro modelo a testar é uma licença por laboratório ou por turma com suporte à instalação e à reprodução.

## Decisão após o piloto

Prosseguir para uma segunda turma se pelo menos quatro das cinco pessoas exportarem em até dez minutos sem ajuda, quatro explicarem corretamente teoria e resultado, todos os pacotes entregues puderem ser conferidos por um colega e um laboratório indicar responsável e atividade real para uma segunda rodada. Registrar também a diferença de tempo por pessoa em relação ao notebook. Corrigir qualquer divergência nas métricas antes de ampliar acesso. Se a ferramenta passar nos testes técnicos e ninguém aceitar uma segunda rodada, investigar quem de fato paga e qual etapa da rotina ainda custa tempo.

| Risco concreto | Sinal no piloto | Resposta planejada |
| --- | --- | --- |
| Contagem correta na ordem errada dos bits | O algoritmo de segredo conhecido devolve `011` para `110` | Conferir a conversão no adaptador e repetir o aceite das seis combinações |
| Comparação contaminada por carga da máquina | Tempos mudam entre repetições mesmo com o circuito fixo | Rodar sequencialmente, registrar recursos, exibir mediana e intervalo interquartil |
| Dependência de uma biblioteca ou provedor | Atualização altera o formato da saída ou impede a instalação | Fixar ambiente verificado, isolar o adaptador e testar o mesmo pacote antes de atualizar |
| IA atribui a diferença a uma causa que o ensaio não mede | Uma frase não aponta para observação compatível | Oferecer o resumo local, revisar a regra e repetir os casos de aceite do relator |
| Piloto difícil de repetir no laboratório | O colega precisa do autor para interpretar o pacote | Observar onde ele parou e corrigir manifesto, exportação ou instruções antes de vender |
| Resultado interpretado como vantagem quântica | Comparação local é apresentada como desempenho de um processador físico | Identificar a origem em toda saída e explicar o que a medição em base Z permite concluir |

## Evolução depois do aceite

1. Rodar um único circuito Bell em um único dispositivo físico IBM, com credencial e orçamento do laboratório. Registrar layout físico, compilação para o alvo, identificador remoto, datas, shots concluídos e metadados de calibração disponíveis.
2. Repetir o circuito em outro horário e mostrar incerteza e condições de execução. Semear a simulação serve para reprodução local. O ensaio físico é comparado estatisticamente.
3. Priorizar integração adicional somente se o parceiro precisar dela para repetir uma tarefa. A primeira candidata para validação independente local é PennyLane. A primeira alternativa comercial multi-hardware a avaliar é Amazon Braket.

As escolhas de engenharia estão em [Arquitetura](arquitetura.md). Os fornecedores e interfaces pesquisados estão no [Guia de integrações](integracoes.md). Os roteiros de campo e liberação estão em [Piloto e telas](piloto-e-telas.md) e [Qualidade](qualidade-e-release.md).

O [plano paralelo dos 12 produtos](ecossistema-quantico.md) registra as oportunidades de expansão, os compradores e a evidência necessária para abrir uma nova frente. As seis semanas acima são dedicadas ao Radar Quantum Bench.

**Proteção da implementação.** Na semana 1, classificar o que será público ou reservado. Na semana 4, verificar o que a interface e a exportação entregam ao navegador. Na semana 5, bloquear a liberação de qualquer pacote que exponha ativo reservado. O responsável pela liberação guarda a evidência do pacote aprovado. [Critérios de proteção do produto](protecao-do-produto.md)
