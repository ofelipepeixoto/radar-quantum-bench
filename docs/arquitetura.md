# Arquitetura do piloto

Uma instalação por laboratório, no computador do pesquisador. O usuário abre a interface no navegador. A API serve a versão estática da interface e os resultados na mesma origem. O processo que executa o simulador pode ser reiniciado sem apagar o histórico. A primeira instalação usará Linux ou WSL2 com a mesma imagem e versões de dependências fixadas.

## Componentes

| Peça | Escolha inicial | Responsabilidade |
| --- | --- | --- |
| Interface | Astro, TypeScript e componentes interativos no formulário, andamento e resultados | Exibir as unidades, a teoria, as duas condições e o vínculo entre números e contagens. A página estática de resultado lê o identificador na URL e busca os dados na API local. |
| API | Python, FastAPI e modelos de entrada e saída versionados | Validar a configuração, impor limites, registrar a solicitação e montar as respostas. |
| Persistência | SQLite local com transações e diretório de artefatos por comparação | Guardar estado e identificadores. Gravar artefatos em arquivo temporário e mover para o destino só ao concluir. |
| Executor | Processo Python separado usando Qiskit e Aer | Construir um dos três circuitos, compilar, executar uma repetição de cada vez e coletar medições e tempos. |
| Métricas | Biblioteca Python pura, utilizada também pela verificação via linha de comando | Calcular taxas, TVD e intervalos a partir das contagens. Guardar versão do cálculo, unidade, referência e numerador/denominador quando aplicáveis. |
| Relator | Resumo local por regras e modelo de linguagem opcional | Selecionar explicações e hipóteses com evidência. O servidor insere os números a partir de fatos validados. |
| Demonstração pública opcional | Cloudflare Pages com resultados de exemplo autorizados e pré-calculados | Permitir explorar um caso na web. O identificador do exemplo aponta apenas para arquivos estáticos do exemplo. As simulações do piloto rodam no laboratório. |

Astro permite carregar JavaScript só onde a página precisa de interação. Em Cloudflare Pages, a regra de preço para arquivos estáticos se aplica às requisições que não chamam Functions. Esta arquitetura também permite rodar o piloto sem publicar a demonstração. [Astro](https://docs.astro.build/en/concepts/islands/) · [Cloudflare Pages](https://developers.cloudflare.com/pages/functions/pricing/)

## Como os dados circulam

1. A API recebe o identificador e a revisão do circuito, shots, repetições, perfil de ruído e estratégia de sementes. Valida tudo e cria a comparação e as linhas esperadas de trabalho na mesma transação.
2. Nesta instalação local, um bloqueio de arquivo mantido pelo sistema operacional permite um único executor por diretório de dados. Ao iniciar sob esse bloqueio, o executor devolve os trabalhos interrompidos à fila e registra as tentativas anteriores. A conclusão exige o identificador da tentativa ainda ativa. Alternar ideal e ruído conforme o protocolo. [Operação e limites desta implementação](api-local.md)
3. O adaptador converte os bits do provedor para a ordem canônica, preservando também a saída e o mapa originais. As contagens são confirmadas numa transação com o estado, a duração e a referência ao arquivo. Após reinício, reconciliar trabalhos interrompidos e arquivos órfãos. Uma comparação pode ter várias tentativas e apenas um resultado aceito por condição e repetição.
4. O motor calcula as métricas quando as condições estão completas. O relatório referencia métricas e evidências pelo identificador. O pacote exportado preserva as medições mesmo se o texto precisar ser refeito.
5. A interface recupera o andamento por consulta periódica. Exibe a última atualização, informa interrupção de conexão e recupera o mesmo pedido ao reabrir a página.

## Modelo mínimo de dados

| Entidade | Campos essenciais e regra |
| --- | --- |
| Circuito | Identificador do catálogo, revisão, referência analítica, mapa lógico, preparação e hash do circuito |
| Comparação | ID, revisão do protocolo, configuração, ambiente, status, origem da cópia, chave idempotente e hash da configuração |
| Condição e repetição | Circuito compilado, perfil do adaptador, ruído, posição no ensaio, shots solicitados, semente e marcador de aquecimento |
| Tentativa | ID próprio, número da tentativa, provedor ou simulador, início e fim, tempos por fase, status, erro categorizado e referência ao resultado |
| Observação | Contagens obtidas, ordem dos bits, shots concluídos, metadados de máquina e de execução com unidades |
| Métrica e relatório | Regra de cálculo e versão, IDs das observações, valor e unidade, validade, versão do relator, evidências e origem do texto |
| Artefato | Caminho relativo ao pacote, tipo, tamanho, algoritmo e hash para conferência |

Distinguir o ID único de cada execução do hash da configuração. Dois ensaios intencionalmente idênticos terão registros separados e poderão ser comparados. Um duplo clique no mesmo envio deverá recuperar o ID original. A mesma chave idempotente com parâmetros diferentes deverá retornar conflito.

## Contrato proposto da API local

| Operação | Resultado esperado |
| --- | --- |
| `GET /api/v1/experimentos` | Três circuitos com revisão, pergunta, parâmetros permitidos e referência teórica |
| `POST /api/v1/comparacoes` | `202` e ID para acompanhamento. Exigir chave de idempotência. Responder `422` para parâmetros inválidos e `429` quando a fila atingir o limite. |
| `GET /api/v1/comparacoes/{id}` | Estado das condições, tentativas e dados disponíveis. Estados incluem em fila, em execução, parcial, concluída e falhou. |
| `GET /api/v1/comparacoes/{id}/metricas` | Contagens, referência e métricas com IDs, unidades e marcação de conjunto incompleto |
| `POST /api/v1/comparacoes/{id}/retentativas` | Reenfileirar apenas o trabalho interrompido ou com falha. Usar chave idempotente e preservar tentativas anteriores. |
| `POST /api/v1/comparacoes/{id}/relatorio` | Gerar explicação a partir das evidências já calculadas. Limitar repetições pagas e identificar o resumo local. |
| `GET /api/v1/comparacoes/{id}/exportacao` | Pacote identificado por versão e estado, com arquivos brutos, métricas, relatório e somas de verificação |

No primeiro piloto, disponibilizar esses endpoints em loopback. A versão que um dia servir mais de um laboratório precisará vincular cada consulta e alteração à instituição autorizada.

## Pacote de reprodução

Propor um ZIP com `manifesto.json`, `circuitos/`, `contagens.jsonl`, `metricas.csv`, `relatorio.md` e instruções sobre o esquema. Usar OpenQASM 3 como representação legível para os circuitos contemplados. Guardar separadamente mapa de leitura, definição do ruído, sementes, versão do simulador, ambiente executável fixado e hashes. O circuito sozinho não contém as condições da experiência. [OpenQASM](https://github.com/openqasm/openqasm) · [Serialização do Qiskit](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qasm3)

Prever um comando local de verificação que leia o pacote, confira os hashes e recalcule as métricas sem rede ou IA. Para exportações antigas, selecionar o leitor pela versão do esquema, conservar o arquivo original e informar de forma legível um formato desconhecido.

## Recursos e formato do adaptador

Reportar profundidade, número de portas de dois qubits e número de qubits antes e depois da compilação. Medir tempo de parede com relógio monotônico e, quando suportado, CPU e pico de memória RSS do processo isolado. Identificar unidade, método, sistema, quantidade de threads e se o pico cobre toda a vida do processo ou só a tentativa. Quando o provedor não expuser um dado, exibir “indisponível”. Medir aquecimento separadamente.

O adaptador do simulador retorna origem, circuito e layout usados, ID da tentativa, contagens, ordem dos bits, shots solicitados e recebidos, tempos e recursos disponíveis. Uma integração física acrescentará ID de trabalho externo, dispositivo, fila, instante de execução e condições de calibração disponíveis. Espera por rede e fila fica fora do tempo do processador quântico. Preservar o tipo nativo do resultado. Um provedor que só oferece probabilidades não atende ao aceite de contagens brutas do piloto.

## Distribuição e operação

Na primeira semana, testar instalação num ambiente limpo, com versões de Python e Qiskit suportadas pela distribuição do Aer escolhida. Fixar dependências e registrar versão ou digest do ambiente. Antes do piloto, publicar instruções correspondentes à versão realmente testada. A CI prevista rodará testes científicos, de API, de exportação e build da interface a cada mudança pertinente. A cada entrega candidata, repetir um teste de ponta a ponta em instalação limpa e uma restauração de backup. Guardar a revisão do código junto com as evidências. [Protocolo científico](protocolo-cientifico.md) · [Qualidade e recuperação](qualidade-e-release.md)
