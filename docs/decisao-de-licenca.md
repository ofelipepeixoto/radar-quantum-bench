# Decisão de licença do código próprio

**Estado em 20/11/2026: proposta aguardando decisão do titular.** Este documento organiza a escolha comercial. Ele não aplica uma licença ao projeto, não altera os avisos de terceiros e não libera a candidata para o piloto. O campo `licenca_propria_pendente` permanece no manifesto até haver uma decisão registrada e sua implementação revisada.

## Recomendação para esta fase

A hipótese atual é cobrar por laboratório ou turma e preservar componentes comerciais reservados. Para esse objetivo, a proposta é avaliar **PolyForm Free Trial 1.0.0 para uma avaliação temporária**, acompanhada de condições comerciais próprias para uso continuado. Antes de aplicar essa proposta, o titular precisa aprovar a concessão e conferir as condições do piloto, incluindo o compartilhamento de cápsulas com código. Essa recomendação é uma inferência de produto a partir da hipótese comercial e dos textos oficiais abaixo.

O texto padrão Free Trial permite avaliar a adequação do software a uma aplicação por menos de 32 dias consecutivos. Ele permite alterações para a finalidade admitida e não concede redistribuição das cópias. A própria PolyForm descreve essa opção como uma forma de avaliar integração antes de uma licença de produção. [Texto oficial Free Trial 1.0.0](https://polyformproject.org/licenses/free-trial/1.0.0) · [Orientação do projeto PolyForm](https://polyformproject.org/why-adopt-polyform)

A cápsula científica atual inclui fontes. Para manter a conferência entre colegas no piloto, a autorização escolhida precisa cobrir esse percurso. Uma alternativa é cada avaliador receber a mesma candidata diretamente do titular, sob as condições aprovadas. Repassar o pacote que inclui software a outra pessoa exige conferir a autorização correspondente. A regra de distribuição precisa estar resolvida antes das sessões.

## Comparação das alternativas

| Alternativa | Permissões relevantes do texto | Efeito na hipótese por laboratório |
| --- | --- | --- |
| Apache License 2.0 para o núcleo próprio | Concede direitos amplos de reprodução, alteração e distribuição, com condições de licença e avisos. Inclui concessão de patentes nas condições do texto. | Favorece adoção aberta. A receita precisaria se apoiar em serviços, suporte, operação ou componentes privados. O núcleo já concedido não fica reservado ao Radar. |
| PolyForm Noncommercial 1.0.0 | Admite usos não comerciais, alteração e distribuição nas condições previstas. O texto também admite uso por instituições educacionais e de pesquisa pública independentemente da origem de financiamento. | Pode fazer sentido se a intenção for oferecer essa edição a tais instituições e cobrar de outros públicos ou por serviços. Não é a escolha recomendada para sustentar a cobrança pelo uso desse mesmo software nas instituições descritas. |
| PolyForm Free Trial 1.0.0, sujeita à decisão do titular | Avaliação temporária da adequação do software, por menos de 32 dias consecutivos. Não concede redistribuição. | Aproxima a avaliação de uma negociação posterior por laboratório. Exige resolver o recebimento das cápsulas pelos colegas e as condições do uso continuado. |
| Conservar a licença própria pendente enquanto a decisão é tomada | Não acrescenta uma concessão de uso àquela já existente. A visibilidade e os recursos da plataforma GitHub seguem suas próprias condições. | Permite continuar a preparação técnica e a revisão. Mantém a pendência que impede tratar a candidata como piloto liberado. |

As condições de Apache 2.0 vêm do [texto da Apache Software Foundation](https://www.apache.org/licenses/LICENSE-2.0), especialmente das seções 2 a 4. Os termos de Noncommercial estão no [texto oficial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0). A PolyForm aponta que essa opção não atende ao objetivo de vender ferramentas a organizações educacionais ou de pesquisa quando se pretende cobrar pelo uso delas. [Critérios oficiais de escolha](https://polyformproject.org/why-adopt-polyform)

## O que precisa constar na decisão

O registro do titular deve identificar o código próprio abrangido, a opção e a versão escolhidas, a revisão do projeto e o destino do pacote. Para uma avaliação temporária, deve indicar os participantes autorizados por código, o período e a forma de obter ou compartilhar o software durante a conferência entre colegas. Os termos comerciais continuados precisam ter revisão adequada ao acordo pretendido. Este documento não redige esse contrato nem presume que ele já exista.

Depois da decisão, a implementação deve incluir o texto aplicável, os avisos, a atualização coerente do README, do inventário e do manifesto e uma nova revisão da candidata. Dados de participantes e termos privados permanecem fora do repositório público. As dependências continuam com suas próprias licenças e atribuições em [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Proteção da implementação

A escolha de licença define permissões; o controle de distribuição decide quais arquivos serão entregues. O código que já está público e os arquivos enviados ao navegador ou ao laboratório podem ser examinados. A proteção de uma futura lógica comercial reservada depende de mantê-la fora dessas entregas e de conferir as interfaces e exportações autorizadas. A lista explícita e os hashes da candidata ajudam a revisar esse conteúdo. [Proteção do produto](protecao-do-produto.md)

O GitHub explica que uma licença própria deve ser escolhida conscientemente e que repositório público envolve os direitos de visualização e fork previstos nos termos da plataforma. A ausência de um arquivo de licença não transforma a distribuição em autorização geral de uso. [Orientação oficial do GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

**Escolha proposta para o titular:** autorizar a preparação da opção PolyForm Free Trial 1.0.0 para a avaliação, com a distribuição entre avaliadores explicitamente resolvida, ou escolher uma das alternativas acima antes de aplicar qualquer concessão. A proposta aguarda essa decisão.
