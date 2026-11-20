# Registrar o piloto com evidências

O registro local reúne os testes da candidata e as observações feitas pelas pessoas. Cada evidência se liga ao SHA-256 do ZIP e à revisão de origem. Uma candidata nova exige um registro novo. O registro começa vazio, com zero sessões e os aceites humanos pendentes. A validação com comprador está adiada por decisão do titular. A candidata nova registra a licença Apache 2.0 conferida, sem converter essa conferência em aprovação humana ou comercial.

Os arquivos e anexos ficam em `local-data/acceptance`, fora do controle de versão por padrão. Os templates públicos em `pilot` têm campos vazios. Os comandos recusam campos desconhecidos, outra candidata, participante duplicado e anexo cujo hash divirja do declarado. Dentro do projeto, os registros devem ficar em `local-data`. Eles não são enviados ao navegador ou publicados automaticamente.

## Conferir o computador e iniciar o registro

Depois de instalar o ambiente pelo [guia WSL](testar-no-wsl.md), obtenha o artefato `candidata-revisao-e-evidencias` na execução do GitHub correspondente à versão. Descompacte esse artefato e coloque seu ZIP interno `Radar-Quantum-Bench-Candidata.zip` e o arquivo `SHA256SUMS` em `local-data/candidata`. O ZIP interno deve permanecer intacto. Confira o digest no registro da execução do GitHub.

Com o Python 3.12 do ambiente virtual ativo, execute na raiz do projeto.

```bash
RQB_CANDIDATE="$PWD/local-data/candidata/Radar-Quantum-Bench-Candidata.zip"
RQB_DIGEST="$(cut -d ' ' -f 1 local-data/candidata/SHA256SUMS)"

python tools/verify_workstation.py --candidate "$RQB_CANDIDATE" \
  --sha256 "$RQB_DIGEST" --output local-data/acceptance/workstation.json

python -m radar_quantum_bench.acceptance init \
  --candidate "$RQB_CANDIDATE" --sha256 "$RQB_DIGEST"

python -m radar_quantum_bench.acceptance import-technical \
  --receipt local-data/acceptance/workstation.json

python -m radar_quantum_bench.acceptance status
```

O verificador confere o ZIP, as versões instaladas e sua própria correspondência à candidata. Depois extrai uma cópia temporária e ensaia os três circuitos, os relatórios, os pacotes e a restauração. Ele informa se o kernel corresponde ao WSL. O resultado do processo automático não registra que uma pessoa percorreu a interface, usou leitor de tela ou trabalhou em outro computador. A saída é criada de forma exclusiva para preservar um resultado anterior. Para repetir um ensaio, escolha outro nome de arquivo.

## Opção de modelo local

Para incluir IA no registro, acrescente `--with-local-model` ao comando `init`. A opção deve ser escolhida ao criar o registro. O resumo determinístico continua disponível sem ela. O [guia do relator](relatorios-locais.md) descreve a configuração do Ollama com recursos de nuvem desativados.

O ensaio abaixo exige um modelo previamente instalado. Ele não baixa modelos nem altera o serviço. Substitua o nome pelo modelo que o laboratório decidiu avaliar.

```bash
python -m radar_quantum_bench.release verify "$RQB_CANDIDATE" --sha256 "$RQB_DIGEST"
python -m zipfile -e "$RQB_CANDIDATE" local-data/candidata/extraida
python local-data/candidata/extraida/tools/verify_local_model.py --model qwen2.5:0.5b \
  --candidate "$RQB_CANDIDATE" --sha256 "$RQB_DIGEST" \
  --output local-data/acceptance/model.json

python -m radar_quantum_bench.acceptance import-technical \
  --receipt local-data/acceptance/model.json
```

O verificador precisa corresponder aos hashes da candidata e ser executado de sua cópia extraída, conforme a mensagem do comando. Ele considera o modelo aprovado no ensaio somente quando as três seleções reais passam pelo contrato, os fatos e limites são preservados e a reabertura e os downloads coincidem. Timeout ou resumo alternativo mantêm a evidência de falha. Um ensaio preparatório sem candidata não pode ser importado como aceite final.

A evidência registra nome e digest do modelo, versão do Ollama e duração em milissegundos. Ela não inclui pensamentos do modelo, texto bruto recebido ou dados do laboratório. O estado `technical_receipt_recorded` informa que um recibo consistente foi registrado. Esse registro não funciona como assinatura ou autenticação independente de sua origem.

## Aceites feitos por pessoas

Use uma cópia privada de `pilot/acceptance-template.json`. Preencha o digest e a revisão da candidata, a verificação (`license`, `wsl_pc`, `second_computer`, `scientific_review` ou `screen_reader`), data, resultado, código do observador e hash do anexo. Use códigos `R01`, `R02` e assim por diante para responsáveis. Os nomes e contatos ficam em um controle privado separado.

```bash
sha256sum local-data/acceptance/evidencia-do-revisor.txt
python -m radar_quantum_bench.acceptance check \
  --record local-data/acceptance/revisao.json \
  --attachment local-data/acceptance/evidencia-do-revisor.txt
```

A base do registro é `recorded_human_attestation`. Receber um arquivo não comprova a identidade do revisor nem substitui seu trabalho. Uma verificação pode ter mais de um registro, preservando o histórico. O anexo deve ser uma evidência real da atividade descrita. A [decisão de licença](decisao-de-licenca.md) foi autorizada para a edição pública. O registro distingue a conferência automática do pacote de uma declaração humana e preserva os resultados de versões antigas.

## Cinco sessões em dois laboratórios

Use uma cópia de `pilot/session-template.json` para cada participante `P01` a `P05`. Registre laboratórios `A` e `B`, sem nomes pessoais. O roteiro completo está em [Piloto e telas](piloto-e-telas.md).

Três participantes começam no notebook e dois na plataforma. As listas de sementes A e B devem aparecer nos dois métodos. A lista A usa Bell 20261120, GHZ 20261220 e BV 20261320. A lista B usa, respectivamente, 20261121, 20261221 e 20261321. Cada participante realiza as tarefas pareadas com listas diferentes. Mantenha a mesma pergunta, configuração científica e computador para as duas tarefas daquela pessoa.

Registre duração em segundos, quantidade de ajudas, conclusão da exportação, compreensão de observação/teoria/limitação e conferência da métrica por um colega. O código recusa uma declaração de recálculo quando o pacote da plataforma não foi exportado.

```bash
python -m radar_quantum_bench.acceptance add-session \
  --record local-data/acceptance/P01.json \
  --attachment local-data/acceptance/evidencia-P01.txt
```

O resumo calcula os critérios publicados: quatro exportações sem ajuda em até 600 segundos, quatro interpretações corretas, cinco recálculos e cinco pessoas de dois laboratórios. A mediana da diferença de tempo usa somente pares com as duas exportações concluídas e informa quantos pares entraram. O sinal da diferença é plataforma menos notebook. Esse número é descritivo para o piloto.

A segunda rodada possui um registro separado com candidata, laboratório, código de responsável, data e interesse em discutir continuidade. Use `second-round --record ARQUIVO --attachment ANEXO`. Seu esquema contém `schema: rqb-pilot-second-round/1`, `candidate_sha256`, `source_revision`, `lab`, `responsible_code`, `scheduled_on`, `commercial_interest`, `observed_on`, `observer_code` e `evidence_sha256`. O interesse aceito usa `accepted_discussion`.

## Rever antes de compartilhar

```bash
python -m radar_quantum_bench.acceptance status --output /tmp/pilot-summary.json
```

O resumo omite anexos, códigos individuais de participantes e responsáveis, datas e caminhos privados. A exportação exige um destino fora do repositório, para revisão antes de qualquer publicação. Ele informa a política da candidata recebida. Para a versão nova, indica licença conferida, aceites humanos pendentes e validação com comprador adiada. Para as antigas, preserva o estado originalmente registrado. Registrar todos os resultados não concede licença nem aprova automaticamente a distribuição ou a conclusão científica.
