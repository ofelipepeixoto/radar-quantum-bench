# Quarto marco do Radar Quantum Bench

A entrega parte da main c8557bfd79ddfebe63915c8d615eb88b6995a422 e acrescenta a bancada em português ao serviço local. Astro gera a página estática. O JavaScript consulta a API na mesma origem. O banco, o executor e o protocolo científico continuam atendendo aos três circuitos do catálogo.

## Fluxo implementado

A pessoa escolhe Bell, GHZ ou Bernstein-Vazirani, confere a prévia do circuito e pode ajustar a semente. Ao executar, a página registra a chave do envio e abre a comparação pelo identificador devolvido pela API. O endereço permite voltar à mesma execução após uma recarga. O histórico tem paginação e ação para abrir cada trabalho.

Os estados de fila, execução, conclusão e falha aparecem com rótulos. Cada condição informa quantas repetições foram concluídas. Uma resposta perdida conserva a configuração e a chave para confirmação do mesmo pedido. A reconexão de leitura pode ser feita mesmo antes de selecionar um trabalho.

Com a comparação concluída, a tela apresenta a taxa de resultados no conjunto esperado, o intervalo de Wilson, a TVD em relação à teoria ideal e o tempo mediano. O gráfico usa a mesma escala nas três séries e tem uma tabela equivalente de contagens e percentuais. As palavras com contagem ou probabilidade zero permanecem visíveis. O ZIP é baixado pelo endpoint existente, e os comandos de repetir configuração e trocar semente criam trabalhos novos.

## Validação realizada

| Verificação | Resultado local |
| --- | --- |
| Instalação reproduzível da interface | npm ci concluído com o lockfile |
| Tipos e build | Astro check com zero erros e zero avisos. Build estático concluído. |
| Backend | 56 testes aprovados, incluindo o host estático e a API existente |
| Navegador | Sete testes Playwright aprovados em Chromium Headless 153.0.8010.0 |
| Ciência mostrada na tela | Contagens de Bell, GHZ e BV conferidas contra as respostas da API real, com executor e simulador em CPU |
| Exportação | SHA-256 do ZIP baixado pelo navegador igual ao arquivo servido pela API |
| Pedido com resposta perdida | O servidor aceitou o POST, o teste interrompeu a resposta, recarregou a página e confirmou o mesmo ID com a mesma chave |
| Teclado e largura estreita | Seleção, envio e abertura por teclado. Catálogo e resultado a 320 pixels sem rolagem horizontal do documento, com tabelas roláveis na própria região. |
| Acessibilidade automática | Axe sem violações nas regras WCAG A e AA selecionadas, no catálogo e no resultado móvel |
| Recursos locais | Fluxo Bell sem solicitações para outras origens. Fontes, CSS e JavaScript servidos na mesma origem. |

Fila cheia e parte dos erros de comunicação são respostas interceptadas explicitamente nos testes. As medições, o histórico, a perda de resposta após aceitação e o download usam o serviço real. As verificações automáticas e o percurso por teclado cobrem parte do aceite de acessibilidade. Os testes com leitores de tela e com participantes do laboratório ainda pertencem ao piloto.

O ambiente local usou Node 24.22.3, npm 11.19.1, Astro 7.4.13 e Playwright 1.65.1. O build recebe as fontes Geist e IBM Plex Mono com suas licenças. A integração contínua repete a instalação, o build, os testes Python e o fluxo pelo navegador usando o Chromium distribuído pelo Playwright.

A revisão do código verificou origem, conteúdo estático e gravação idempotente. A interface escreve os dados em elementos de texto, sem interpretar respostas da API como HTML. Os cabeçalhos restringem scripts, fontes e conexões à própria origem. Somente a pasta compilada é disponibilizada pelo host estático, com testes para arquivos ausentes e fora dessa pasta. Os artefatos científicos anteriores preservam seus hashes.

## Próxima entrega prevista

Acrescentar uma explicação em português baseada nas métricas calculadas e em seus identificadores de evidência. O resumo determinístico deve continuar disponível quando um modelo opcional falhar. O aceite inclui valores e unidades corretos, limitações visíveis e referência às contagens que sustentam cada conclusão. Em seguida, conduzir as sessões com participantes já previstas no [plano de piloto](piloto-e-telas.md).

A [operação da interface](interface-local.md) contém os comandos para iniciar esta versão no computador do laboratório.
