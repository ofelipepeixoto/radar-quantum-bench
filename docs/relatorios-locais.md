# Explicar e conferir os resultados

Ao concluir Bell, GHZ ou Bernstein-Vazirani, a bancada apresenta **Leitura dos resultados**. O resumo local calcula as frases a partir do JSON validado do experimento. Ele informa o total de medições, as taxas, o intervalo de Wilson, a TVD, os tempos locais e a diferença observada entre as condições.

Cada referência abre **Conferir as evidências**. A tabela inclui identificador, valor, unidade, condição e origem no JSON. Percentuais usam quatro casas decimais, TVD usa seis e tempos usam três. A variação das taxas usa pontos percentuais. O hash identifica os bytes do resultado que sustentam o relatório. A procedência também informa o trabalho, a execução e as revisões do esquema e das instruções.

O relatório identifica o ensaio como simulação Aer em CPU com ruído sintético. As medições na base Z, isoladamente, não atestam emaranhamento. A taxa de resultados esperados não é uma medida de fidelidade do estado. O ensaio também não demonstra vantagem quântica ou desempenho de um processador físico.

## Downloads e histórico

Os botões **Baixar relatório Markdown** e **Baixar relatório JSON** entregam o mesmo texto e suas evidências. O Markdown inclui uma tabela com as origens e os cálculos de conversão. Os relatórios são arquivos separados do ZIP científico e apontam para o SHA-256 de seu resultado. As cápsulas científicas anteriores preservam seus arquivos e hashes.

A API também gera um resumo parcial quando já existe checkpoint. Ele indica o progresso de cada condição, preserva as métricas disponíveis e informa o que falta. A conclusão comparativa e a sugestão de próximo teste aparecem somente quando o protocolo está completo. A interface abre o relatório após a conclusão confirmada pelo executor.

Quando há uma seleção aprovada de IA, o diretório `local-data/reports` guarda somente os identificadores das frases, as evidências e a procedência. Toda leitura reconstrói os fatos do resultado validado e verifica essa seleção novamente. O texto livre do modelo não é salvo. Uma seleção incompatível devolve o resumo local. Ao fazer uma cópia da instalação, preserve todo o diretório de dados, incluindo `reports`.

## Modelo local opcional

O resumo padrão já atende ao fluxo de uso e dispensa instalação de IA. Esta versão oferece um adaptador para um modelo previamente instalado no **Ollama do mesmo ambiente**, acessível em `127.0.0.1:11434`. Ele permite selecionar e ordenar observações entre frases aprovadas. Os valores, as unidades, os limites e a sugestão permanecem sob controle do programa.

Para habilitar a opção, primeiro configure o Ollama para executar sem recursos de nuvem. Se você inicia esse processo manualmente no Ubuntu, encerre sua instância anterior e inicie com a variável aplicada ao próprio Ollama.

```bash
OLLAMA_NO_CLOUD=1 ollama serve
```

Se ele roda como serviço ou aplicativo, configure essa variável nesse serviço ou aplicativo e reinicie-o. Aplicá-la apenas ao processo do Bench não altera um Ollama que já estava rodando. A [documentação oficial do Ollama](https://github.com/ollama/ollama/blob/main/docs/faq.mdx#how-do-i-disable-ollamas-cloud-features) descreve também `disable_ollama_cloud` em `~/.ollama/server.json`.

Em outra aba Ubuntu, confira os modelos disponíveis com `ollama list`. O Bench não baixa modelos. Escolha um que já esteja instalado e cuja licença permita seu uso. Com a `.venv` do projeto ativa, reinicie o servidor substituindo `meu-modelo:tag` pelo nome exato da lista.

```bash
cd ~/projetos/radar-quantum-bench
source .venv/bin/activate
python -m radar_quantum_bench.local serve --data-dir "$PWD/local-data" --report-model meu-modelo:tag
```

O executor mantém o comando habitual em outro terminal. Após abrir uma comparação concluída, clique em **Organizar com IA local**. Ler a página, atualizar o histórico ou baixar arquivos não consulta o modelo. A sugestão de próximo teste depende de uma nova ação sua para iniciar um experimento.

O adaptador consulta a versão do Ollama e os metadados do modelo antes de enviar os fatos. Ele recusa indicadores de modelo remoto, nomes de nuvem e modelos sem digest ou tamanho local válido. Não aceita URL de destino, proxy de ambiente, redirecionamento ou ferramentas. As chamadas usam os endpoints oficiais [tags](https://docs.ollama.com/api/tags), [show](https://docs.ollama.com/api/show) e [chat](https://docs.ollama.com/api/chat). Os campos de modelo remoto estão no [contrato oficial](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml).

Cada consulta tem prazo total de 20 segundos. A resposta de chat admite até 64 KiB, e as respostas de metadados admitem até 1 MiB por pedido. O adaptador limita a geração a 2.048 tokens e solicita uma thread. A carga do modelo precisa caber na memória disponível. Uma carga lenta, modelo ausente, resposta inválida ou falha de rede conserva o resumo determinístico. O servidor aceita uma consulta de IA por vez e mantém as leituras e a exportação científica disponíveis.

Uma resposta aprovada registra nome, digest do modelo informado pelo Ollama e versão do Ollama. Não atualize a tag durante o ensaio, pois o digest vem da consulta aos metadados anterior à geração. A mesma comparação reutiliza a seleção já aprovada para aquele nome. Para avaliar outra revisão, escolha uma tag distinta ou crie uma comparação nova. A indisponibilidade posterior do modelo não impede a leitura da seleção guardada e validada.

Esta entrega testou o adaptador com respostas simuladas e um servidor HTTP de teste. A qualidade da seleção e o consumo de memória de um LLM real ainda precisam ser verificados na instalação do laboratório.

## Usar a API

Troque `ID` pelo identificador da comparação. As leituras abaixo funcionam sem modelo configurado.

```bash
curl --fail http://127.0.0.1:8000/api/v1/comparacoes/ID/relatorio
curl --fail http://127.0.0.1:8000/api/v1/comparacoes/ID/relatorio.md -o relatorio.md
curl --fail http://127.0.0.1:8000/api/v1/comparacoes/ID/relatorio.json -o relatorio.json
```

O POST explícito solicita a seleção opcional para uma comparação concluída. Ele dispensa corpo e chave de criação de trabalho.

```bash
curl --fail -X POST http://127.0.0.1:8000/api/v1/comparacoes/ID/relatorio
```

Uma comparação ainda sem checkpoint devolve 409. ID inexistente devolve 404. Um resultado que diverge do hash de conclusão, de sua configuração ou do contrato do relator devolve 409. Modelo desativado ou indisponível devolve o relatório determinístico com `fallback_reason`. Um relator ocupado devolve 429. Os limites de Host e origem são os mesmos da [API local](api-local.md).
