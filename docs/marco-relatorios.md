# Quinto marco do Radar Quantum Bench

A entrega parte da main `932bd000c3d6e1f3c5257307bfd8c3729fdf2b59`. Ela acrescenta explicações em português para Bell, GHZ e Bernstein-Vazirani, downloads Markdown e JSON e um adaptador opcional de IA local. O [passo a passo para WSL](testar-no-wsl.md) agora acompanha a preparação do ambiente, os dois processos e a leitura do relatório.

## Comportamento entregue

O relator determinístico usa o resultado científico validado. Cada frase aponta para fatos com valores, unidades, condição, precisão e origem no JSON. A resposta identifica trabalho, execução, hash dos mesmos bytes que foram lidos e revisões do contrato e das instruções. Ela distingue proporção de fidelidade, tempo local de execução física e variação em pontos percentuais de percentuais absolutos.

Uma comparação parcial recebe um relato do progresso disponível, sem conclusão entre condições. Os limites científicos ficam visíveis e a sugestão de próximo teste vem marcada como hipótese. O programa não inicia trabalho a partir de um relatório.

O adaptador opcional consulta um Ollama em loopback após uma ação explícita. O modelo pode escolher e ordenar observações aprovadas. Texto livre, números, unidades ou evidências trocados, direção invertida e campos desconhecidos levam ao resumo local. Antes de enviar fatos, o adaptador verifica metadados locais e bloqueia indicadores de modelo remoto. O prazo total é de 20 segundos. Não existe troca automática para um fornecedor externo.

O registro guardado contém somente a seleção validada e sua procedência. A leitura reconstrói as frases e confere a ligação ao trabalho e ao resultado. Tela, Markdown e JSON usam essa mesma seleção. As cápsulas científicas e os seis módulos científicos que compõem seus hashes preservam o conteúdo anterior.

## Evidências de validação

| Verificação | Resultado local |
| --- | --- |
| Suíte Python | 91 testes aprovados, incluindo ciência, fila, recuperação, API, host, relator e adaptador. |
| Tipos e build da interface | Astro check sem erros, avisos ou hints. Build estático concluído. |
| Navegador | Nove testes Playwright aprovados em Chromium Headless 153.0.8010.0, com API e executor reais nos fluxos científicos. |
| Relatos dos três circuitos | Resumo e observações da tela comparados ao JSON real da API. Valores, unidades, direção e referências também cobertos pela suíte Python. |
| Downloads | Markdown e JSON baixados no navegador, com hash e texto iguais aos da resposta. ZIP científico conferido pelo fluxo existente. |
| Persistência | Seleção de um modelo dublê reaberta em nova instância da aplicação e nos dois downloads, mesmo com o modelo desativado. |
| Respostas não autorizadas | Números ou unidades inseridos, evidência de outra equipe, ordem incompatível de fatos, alegação física e texto que parece instrução recusados pelo contrato fechado. |
| Alteração de dados | Resultado trocado com mesma configuração e cache copiado de outro trabalho recusados. Seleção adulterada retorna resumo local sem reproduzir o texto recebido. |
| Falhas da IA | Timeout e seleção inválida preservam o relatório local e o ZIP. Uma segunda chamada simultânea é recusada sem interromper a leitura. |
| Transporte do adaptador | Testes simulados e fixture HTTP em loopback verificam metadados, JSON estrito, limite de resposta, identidade, redirecionamento e prazo. Nenhum LLM real foi executado. |
| Acessibilidade | Axe sem violações nas regras WCAG A e AA selecionadas, incluindo a página de resultado a 320 pixels. Percurso por teclado e tabelas com rolagem própria. |
| WSL | Sintaxe dos blocos Bash e opções dos comandos conferidas em Linux. Ainda falta executar o guia no PC Windows do usuário. |

O ambiente usou Python 3.12.14, Qiskit 2.6.2, Aer 0.18.4, Node 24.22.3 e npm 11.19.1. O aviso de depreciação do cliente httpx usado pelo TestClient permanece nas versões travadas. Os testes passaram com essas versões. Os ensaios do contrato do modelo usam dados fictícios e dublês explícitos. Eles não equivalem a uma execução de Garak sobre um LLM instalado.

## Próximo marco

Preparar uma versão candidata para o piloto. Reunir o inventário do que será distribuído, testar limites de tempo e memória da simulação e conferir o bloqueio de material reservado no pacote público. Repetir instalação e restauração em outro computador, validar um modelo local real se o laboratório optar por ele e executar o percurso com leitor de tela. Registrar responsável, resultado e pendências antes das sessões com cinco participantes nos dois laboratórios previstos. O [plano do piloto](piloto-e-telas.md) conserva os critérios de decisão.
