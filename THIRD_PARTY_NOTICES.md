# Componentes de terceiros

O [inventário versionado](releases/dependencies.json) registra as 27 dependências Python das versões travadas e as 396 referências do lockfile npm. O lockfile inclui dependências de desenvolvimento e pacotes opcionais de outras plataformas. Esses números não representam arquivos binários incluídos na candidata.

O inventário usa os metadados efetivamente instalados para Python e os campos de licença e integridade do lockfile para npm. Preserva expressões compostas quando fornecidas pelo pacote. Quando o campo de licença contém um texto longo, registra seu hash e os arquivos de licença da distribuição instalada. Ele permite localizar os avisos de terceiros sem reclassificar todas as bibliotecas sob uma licença única.

## Material incluído na candidata de revisão

| Material | Origem e licença registrada | Aviso preservado |
| --- | --- | --- |
| Fontes Geist | `@fontsource-variable/geist` 5.3.0, OFL-1.1 | [Licença original](web/public/licencas/Geist-OFL.txt), também copiada para o build estático |
| Fontes IBM Plex Mono | `@fontsource/ibm-plex-mono` 5.3.0, OFL-1.1 | [Licença original](web/public/licencas/IBM-Plex-Mono-OFL.txt), também copiada para o build estático |
| Circuitos, contagens sintéticas e código do projeto | Revisão indicada no manifesto da candidata | Os pacotes científicos históricos mantêm seus próprios manifestos e fontes |

Os arquivos de Astro e Vite são obtidos pelo gerenciador de pacotes para construir a página. O inventário registra suas licenças MIT. A candidata não inclui `node_modules`, wheels Python, compiladores ou pesos de modelos. Os requisitos e o lockfile indicam como obter o ambiente de execução e teste. Os avisos desses pacotes acompanham suas próprias distribuições.

As licenças de dependências de teste, como MPL-2.0 do Axe e do Certifi, continuam identificadas no inventário. A licença Apache-2.0 de Qiskit e Aer e a expressão composta de NumPy permanecem registradas separadamente. Os arquivos instalados de SciPy também possuem avisos de componentes do binário. Se uma futura distribuição incluir wheels, containers ou outros binários, sua lista de arquivos e todos os avisos correspondentes precisarão ser conferidos para esse novo destino.

## Código próprio e decisão de distribuição

A licença do código próprio ainda depende de uma decisão do titular. Este arquivo registra componentes e preserva atribuições de terceiros. Ele não concede uma licença ao código do Radar e não declara a candidata apta para distribuição do piloto. O manifesto mantém essa pendência explícita. A preparação técnica, os testes e a revisão do pacote podem prosseguir enquanto essa decisão é registrada.

Para conferir o inventário no ambiente Python travado, execute na raiz `python tools/inventory_dependencies.py --check`. Para atualizar depois de uma mudança deliberada de dependências, execute o mesmo comando sem `--check`, revise as diferenças e gere uma nova candidata.
