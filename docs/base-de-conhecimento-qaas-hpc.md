# Do simulador local a um possível serviço quântico

O Radar Quantum Bench já permite responder a uma pergunta concreta: como muda a distribuição de um circuito quando o simulador inverte cada bit medido com probabilidade de 2%? O PDF *1) Visão e posicionamento*, recebido em 21 de novembro de 2026, faz uma pergunta de outra escala: como oferecer acesso a processadores quânticos como serviço (QaaS), combinando-os com computação de alto desempenho (HPC)? Esta página liga as duas ideias e indica que evidência justificaria cada passo. [Coletas do Bench](../examples/catalogo/) · [Registro da fonte](../knowledge/sources.json)

### O que veio do documento

As páginas 1 a 3 apresentam quatro zonas e descrevem como processamento, armazenamento e controle poderiam trabalhar juntos. As páginas 4 a 6 esboçam um campus modular e um horizonte de **36 a 60 meses**. As páginas 6 a 8 e 12 a 14 distinguem um local preparado para receber equipamentos (*Q-Ready*, rota A) de uma instalação com um processador quântico próprio (rota B). Esses prazos pertencem ao cenário do autor. O projeto decide cada expansão pela evidência disponível. A política vigente mantém as integrações locais e gratuitas, a execução paga desabilitada e a validação com compradores adiada pelo responsável. [Contrato público](../PUBLIC-CONTRACT.json)

| Zona proposta na p. 1 | O que representa | Como isso orienta o software |
| --- | --- | --- |
| **ZQ · Equipamento quântico** | Processadores quânticos (QPUs), instrumentação e condições físicas de operação | Se surgir acesso a dispositivo, registrar modelo, horário e calibração disponível. Hoje o identificador do executor aponta para o simulador. |
| **ZH · Computação de alto desempenho** | CPU e GPU para simulação e etapas clássicas | Medir primeiro duração e resultado em CPU. Uma comparação futura com GPU precisa de uma tarefa definida, do mesmo conjunto de entradas e de um registro do ambiente. |
| **ZD · Dados** | Amostras, arquivos de experimento e armazenamento | Vincular configuração, sementes, contagens, versões e relatório. Conferir por hash qual arquivo outra pessoa recebeu. |
| **ZO · Operação e controle** | Filas, acompanhamento e, em uma instalação física, controle dos instrumentos | No software, conservar a sequência de tentativas e a relação entre trabalho e resultado. Introduzir controle de instrumento somente com um responsável e um protocolo próprio. |

### Onde entram os 12 produtos

As zonas abaixo indicam dependências para testar cada ideia. ZQ, nas linhas de sensores, identifica uma futura dependência de instrumento. Um sensor pode fornecer medições sem que o produto use uma QPU.

| Produto | Zonas de interesse | Primeira evidência que faz sentido buscar |
| --- | --- | --- |
| Radar Quantum Bench | ZH, ZD | Recalcular a comparação de Bell, GHZ ou Bernstein-Vazirani a partir das contagens exportadas. |
| Radar Quantum Ops | ZO, ZD | Rastrear uma tentativa interrompida até seu resultado final e conferir o recibo no laboratório de origem. |
| Quantum Code Copilot | ZH, ZD | Revisar um circuito proposto e comparar sua saída com um caso de referência reservado. |
| Camaleão Quantum Lab | ZH, ZD | Usar as mesmas contagens em um exercício no qual o aluno explique a diferença entre previsão e amostra. |
| Quantum Optimize | ZH, ZD | Resolver uma instância pequena em condições equivalentes e comparar com um método clássico que respeite as mesmas restrições. |
| Quantum Materials Lab | ZH, ZD | Comparar energias calculadas para a mesma geometria e base, com unidades e referência revisadas por especialista. |
| Quantum ML Bench | ZH, ZD | Comparar modelos clássicos e quânticos com a mesma divisão de dados e critérios de avaliação. |
| Quantum Noise Studio | ZH, ZD, futura ZQ | Comparar o modelo sintético a uma distribuição conhecida. Para testar se representa um dispositivo, obter medições identificadas desse dispositivo. |
| Quantum Calibrate | ZQ, ZO, ZD | Um laboratório parceiro mede uma referência antes e depois de uma calibração e registra condições e incerteza. |
| Quantum Sensor Studio | ZQ, ZD | Comparar uma série temporal autorizada com um instrumento de referência, preservando unidade, horário e calibração. |
| Quantum Navigation Lab | ZD, ZH, futura ZQ | Começar com trajetória civil simulada e referência conhecida. A etapa geofísica exige mapa apropriado, medições reais e revisão de especialista. |
| Radar PQC | ZO, ZD | Conferir um inventário criptográfico autorizado em computadores convencionais. Uma QPU fica fora das dependências desse ensaio. |

Os produtos aparecem aqui como aplicação das quatro zonas ao portfólio do projeto. A tabela original conserva os objetivos, dependências e critérios de cada produto. [Mapa do ecossistema](ecossistema-quantico.md)

### Condições para mudar de etapa

| Etapa | O que torna possível avaliá-la |
| --- | --- |
| **1. Bench em CPU, disponível** | Abrir o pacote de referência, recuperar a semente e recalcular a distribuição e as métricas. Cada circuito reúne 20.480 medições avaliadas, repartidas entre leitura ideal e leitura com ruído. [Protocolo](protocolo-cientifico.md) |
| **2. Operação por laboratório, na camada privada de software** | Verificar isolamento entre dois laboratórios, limites de fila, retomada de uma tentativa e vínculo entre resultado e recibo. O núcleo público segue como referência científica reproduzível. |
| **3. Orquestração híbrida, proposta** | Demonstrar em ambiente local gratuito como encaminhar uma etapa clássica e uma etapa simulada, registrar espera e execução separadamente e recuperar uma falha. Uma integração física posterior depende de acesso autorizado e de nova decisão. |
| **4. Instalação Q-Ready, possível** | Identificar uma necessidade que o software e o acesso remoto disponíveis não atendam. Uma equipe de engenharia deve verificar as condições do local, a energia, a refrigeração, os requisitos do instrumento e a segurança de operação. Ver pp. 7, 12 e 13 da proposta. |
| **5. QPU própria, condicional** | Reavaliar demanda documentada, capacidade de operação, acesso a suporte do fabricante e parecer de especialistas. O PDF trata dessa decisão nas pp. 8, 13 e 14. A compra de equipamentos requer decisão específica futura. |

### Como ler as métricas

No Bench, **2% é a probabilidade configurada de inverter cada bit na leitura simulada**. Para Bell, isso prevê 96,08% de resultados com os bits iguais. A amostra publicada deu 96,2207%. As contagens medem o que o simulador produziu sob essa regra. Fidelidade de portas e os tempos quânticos T1 e T2 pedem caracterização do dispositivo, indicação dos qubits e data da medição. A p. 5 do PDF reúne essas métricas físicas como objetivos futuros. [Referência do Bench](../examples/catalogo/bell.json) · [IBM Quantum sobre caracterização e calibração](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/calibration-jobs)

Na simulação local, o tempo descreve a execução na máquina que fez o ensaio. Para estudar a eficiência de uma instalação real, o PUE relaciona a energia total consumida à energia dos equipamentos de TI no mesmo período. Um estudo do coeficiente de desempenho da refrigeração (COP) requer carga térmica, energia fornecida e condições de operação medidas. A escolha da fronteira de medição cabe à engenharia do local. O PDF aborda esses indicadores nas pp. 1, 8 e 12. [Guia de eficiência energética em centros de dados, seção 8](https://www.energy.gov/sites/default/files/2024-07/best-practice-guide-data-center-design.pdf)

As pp. 5 e 6 também levantam a correção quântica de erros (QEC). Um modelo pode servir para estudar um código. Demonstrar correção em equipamento físico exige protocolo de teste, medições e revisão científica próprios. Cada relatório deve identificar se a evidência veio de simulação, caracterização do instrumento ou observação de campo.

**Proveniência.** A fonte `user-vision-positioning-01` é uma proposta fornecida pelo responsável pelo projeto, com 14 páginas. As referências técnicas externas esclarecem definições específicas. O arquivo original pode ser identificado pelo SHA-256 `2ee04e640b2a1981d88e92ee02029adddb329d0251ce4102c216dd0f936d5669`. [Registro de proveniência](../knowledge/sources.json)
