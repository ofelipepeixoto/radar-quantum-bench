# Onde o Radar Quantum Bench está no planejamento

O MVP local está implementado e passa por preparação técnica para o piloto. É possível escolher Bell, GHZ ou Bernstein-Vazirani, executar as duas condições em CPU, consultar o histórico, comparar resultados e baixar o pacote científico e a explicação. A decisão de liberar o piloto ainda depende dos aceites registrados abaixo.

## Etapas do plano

| Etapa prevista | Situação | Evidência e pendências |
| --- | --- | --- |
| 1. Primeiro experimento Bell | Implementado | Código, contagens, sementes, OpenQASM e ZIP verificável. [Protocolo e referência](protocolo-cientifico.md) |
| 2. GHZ e Bernstein-Vazirani | Implementado | Catálogo de três circuitos e coleta de referência com 61.440 medições avaliadas. [Registro](marco-catalogo.md) |
| 3. API, fila e histórico | Implementado | SQLite, idempotência, recuperação após interrupção e exportação. [Registro](marco-api.md) |
| 4. Interface em português | Implementação concluída, aceite humano pendente | Fluxos testados no navegador, teclado e verificações automáticas de acessibilidade. Falta o percurso com leitor de tela por uma pessoa. [Registro](marco-interface.md) |
| 5. Relator e candidata | Em validação | Relatórios rastreáveis, opção de IA local, limites do executor, inventário e conferência do pacote. Candidata permanece para revisão. [Relator](marco-relatorios.md) · [Preparação da candidata](marco-candidata.md) |
| 6. Piloto com usuários | Sem sessões registradas no projeto | O plano prevê cinco pessoas de dois laboratórios, comparação com a rotina atual e decisão sobre continuar. [Roteiro](piloto-e-telas.md) |

As semanas do plano são uma estimativa de esforço. A implementação das telas e dos testes automáticos não comprova, por si, que todas as atividades de uma semana foram aceitas por um laboratório. Entrevistas com professores, revisão científica por outra pessoa e disposição de um comprador para uma segunda rodada continuam sem evidências registradas neste repositório.

## O que esta entrega prepara

O executor de produção passa a rodar cada comparação em um subprocesso supervisionado, com prazo e teto de memória virtual. Um recibo operacional registra limites, tempo total e pico de memória residente medido pelo sistema. As medições científicas permanecem nos formatos anteriores.

A candidata reúne somente os arquivos autorizados por uma lista explícita, com hashes das fontes e da interface compilada. O verificador recusa arquivos extras, alterações e marcadores reservados de teste. O inventário identifica as dependências travadas. O pacote se apresenta como candidata de revisão e conserva o bloqueio de licença própria pendente.

Uma instalação nova em ambiente Linux isolado permite conferir os três circuitos, API, relatórios e restauração de uma cópia dos dados. Esse ensaio usa outro diretório e outro ambiente Python no mesmo computador de execução. A validação em um segundo computador físico continua sendo uma atividade separada.

## O que falta para o piloto

| Prioridade | Falta fazer | Quem precisa participar | Como encerrar |
| --- | --- | --- | --- |
| 1 | Definir a licença do código próprio e registrar o destino da distribuição | Titular do projeto e responsável pela versão | Texto aprovado no repositório e nova revisão da candidata com seus avisos |
| 2 | Percorrer a instalação e a primeira comparação no PC Windows com WSL | Operador desse computador | Anotar versões, resultado do teste, download e reabertura do histórico usando o [guia](testar-no-wsl.md) |
| 3 | Conferir reprodução e restauração em outro computador físico | Revisor e laboratório parceiro | Reabrir os dados copiados, conferir hashes e repetir as contagens nas versões travadas |
| 4 | Validar o percurso com leitor de tela | Pessoa que use o leitor e equipe da interface | Registrar navegação, foco, entendimento das tabelas e eventuais correções |
| 5 | Validar um modelo real, se a opção de IA for incluída no piloto | Responsável pelo ambiente local | Registrar nome, digest, consumo e latência, seleção aprovada e comportamento de falha. O resumo determinístico continua sendo a opção padrão. |
| 6 | Registrar revisão científica independente e recrutar participantes | Especialista e dois laboratórios | Conferência do protocolo, agenda das cinco sessões e responsável por reunir os resultados |
| 7 | Conduzir as sessões e decidir a continuidade | Produto, participantes e responsável pela compra | Aplicar os critérios do plano, incluindo exportar sem ajuda, interpretar os números e aceitar uma segunda rodada |

## Depois do piloto

A primeira execução física prevista usa um único circuito Bell em um dispositivo IBM Quantum. Credencial, permissão e orçamento precisam ser definidos para esse ensaio. Ele deve registrar o dispositivo, layout, compilação, horário e metadados disponíveis. Depois será possível avaliar outra integração por demanda concreta do laboratório.

O [plano dos 12 produtos](ecossistema-quantico.md) continua em paralelo como direção de expansão. Quantum Ops, Copilot, educação e Noise Studio são extensões possíveis da base atual. Otimização, materiais e aprendizado de máquina exigem problemas e referências próprias. Calibração, sensores e navegação dependem de parceiros, dados ou equipamentos físicos. Radar PQC constitui uma frente distinta de segurança em computadores convencionais.

O objetivo atual é obter um primeiro laboratório que consiga repetir a comparação e queira usar a bancada novamente. A expansão do ecossistema seguirá a evidência desse uso.
