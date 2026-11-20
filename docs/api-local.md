# Operar a API local

Uma instalação atende a um laboratório no próprio computador. A API recebe pedidos e consulta o histórico. O executor roda os três circuitos em CPU usando a mesma configuração científica já testada. Ambos usam o mesmo diretório de dados. As fontes e os pacotes científicos anteriores continuam no repositório.

## Instalar e iniciar

Na raiz do repositório, crie e ative um ambiente Python 3.12 em Linux x86_64 ou WSL2 x86_64. Instale com `python -m pip install -r requirements-api.txt`. O arquivo herda as dependências científicas e fixa as adicionais com hashes SHA-256.

Inicie `python -m radar_quantum_bench.local serve --data-dir local-data`. Em outro terminal, com o mesmo ambiente, execute `python -m radar_quantum_bench.local worker --data-dir local-data`. O endereço HTTP é 127.0.0.1 e a porta padrão é 8000. O parâmetro `--port` altera a porta da API. O worker aceita `--once` para processar no máximo um trabalho e encerrar. O comando roda cada comparação em subprocesso com prazo padrão de 120 segundos e teto de memória virtual de 2.048 MiB. `--timeout-seconds` e `--memory-mib` ajustam esses limites. Os recibos em `executions` ficam separados dos resultados científicos. [Evidências operacionais](marco-candidata.md)

A API conserva a especificação em `/openapi.json`. As páginas que carregariam JavaScript de terceiros estão desabilitadas. Por padrão, o serviço usa o resumo determinístico e o simulador local. O parâmetro opcional `--report-model` habilita consultas explícitas ao Ollama em loopback. A configuração e os limites estão no [guia do relator](relatorios-locais.md). Cada ensaio mantém 1.024 medições por repetição e dez repetições por condição.

## Rotas implementadas

| Pedido | Resposta |
| --- | --- |
| GET /health | Indica que a API respondeu. O executor é um processo separado. |
| GET /api/v1/experimentos | Bell, GHZ e BV, referências analíticas, qubits e configurações padrão |
| POST /api/v1/comparacoes | Recebe circuito e semente opcional e devolve 202 com ID e estado |
| GET /api/v1/comparacoes?limit=20&offset=0 | Histórico por página, mais recentes primeiro. Limite de até 100 por consulta e offset de 0 a 2147483647. |
| GET /api/v1/comparacoes/{id} | Estado, configuração, tentativas e progresso científico quando já houver checkpoint |
| GET /api/v1/comparacoes/{id}/metricas | Resumo das medições disponíveis, inclusive quando o ensaio estiver incompleto |
| POST /api/v1/comparacoes/{id}/retentativas | Devolve um trabalho com falha à fila. A próxima execução preserva os checkpoints válidos. |
| GET /api/v1/comparacoes/{id}/exportacao | ZIP científico com código, testes, versões, medições e guia. Exige conclusão do trabalho e do resultado. |
| GET /api/v1/licencas | Identificação Apache 2.0 e hashes dos avisos públicos |
| GET /api/v1/licencas.zip | Licença, NOTICE, escopo e avisos de terceiros para acompanhar a cápsula científica |
| GET /api/v1/relator | Indica se a instalação habilitou o modelo opcional. Não consulta o modelo. |
| GET /api/v1/comparacoes/{id}/relatorio | Relatório com fatos e evidências do checkpoint disponível. Não consulta o modelo. |
| POST /api/v1/comparacoes/{id}/relatorio | Solicita a organização pelo modelo habilitado. Exige conclusão. Reutiliza uma seleção já aprovada para os mesmos dados e modelo. |
| GET /api/v1/comparacoes/{id}/relatorio.md | Download da explicação em Markdown com evidências e identificação da origem |
| GET /api/v1/comparacoes/{id}/relatorio.json | Download do relatório estruturado com os mesmos fatos e texto |

Os POSTs de criação e retentativa exigem `Idempotency-Key`, de um a 128 caracteres, sem espaços. O corpo de criação admite `{"circuit":"bell"}`, `ghz` ou `bv`, e opcionalmente `base_seed`, inteiro de 0 a 4294967295. Campos adicionais e valores inválidos devolvem 422. As sementes padrão são 20261120, 20261220 e 20261320 respectivamente. O POST do relator dispensa corpo e chave e não cria experimentos. Uma consulta de IA em andamento recusa outra com 429. A leitura e o ZIP continuam disponíveis.

Reenviar a mesma chave e a mesma configuração devolve o ID original, inclusive com a fila cheia. Usar a mesma chave para parâmetros diferentes devolve 409. Uma chave de retentativa pertence ao trabalho correspondente. Repeti-la devolve o estado atual daquele trabalho. Uma nova chave de retentativa exige estado `failed`. O arquivo JSON do experimento preserva as tentativas de medição. O SQLite preserva as tentativas do executor de assumir o trabalho.

## Enviar e consultar

Substitua ID pelo identificador devolvido pelo POST. A fila padrão aceita até 32 trabalhos `queued` ou `running`. Novos pedidos acima desse limite recebem 429 e podem ser enviados depois.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/comparacoes \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: aula-ghz-1' \
  -d '{"circuit":"ghz","base_seed":20261220}'

curl http://127.0.0.1:8000/api/v1/comparacoes/ID
curl http://127.0.0.1:8000/api/v1/comparacoes/ID/metricas
curl --fail http://127.0.0.1:8000/api/v1/comparacoes/ID/exportacao -o reproducao.zip
```

Um trabalho pode estar `queued`, `running`, `completed` ou `failed`. Métricas sem arquivo de checkpoint e exportações incompletas devolvem 409. Um ID ausente devolve 404. A resposta expõe apenas a categoria do erro de execução. Use os checkpoints autorizados do laboratório para investigar uma falha, preservando a cópia original.

## Recuperação após interrupção

O executor mantém um bloqueio de arquivo durante toda a sua vida. Um segundo executor no mesmo diretório encerra com erro antes de alterar os trabalhos. Quando o processo morre, o sistema operacional libera o bloqueio. Na próxima inicialização, o executor marca suas tentativas antigas como interrompidas e reenfileira os trabalhos que estavam em execução. Um token por tentativa impede uma conclusão antiga de substituir o estado atual.

Se o checkpoint ainda estiver incompleto, a função científica já existente retoma somente as repetições ausentes. Se todas as medições já tiverem sido salvas, a recuperação conclui o estado no banco sem medir novamente. O banco e o arquivo JSON pertencem ao mesmo diretório. Alterar fontes ou ambiente durante uma coleta exige revisão, pois a retomada valida os hashes e as versões.

A API confere circuito e semente do JSON contra a configuração no SQLite. Ao concluir o trabalho, o executor registra no banco o SHA-256 do resultado inteiro. Ler ou exportar um resultado que divirja desse hash devolve 409. Assim, uma cópia incorreta de outro experimento pode ser detectada mesmo quando o circuito e a semente forem iguais.

## Cópia, restauração e atualização

Para esta primeira edição, pare a API e o executor antes de copiar todo o diretório de dados. Preserve `jobs.sqlite3`, os arquivos auxiliares que ainda existirem e as pastas `results`, `reports` e `executions`. Armazene a cópia em destino privado do laboratório. O lock é liberado pelo sistema operacional. Preserve o arquivo `worker.lock` no diretório e evite removê-lo durante a operação.

Restaure a cópia em outra pasta. Inicie a API com essa pasta e consulte uma comparação conhecida. Confira o JSON, a configuração, as contagens e o hash. Depois inicie o executor. Um ensaio local desta entrega confirmou o histórico e o resultado após essa restauração. Uma cópia feita enquanto houver escrita exige um procedimento consistente que também cubra os arquivos de resultados. O SQLite oferece uma API própria de backup para o banco. [Documentação SQLite](https://www.sqlite.org/backup.html)

Antes de atualizar o software, encerre os processos e guarde a cópia. Use a versão de código e as dependências correspondentes. Se precisar reverter, use a versão anterior com a cópia anterior em uma pasta separada e confira os trabalhos criados desde então antes de retomar o uso.

## Fronteira desta instalação

Use um diretório por instalação local e mantenha a API em loopback. A aplicação restringe Host e confere a origem apresentada pelo navegador. Esta edição pressupõe usuários autorizados no próprio computador. A modalidade compartilhada entre instituições terá autenticação e autorização por recurso como marco próprio.

O banco e os checkpoints ficam fora do controle de versão por padrão em `local-data`. Os ZIPs exportados pela API são cápsulas científicas. Ao redistribuir código próprio dessas cápsulas, acompanhe o download separado de licença e avisos disponível em `/api/v1/licencas.zip`. A interface oferece esse botão junto ao pacote científico. Os bytes e o verificador da cápsula permanecem compatíveis. Para operar a fila e a API, use os módulos adicionais do repositório e `requirements-api.txt`. A [interface em português](interface-local.md) já consome este contrato HTTP na mesma origem. O servidor a disponibiliza quando encontra o build em web/dist ao iniciar.
