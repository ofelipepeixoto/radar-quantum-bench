# Um produto, duas frentes de desenvolvimento

O Radar Quantum Bench mantém a edição científica local pública sob Apache License 2.0. A edição comercial evolui em repositório privado separado. O titular autorizou essa divisão em 20/11/2026 e adiou a validação com um laboratório comprador. O desenvolvimento atual permanece limitado às integrações locais gratuitas.

## O que compõe a edição pública

| Conteúdo atual | Finalidade |
| --- | --- |
| Circuitos Bell, GHZ e Bernstein-Vazirani, ruído sintético e métricas | Comparação científica de referência em CPU |
| Contagens de exemplo, OpenQASM, formatos, exportação e verificador | Reprodução e conferência dos resultados |
| API local, fila SQLite e recuperação | Operação da bancada em um computador autorizado |
| Interface local, relatório determinístico e seletor opcional de IA local | Demonstração e uso da bancada em português |
| Testes, ferramentas de conferência e documentação | Manutenção, instalação e portfólio público |

Essa é a implementação já pública que apoia o núcleo científico. Os arquivos e porções próprias abrangidos estão discriminados em [LICENSE-SCOPE.json](../LICENSE-SCOPE.json). A [LICENSE](../LICENSE) contém o texto Apache 2.0 e o [NOTICE](../NOTICE) identifica as atribuições. Dependências, fontes e porções de terceiros conservam seus próprios avisos.

Os três ZIPs científicos históricos mantêm seus bytes. Sua distribuição precisa acompanhar os avisos externos indicados em [Licenças dos artefatos](../artifacts/LICENCAS.md). O pacote completo da edição pública contém os avisos. Recursos comerciais futuros começam fora desta árvore e não recebem automaticamente a licença da edição pública.

## O que evolui na edição comercial

As frentes comerciais planejadas incluem contas e funções por equipe, isolamento entre laboratórios, operação hospedada, quotas e controle de custos, integrações próprias, administração e suporte contratado. Esses recursos ainda precisam de implementação e testes próprios. O fato de existir um repositório privado não comprova que uma plataforma empresarial esteja pronta.

A edição privada consome o núcleo público por uma revisão fixa e um contrato de capacidades. O código científico fica mantido no núcleo. Alterações científicas passam pelos mesmos testes e pela revisão da edição pública. O código próprio privado permanece reservado. Caso uma implementação Apache seja reutilizada, seus direitos e avisos precisam ser preservados.

## Como manter os dois juntos

1. Desenvolver e testar uma mudança científica ou de formato no núcleo público.
2. Integrar a revisão aprovada e gerar a candidata com seus hashes e avisos.
3. Atualizar na edição privada o pin do núcleo e os hashes de licença, aviso e contrato.
4. Executar a conferência de compatibilidade antes de desenvolver ou integrar recursos comerciais.
5. Registrar uma nova versão do contrato quando um consumidor precisar adaptar seu comportamento.

O [PUBLIC-CONTRACT.json](../PUBLIC-CONTRACT.json) registra as capacidades e os formatos atualmente disponíveis. Ele descreve uma instalação local. Autenticação e isolamento entre laboratórios continuam fora da implementação atual. A compatibilidade não deve ser inferida apenas pelo nome da branch main. Os rótulos de prontidão e a política de desenvolvimento descrevem esta versão e as decisões do projeto. Eles não acrescentam restrições aos direitos concedidos pela Apache 2.0 para usar, modificar ou redistribuir as porções próprias licenciadas.

Os arquivos privados, seus históricos, configurações internas, dados e credenciais não entram na distribuição pública. Esta documentação pública registra a fronteira e o contrato comum. O plano de desenvolvimento e os detalhes internos da edição comercial permanecem naquela frente.

## Integrações e custo nesta fase

A [política de desenvolvimento](../config/development-policy.json) fixa `local_free_only`, `paid_execution: false` e `buyer_validation: deferred_by_owner`. A candidata confere essa política antes de empacotar. A edição privada também confere o contrato e essa condição.

As execuções atuais usam Qiskit Aer em CPU e, quando habilitado, Ollama em loopback com modelo obtido separadamente. Não há envio de trabalhos a QPU, serviço de inferência pago, cobrança, implantação ou contratação automática. Contas de fornecedores, quotas e orçamento terão decisão própria antes de qualquer integração remota. Computador, energia e eventual uso de quotas da plataforma continuam sendo custos do ambiente.

## Piloto e produto comercial

A validação com comprador está adiada por decisão do titular. Os aceites técnicos e humanos continuam identificados e podem ser retomados. O registro não marca um laboratório como aprovado nem registra preço ou demanda sem evidência. A [avaliação de prontidão comercial](prontidao-comercial.md) descreve o que já pode ser oferecido com escopo limitado.
