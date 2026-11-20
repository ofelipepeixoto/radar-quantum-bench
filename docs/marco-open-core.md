# Edição pública Apache 2.0 e frente comercial separada

A entrega parte da main `b11305f23571b32ff1a3959929942a018ef83624`. O titular autorizou Apache 2.0 para o núcleo público, desenvolvimento comercial separado em repositório privado, integrações locais gratuitas e adiamento da validação com um laboratório comprador.

## Entrega pública

O texto oficial Apache 2.0 acompanha LICENSE, NOTICE, avisos de terceiros e uma classificação explícita em LICENSE-SCOPE.json. O escopo cobre as porções próprias já públicas do MVP e seu apoio local de API, interface, relatórios, testes e documentação. Fontes e porções de terceiros mantêm seus avisos. Componentes privados futuros ficam fora dessa concessão.

Os três ZIPs científicos originais mantêm seus hashes e seu verificador. A interface acrescenta o download separado **Baixar licença e avisos**, também disponível pela API. Ele acompanha a redistribuição do código próprio da cápsula com os avisos correspondentes. O pacote completo da candidata inclui todos esses arquivos.

O manifesto novo usa `rqb-review-candidate/2`, registra hashes da licença e do escopo e confere a política `local_free_only`, `paid_execution: false` e `buyer_validation: deferred_by_owner`. Seu estado é `review_only`, com aceites humanos pendentes. Os rótulos de prontidão não restringem os direitos concedidos pela Apache 2.0. Os pacotes e registros antigos continuam legíveis com a política original.

O PUBLIC-CONTRACT.json identifica capacidades locais e formatos compartilhados. A frente comercial fixa a revisão do núcleo e os hashes de licença, atribuição e contrato antes de consumir essa versão. Mudanças no núcleo passam pelos testes públicos. Funções comerciais futuras têm desenvolvimento e revisão próprios.

## Verificações

| Frente | Evidência |
| --- | --- |
| Licença | Texto oficial, NOTICE, classificação completa dos arquivos e exceções de terceiros conferidos |
| Arquivos históricos | Bell, GHZ e BV mantiveram seus SHA-256 e passaram no verificador científico estrito |
| Pacote novo | Licença e política verificadas antes de gerar ou aceitar o formato 2 |
| Compatibilidade | Formato 1 e registros antigos continuam aceitos sem reclassificação de seus resultados históricos |
| Interface e avisos | Download científico e ZIP separado dos avisos conferidos pela API e pelo navegador |
| Operação | Simulação CPU e modelo local opcional, sem envio a QPU ou contratação de serviço pago |
| Fronteira comercial | Repositório privado separado, sem cópia de implementação comercial para a distribuição pública |

Os resultados das suítes e da candidata estão na execução da PR correspondente. O ensaio completo do pacote extraído e a importação do recibo do computador continuam no workflow. Os seis módulos científicos que compõem os hashes das cápsulas preservam seu conteúdo.

## Situação comercial e próximos passos

O MVP permite demonstração e uma oferta experimental de instalação, treinamento e suporte com escopo definido. Contas, permissões por laboratório, isolamento entre equipes e operação hospedada ainda são frentes planejadas. A [prontidão comercial](prontidao-comercial.md) registra os limites da oferta atual.

A validação com comprador está adiada por decisão do titular. Não houve contato, negociação, contratação, sessão fictícia ou preço validado nesta entrega. O plano mantém os aceites humanos para uma retomada posterior e permite continuar a engenharia com dados sintéticos. A [divisão das edições](nucleo-e-edicao-comercial.md) descreve o trabalho conjunto.
