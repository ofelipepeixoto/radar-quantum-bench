# Pacote candidato para revisão técnica

O comando de distribuição prepara uma cópia para revisão da instalação local. O perfil desta entrega é `review-candidate`. O formato novo `rqb-review-candidate/2` registra Apache-2.0 para as porções próprias, hashes de licença e escopo e `readiness.status` como `review_only`, com aceites humanos pendentes. A validação com comprador está adiada por decisão do titular. Esse estado não declara o piloto aprovado. As atribuições dos componentes de terceiros estão em [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) e o inventário está em [dependencies.json](dependencies.json).

## Preparar a revisão

A lista [public-files.json](public-files.json) declara cada fonte pública e o hash de cada arquivo compilado da interface. O pacote contém o código, a documentação, os testes, exemplos de simulação autorizados e as cápsulas científicas anteriores. Ele entrega o build para abrir a interface depois de preparar as dependências Python. Wheels, node_modules, pesos de modelos e dados do laboratório ficam fora do pacote.

Após compilar a interface com o lockfile, registre explicitamente os arquivos que serão revisados.

```bash
npm --prefix web ci
npm --prefix web run check
npm --prefix web run build
python -m radar_quantum_bench.release snapshot-web
git diff -- releases/public-files.json
```

O registro exige que o diretório compilado contenha somente o HTML, as duas licenças das fontes e os recursos alcançados pelo HTML e pelo CSS. Arquivo extra, link simbólico, referência externa ou mapa de código interrompe essa etapa. Revisar o diff e os testes faz parte da aprovação da lista. O registro explícito não decide sozinho se um conteúdo é público.

Publique a revisão de código e use uma cópia limpa desse commit. O comando abaixo exige o SHA completo e confere os bytes de todas as fontes contra o objeto Git informado. Arquivos locais modificados ou ainda sem commit impedem que um pacote seja atribuído àquela revisão. O build também precisa coincidir com os hashes aprovados na lista.

```bash
python -m radar_quantum_bench.release build \
  --revision "$(git rev-parse HEAD)" \
  --output /tmp/Radar-Quantum-Bench-Candidata.zip
sha256sum /tmp/Radar-Quantum-Bench-Candidata.zip
```

O comando cria o arquivo de modo exclusivo e preserva uma candidata anterior. O ZIP contém `RELEASE-MANIFEST.json`, com revisão de origem, perfil, estado de licença, caminho, tamanho e SHA-256 de cada arquivo. A ordem e os metadados do ZIP são fixos. A receita produz os mesmos bytes quando repetida com as mesmas fontes e o mesmo ambiente verificado.

## Conferir o arquivo recebido

Guarde o SHA-256 no registro de revisão. Use o valor esperado desse registro ao conferir uma cópia.

```bash
python -m radar_quantum_bench.release verify \
  /tmp/Radar-Quantum-Bench-Candidata.zip \
  --sha256 HASH_DO_REGISTRO_DA_CANDIDATA
```

Sem `--sha256`, a verificação confere somente a integridade interna e a estrutura. Um manifesto recomposto por outra pessoa não comprova autoria ou autorização. O verificador recusa membros extras, ausentes, repetidos, alterados, caminhos inseguros, links simbólicos e conteúdos fora da lista declarada. Esta etapa não substitui uma assinatura de artefato.

## Conferir material reservado

Os comandos `build` e `verify` aceitam `--forbid-marker MARCADOR`, repetível. O teste de proteção usa um identificador fictício criado durante o ensaio. Quando esse identificador aparece em um arquivo destinado ao pacote, a verificação recusa a candidata e informa somente o caminho afetado. Outra prova injeta um JavaScript extra no build e confirma sua recusa, mesmo com extensão permitida. Alterar o conteúdo de um arquivo de build aprovado também quebra o hash registrado.

O controle combina a lista revisada, os hashes e os marcadores declarados. Ele não é um classificador universal de segredos. O código distribuído permanece inspecionável. Proteger uma implementação comercial reservada exige mantê-la fora dos arquivos entregues, conforme o [plano de proteção](../docs/protecao-do-produto.md).

Depois da revisão técnica, os aceites humanos continuam registrados como pendentes. A validação com comprador está adiada por decisão do titular. Pacotes antigos no formato 1 continuam legíveis com a política original. A [divisão das edições](../docs/nucleo-e-edicao-comercial.md) registra o alcance da licença e os próximos passos.
