# Preparação da candidata para o piloto

Registro histórico desta etapa. A licença pública e a política de desenvolvimento foram atualizadas no [marco das duas edições](marco-open-core.md). O [panorama atual](panorama-do-projeto.md) reúne os aceites restantes e o adiamento das sessões.

Esta entrega parte da main `e9d9ab53d48657fe3612bfc43a829d949c50b141`. O objetivo é reunir uma candidata verificável do MVP local e avançar os controles operacionais. O pacote conserva o perfil `review-candidate`. O aceite do piloto continua pendente.

## Limites e recuperação

O comando de produção `python -m radar_quantum_bench.local worker` inicia cada comparação em um subprocesso. O padrão é 120 segundos de prazo total e 2.048 MiB de memória virtual. O teto de memória usa `RLIMIT_AS` no Linux e WSL. A duração inclui inicialização, compilação e coleta. O tempo científico das repetições mantém sua definição anterior.

O supervisor encerra o grupo ao exceder o prazo. O filho também é encerrado se perder o supervisor, e herda o bloqueio da fila enquanto termina. Checkpoints já escritos permanecem disponíveis para recuperação. Em uma tentativa de retorno, somente medições pendentes são executadas. O caminho de biblioteca `run_worker` mantém compatibilidade com os chamadores antigos; os limites são aplicados pelo comando de produção e por chamadas que forneçam `WorkerLimits`.

Cada tentativa supervisionada grava `executions/{trabalho}/{tentativa}.json` no diretório privado de dados. O recibo registra prazo, teto de memória virtual em MiB, duração em ms, pico RSS observado em KiB, código de saída e categoria do resultado. O pico RSS é uma medida de memória residente e difere do teto de memória virtual. Um SIGKILL no supervisor pode impedir a gravação do recibo. Nesse caso, a tentativa durável no SQLite e sua recuperação continuam sendo a referência.

```bash
python -m radar_quantum_bench.local worker --data-dir "$PWD/local-data" \
  --timeout-seconds 120 --memory-mib 2048
```

O prazo aceita valores positivos de até 86.400 segundos e o teto de memória virtual aceita inteiros entre 256 e 16.384 MiB. A fila continua limitada a 32 trabalhos ativos, com um executor por diretório. A API mantém o protocolo fixo de dez repetições de 1.024 medições por condição.

## Pacote e inventário

O [comando de distribuição](../releases/README.md) exige uma lista explícita de fontes, um commit cujos bytes coincidam com essas fontes e os hashes aprovados do build. Ele gera manifesto por arquivo e SHA-256 externo do ZIP. A verificação recusa membros extras, ausentes, duplicados, links, mapas de código e alterações de conteúdo. Os ensaios incluem um marcador privado fictício e JavaScript indevido no build.

O inventário registra 27 dependências Python travadas e 396 referências do lockfile npm, incluindo opcionais de outras plataformas. O pacote não inclui wheels, node_modules ou pesos. As fontes Geist e IBM Plex Mono preservam seus avisos OFL. A [lista de terceiros](../THIRD_PARTY_NOTICES.md) delimita o conteúdo efetivamente entregue. A licença do código próprio continua pendente e mantém o manifesto bloqueado para liberação do piloto.

## Validação técnica

| Ensaio | Evidência |
| --- | --- |
| Suíte Python | 107 testes aprovados, incluindo os testes anteriores, sete de execução supervisionada, oito de distribuição e um de restauração |
| Interface | Astro check e build concluídos. Nove testes de navegador aprovados com API e executor reais nos fluxos científicos. |
| Prazo | Subprocesso encerrado ao exceder o limite, checkpoint preservado e retomada sem repetição de medições concluídas |
| Memória virtual | Tentativa real de alocar 512 MiB sob limite de 256 MiB recusada. Falha nativa sem diagnóstico de memória permanece uma falha de processo. |
| Morte do supervisor | SIGKILL real interrompeu o filho. Um novo executor recuperou a tentativa e concluiu o trabalho. Houve também um ensaio independente pela CLI. |
| Distribuição | Hashes e lista de arquivos conferidos. Arquivo extra, build alterado, marcador reservado e ZIP adulterado recusados pelos testes. |
| Instalação separada | Ambiente Python novo preparado com as wheels travadas disponíveis e `pip check`. O probe do pacote extraído verifica as três comparações, relatórios e exportações. |
| Restauração | O probe copia o diretório inteiro, remove a origem, reabre a cópia e confere IDs, contagens, hashes, relatórios e recibos. O teste de integração também cobre esse percurso. |
| Reprodução sem sockets Python | Um subprocesso bloqueia conexões Python, confirma o bloqueio com um canário e repete os três circuitos pelas sementes. O resultado é comparado à rodada HTTP. Este ensaio não constitui isolamento de rede pelo sistema operacional. |

A integração contínua executa primeiro os testes científicos e do navegador. O job `candidata` usa um ambiente Python separado, confere o inventário, compila a página, gera o pacote do commit exato, verifica seu digest e executa `tools/verify_candidate.py` sobre o ZIP extraído. O artefato `candidata-revisao-e-evidencias` reúne ZIP, SHA256SUMS e `candidate-result.json`. A execução correspondente à PR registra o resultado observado e a revisão efetivamente testada.

O probe registra o alvo, as versões, o uso do ambiente virtual, resultados por circuito e medidas operacionais. Ele usa somente dados de teste e omite caminhos privados e identificadores de execução na evidência reduzida. A preparação inicial instala dependências. O build compilado e as simulações usam os arquivos locais depois dessa preparação.

## Estado do aceite

O resultado desta etapa é uma candidata para revisão técnica. Ainda faltam decisão de licença própria, instalação no PC Windows do usuário, reprodução em outro computador físico, revisão científica independente registrada e percurso humano com leitor de tela. A integração com um LLM real depende da escolha de habilitar a opção de IA no piloto. Não há Ollama instalado neste ambiente, e o serviço de loopback estava indisponível.

As cinco sessões com participantes de dois laboratórios ainda não possuem registros no projeto. O [panorama do planejamento](panorama-do-projeto.md) organiza essas pendências por prioridade. O [roteiro do piloto](piloto-e-telas.md) mantém os critérios de interpretação, tempo até exportar e interesse em uma segunda rodada.
