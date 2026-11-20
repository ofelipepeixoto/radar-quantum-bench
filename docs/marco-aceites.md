# Ensaios de IA real e registro dos aceites do piloto

Esta entrega parte da main `e4431dd175aeef95e315235867eead2f1daf36f5`. Ela acrescenta um registro privado de evidências, o verificador do computador e um ensaio reutilizável de modelo local real. O roteiro operacional está em [Registrar o piloto](registro-do-piloto.md).

## IA real no contrato do produto

O adaptador foi exercitado com Qwen2.5 0.5B Q4_K_M em CPU e Ollama 0.40.16, com recursos de nuvem desativados. O modelo instalado informou o digest `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67`. A licença do modelo informada pelo fornecedor é Apache-2.0. O runtime e os pesos ficaram fora do repositório e da candidata. [Ficha oficial](https://ollama.com/library/qwen2.5:0.5b)

O primeiro envio detalhado excedeu o prazo de 20 segundos nas três comparações e usou corretamente o resumo determinístico. O ajuste reduz o protocolo entre o produto e o modelo. Os fatos autorizados usam uma tabela compacta com identificador, valor, unidade, condição e precisão. O modelo responde somente com identificadores de observações permitidas. O servidor reconstrói suas referências e mantém resumo, limitações, números e sugestão sob o contrato original.

Após o ajuste, o ensaio preparatório passou em Bell, GHZ e BV, sem aquecimento, com prazo de 20 segundos e durações aproximadas de 12 a 14 segundos. O teste do ZIP final registra o digest da candidata e a revisão de origem antes de aceitar esse resultado como evidência daquela versão. Cada caso exige origem `modelo_local`, ausência de fallback, preservação dos fatos e limites e correspondência dos downloads e da reabertura. Esse ensaio cobre seleção de observações aprovadas. Ele não avalia texto livre nem representa uma execução de Garak.

As instruções do relator passaram à revisão 2. Um cache da revisão anterior recebe o resumo local enquanto uma nova seleção validada não for solicitada. As medições e os pacotes científicos antigos preservam seus hashes.

## Conferir o computador usado

`tools/verify_workstation.py` exige o ZIP e um SHA-256 esperado. O comando confere sua correspondência à candidata, verifica o alvo Linux x86_64/Python 3.12 e as dependências, extrai uma cópia temporária e executa o percurso de ciência, API, relatórios e restauração. O recibo informa se o kernel corresponde ao WSL.

Uma execução neste ambiente Linux comprova esse percurso no ambiente registrado. Ela não declara que o operador percorreu a interface no PC Windows, usou leitor de tela ou trabalhou em outro computador físico. A integração contínua repete o comando e importa o recibo em um registro novo, com zero sessões humanas.

## Registrar as observações

`radar_quantum_bench.acceptance` inicia um registro privado ligado ao ZIP, recebe anexos por hash e calcula os critérios do piloto. Os templates públicos não contêm participantes ou resultados preenchidos. Cada pessoa recebe um código P01 a P05, os laboratórios usam A/B e os observadores usam R01 em diante. O registro distingue declarações humanas de recibos técnicos e não autentica automaticamente seus autores.

Os critérios calculados incluem quatro exportações sem ajuda em até 600 segundos, quatro interpretações corretas, cinco recálculos por colegas e cinco pessoas de dois laboratórios. O teste pareado exige três pessoas começando no notebook e duas na plataforma, com ambas as listas de sementes nos métodos. A mediana de tempo considera somente pares com ambas as exportações concluídas. O resumo informa quantos pares foram usados.

Os registros permanecem em `local-data/acceptance`. A exportação reduzida omite anexos, nomes, códigos individuais, datas e caminhos. Seu destino deve ficar fora do repositório para revisão antes de compartilhar. Nenhuma sessão humana foi inventada nesta entrega. Os casos com cinco participantes existentes nos testes são fixtures sintéticas.

## Verificações e estado

| Frente | Cobertura |
| --- | --- |
| Python | Testes de ciência, API, execução, pacote, protocolo compacto do modelo, prova local e registro de aceites |
| Interface | Build e verificação de tipos Astro, com os nove percursos existentes no navegador |
| Modelo real | Três casos, sem aquecimento, dentro do prazo padrão, sem substituir fatos ou limitações |
| Vínculo à candidata | Provas importadas precisam de digest, revisão e conteúdo correspondente. Ensaio preparatório não entra como aceite final. |
| Guardas | Evidência existente preservada, campos extras recusados, anexo divergente recusado, falha da IA não vira aprovação e registros protegidos de escrita em pastas públicas |
| Privacidade | Recibos e anexos privados por padrão, resumo reduzido e ausência de publicação automática |

A decisão de licença está organizada em [Decisão de licença](decisao-de-licenca.md), com alternativas e efeitos no modelo por laboratório. A proposta de avaliação temporária precisa resolver também o recebimento das cápsulas com código por colegas. Nenhuma concessão foi aplicada sem essa definição. O manifesto da candidata conserva `licenca_propria_pendente`.

Continuam dependendo de participação humana a licença, o percurso no PC Windows do usuário, o teste com leitor de tela, a revisão científica independente, a reprodução em outro computador físico e as cinco sessões. O núcleo técnico e a validação local de IA estão disponíveis para apoiar esses aceites.
