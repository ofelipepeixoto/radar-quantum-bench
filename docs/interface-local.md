# Usar a bancada pelo navegador

A interface Astro usa a API e o executor já instalados no computador do laboratório. O navegador mostra a configuração, o histórico e os resultados. As medições continuam no processo Python, e o SQLite guarda os trabalhos. Todos os recursos da página, incluindo as fontes, são servidos pela própria instalação.

## Preparar a interface

Na raiz do repositório, ative o ambiente Python 3.12 e instale as dependências da API. Para compilar a interface, use Node 22.23.4 ou posterior e npm 9.6.5 ou posterior. A entrega foi verificada com Node 24.22.3 e npm 11.19.1. A instalação inicial requer acesso aos pacotes. Depois do build, a página pode usar os arquivos locais.

```bash
python -m pip install -r requirements-api.txt
cd web
npm ci
npm run check
npm run build
cd ..
python -m radar_quantum_bench.local serve --data-dir local-data
```

Em outro terminal, na raiz e com o mesmo ambiente Python ativado, execute:

```bash
python -m radar_quantum_bench.local worker --data-dir local-data
```

Abra `http://127.0.0.1:8000` no navegador. O servidor carrega o build de `web/dist` ao iniciar. Se ele já estava em execução quando a interface foi compilada, reinicie-o. Uma instalação sem build devolve uma mensagem com os comandos necessários. As rotas da API continuam disponíveis nessa situação.

## Executar uma comparação

Escolha Bell, GHZ ou Bernstein-Vazirani. A prévia apresenta o circuito e seus resultados ideais. As opções avançadas permitem informar uma semente. Ao deixar o campo vazio, o servidor usa a semente padrão do circuito.

O botão Executar comparação envia uma única solicitação à fila. A tela acompanha as duas condições, com dez repetições de 1.024 medições em cada uma. O endereço passa a incluir o identificador da comparação. Recarregar esse endereço recupera o mesmo trabalho. O histórico permite abrir novamente uma comparação já registrada.

Quando as duas condições estiverem completas, confira as métricas e as contagens. O gráfico e a tabela usam as mesmas palavras de bits e a mesma ordem. As barras representam probabilidades de 0% a 100%. A tabela mostra também os resultados de contagem zero. A taxa de resultados esperados usa o conjunto previsto na teoria ideal do circuito. A TVD mede a distância entre a distribuição observada e essa referência.

Baixar pacote ZIP entrega o mesmo pacote científico da API. Repetir configuração cria outro trabalho com a mesma semente. Testar outra semente cria outro trabalho com uma semente diferente. O trabalho original continua no histórico.

## Interrupções e recusas

Se uma resposta de envio se perder, a tela conserva a chave e os parâmetros na aba do navegador. Confirmar envio anterior consulta o mesmo pedido por reenvio idempotente. A reconexão de leitura atualiza o catálogo, o histórico ou a comparação. Uma recusa definitiva da API, como fila cheia ou parâmetros inválidos, libera a configuração para uma tentativa corrigida.

Uma comparação parcial exibe o progresso. O download fica disponível após a conclusão confirmada pelo servidor. Quando o executor falhar, Repetir tentativa solicita a retomada dos checkpoints válidos. O [guia da API](api-local.md) descreve recuperação do executor, capacidade da fila e cópia dos dados.

## Verificação no navegador

Os testes em Playwright iniciam a API e o executor reais em um diretório temporário. Cobrem os três circuitos, teclado, histórico, recarga do endereço e ZIP. Um caso deixa a API processar o pedido e interrompe apenas a resposta para testar a confirmação sem duplicação. Os casos de fila cheia e parte das falhas de rede usam interceptação explícita no teste.

```bash
cd web
npm ci
npm run check
npm run build
npx playwright install chromium
npm run test:e2e
```

O executor Python dos testes deve ter `requirements-api.txt` instalado. A variável `RQB_TEST_PYTHON` permite apontar para esse interpretador. O Playwright usa por padrão seu Chromium instalado. A variável `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` permite testar um binário já disponível no ambiente.

A revisão automática de acessibilidade cobre as regras selecionadas WCAG A e AA no catálogo e na comparação, incluindo a largura de 320 pixels. A verificação manual e os testes com leitores de tela e participantes do laboratório ainda fazem parte do piloto. A interface usa rótulos, foco visível, padrões além de cores e tabelas em regiões com rolagem própria.

As fontes Geist e IBM Plex Mono são distribuídas com as respectivas licenças em `web/public/licencas`. O próximo marco do plano é a explicação dos resultados apoiada em evidências, antes do piloto com usuários.
