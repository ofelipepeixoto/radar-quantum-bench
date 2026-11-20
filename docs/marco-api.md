# Terceiro marco do Radar Quantum Bench

A implementação parte da main f6b6323a02762a7548b265a1d7aa3823ad0f2938. Bell, GHZ e Bernstein-Vazirani já estavam disponíveis. Esta entrega conecta o executor científico a uma API local, a uma fila transacional e a um histórico SQLite.

## O que foi entregue

| Parte | Comportamento implementado |
| --- | --- |
| Envio | Catálogo fechado e configuração validada. A mesma chave com os mesmos parâmetros recupera o mesmo ID. Parâmetros diferentes com a mesma chave devolvem conflito. |
| Capacidade | Até 32 trabalhos ativos na instalação padrão. O limite e a inserção pertencem à mesma transação. |
| Histórico | Banco persistente com estado, configuração e tentativas do executor. Consulta paginada e progresso obtido dos checkpoints científicos. |
| Executor | Processo separado, uma comparação por vez. O bloqueio de arquivo impede dois executores de recuperar ou processar a mesma instalação simultaneamente. |
| Recuperação | Um novo executor registra as tentativas interrompidas e continua as medições pendentes. Se o JSON já estiver completo, conclui o trabalho sem medir novamente. |
| Resultado | Métricas completas ou parciais. Exportação ZIP só após conclusão. Circuito e semente conferidos contra o banco, com hash do arquivo final registrado no SQLite. |
| Operação | Servidor em loopback, verificação de Host e de origem apresentada, configuração de dependências travada e guia de cópia e restauração. |

Os arquivos científicos e os três ZIPs do marco anterior foram preservados. As dependências adicionais da API ficam em requirements-api.txt. A API exporta a cápsula científica já implementada. A operação da fila usa os novos módulos do repositório. [Guia de uso](api-local.md)

## Verificação realizada

A suíte passou com 52 testes em Python 3.12.14 no Linux x86_64, com Qiskit 2.6.2 e Aer 0.18.4. Os testes acrescentados cobrem envio simultâneo em oito conexões, limite da fila, idempotência, reivindicação exclusiva, tentativas antigas, falhas parciais e leitura após reinício.

Dois cenários interromperam processos reais. O primeiro encerrou o executor durante uma comparação, enquanto o segundo encerrou após salvar todas as medições e antes de confirmar a conclusão no SQLite. A recuperação preservou os IDs, as tentativas anteriores e as contagens. No segundo caso, todos os bytes do JSON permaneceram iguais e o simulador não foi chamado de novo.

Um ensaio pelo endereço HTTP de loopback iniciou a API pelo comando documentado, enviou GHZ, repetiu a mesma chave, executou o worker e baixou o ZIP. O resultado somou 20.480 medições e o arquivo passou pelo verificador. Com os processos encerrados, o diretório de dados foi copiado para outra pasta. Reiniciar a API com a cópia preservou o histórico, as métricas e o hash do resultado.

A revisão de código corrigiu o uso de páginas de documentação com JavaScript externo e a associação dos arquivos ao trabalho esperado. Os testes incluem campos inválidos, origem e Host inesperados, troca de JSON entre trabalhos de mesma configuração e leitura de arquivos de outro circuito ou semente. Em checkpoints parciais e registros anteriores sem hash final, a associação disponível se limita a circuito e semente. A integração contínua instala as dependências da API e repete a suíte completa.

O ambiente de testes emite um aviso de descontinuação do transporte HTTPX clássico no TestClient do Starlette. As versões estão fixadas e os testes passaram. A próxima atualização dessas dependências deverá verificar esse transporte.

## Próximo marco

Construir a interface em português com Astro consumindo a API local. As primeiras telas serão catálogo, configuração, andamento e comparação. O aceite será executar um circuito pelo navegador, reabrir a comparação pelo ID e exportar os mesmos dados exibidos na tabela. Gráficos devem acompanhar uma tabela equivalente e navegação completa por teclado. [Telas e piloto previstos](piloto-e-telas.md)

O piloto com usuários e a modalidade compartilhada entre instituições terão seus aceites próprios. A instalação desta entrega opera no computador do laboratório e usa CPU.
