"""Relato local com fatos verificáveis e seleção opcional de frases por modelo.

A resposta do modelo só pode ordenar ou selecionar frases já calculadas. Valores,
unidades, limites científicos e identificadores são preenchidos neste módulo.
"""

from copy import deepcopy
from math import isfinite
import re
from uuid import UUID

from .experiment import validate
from .metrics import specifications

SCHEMA_VERSION = "rqb-report/1"
PROMPT_REVISION = "1"
CONDITIONS = ("ideal", "readout_2pct")
LABELS = {"ideal": "Ideal", "readout_2pct": "Erro de leitura de 2% por bit"}
FALLBACK_REASONS = frozenset(("modelo_indisponivel", "tempo_esgotado", "proposta_invalida",
                              "resposta_invalida", "modelo_ocupado", "registro_invalido",
                              "modelo_desativado", "modelo_remoto_bloqueado"))
_MODEL_ID = re.compile(r"[\w.:/@+-]{1,192}", re.ASCII)


def _number(value, precision=0):
    text = f"{value:,.{precision}f}"
    return text.translate(str.maketrans({",": ".", ".": ","}))


def _reference(node):
    return {"frase_id": node["frase_id"], "fato_ids": list(node["fato_ids"])}


def _base_proposal(report):
    return {
        "estado": report["estado"],
        "resumo": _reference(report["resumo"]),
        "observacoes": [_reference(node) for node in report["observacoes"]],
        "limitacoes": [_reference(node) for node in report["limitacoes"]],
        "proximo_teste": _reference(report["proximo_teste"]) if report["proximo_teste"] else None,
    }


def model_input(report):
    """Dados mínimos de uma comparação, com vocabulário fechado de saída."""
    return {"fatos": deepcopy(report["fatos"]), "proposta_base": _base_proposal(report)}


def _selection(proposal, report):
    base = _base_proposal(report)
    if type(proposal) is not dict or set(proposal) != set(base):
        raise ValueError("Campos incompatíveis com o contrato.")
    for key in ("estado", "resumo", "limitacoes", "proximo_teste"):
        if proposal[key] != base[key]:
            raise ValueError("A proposta alterou uma seção obrigatória.")
    rows = proposal["observacoes"]
    if type(rows) is not list or not 1 <= len(rows) <= len(base["observacoes"]):
        # Com zero medições, nenhuma observação é permitida.
        if not (rows == [] and base["observacoes"] == []):
            raise ValueError("Seleção de observações inválida.")
    seen = set()
    selected = []
    for row in rows:
        if type(row) is not dict or set(row) != {"frase_id", "fato_ids"}:
            raise ValueError("Uma observação contém conteúdo livre.")
        if type(row["frase_id"]) is not str or type(row["fato_ids"]) is not list:
            raise ValueError("Tipos de observação incompatíveis.")
        if row not in base["observacoes"] or row["frase_id"] in seen:
            raise ValueError("A frase ou as evidências pertencem a outro relato.")
        seen.add(row["frase_id"])
        selected.append(next(deepcopy(node) for node in report["observacoes"]
                             if node["frase_id"] == row["frase_id"]))
    return selected


def build_report(document, *, job_id, result_sha256, proposal=None, model_id=None,
                 fallback_reason=None):
    """Produzir o resumo determinístico, com alternativa segura para IA inválida.

    O chamador calcula result_sha256 dos bytes do JSON e confere sua associação
    ao trabalho. Este módulo valida o documento científico e usa seus valores.
    """
    validate(document)
    simulator = document["environment"]["simulator"]
    if (not isinstance(simulator, dict) or simulator.get("name") != "AerSimulator"
            or simulator.get("device") != "CPU"):
        raise ValueError("O relatório exige uma simulação Aer em CPU.")
    job_id = str(UUID(job_id))
    if not isinstance(result_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", result_sha256):
        raise ValueError("Digest do resultado inválido.")
    if model_id is not None and (type(model_id) is not str or not _MODEL_ID.fullmatch(model_id)):
        raise ValueError("Identificação do modelo inválida.")
    if fallback_reason is not None and fallback_reason not in FALLBACK_REASONS:
        raise ValueError("Motivo de alternativa desconhecido.")
    config, summary = document["config"], document["summary"]
    circuit = config["circuit"]
    spec = specifications(circuit)
    facts = []

    def fact(identifier, value, unit, condition, precision, pointer, calculation=None):
        if type(value) in (float, int) and not isfinite(value):
            raise ValueError("Fato numérico não finito.")
        entry = {"id": identifier, "valor": value, "unidade": unit,
                 "condicao": condition, "precisao": precision, "origem": pointer}
        if calculation:
            entry["calculo"] = calculation
        facts.append(entry)
        return identifier

    def node(identifier, ids, text):
        item = {"frase_id": identifier, "fato_ids": list(ids), "texto": text}
        return item

    fact("circuito", circuit, "identificador", None, None, "/config/circuit")
    fact("shots_por_repeticao", config["shots"], "medições", None, 0, "/config/shots")
    fact("repeticoes_por_condicao", config["repetitions"], "repetições", None, 0, "/config/repetitions")
    fact("total_shots", summary["total_shots"], "medições", None, 0, "/summary/total_shots")
    fact("simulador", "AerSimulator em CPU", "ambiente", None, None,
         "/environment/simulator", "catálogo local validado")
    fact("base_medicao", "Z", "base", None, None, "/environment/logical_qasm_sha256",
         "catálogo de circuitos com medição na base computacional")
    fact("ruido_por_bit", 2.0, "%", "readout_2pct", 0,
         "/environment/noise_model/readout_2pct/readout_flip_probability", "100 × probabilidade")
    fact("intervalo_metodo", "Wilson 95%", "método", None, None, "/summary/conditions",
         "intervalo binomial de Wilson, z = 1,959963984540054")
    theory_ids = []
    for word in spec["words"]:
        theory_ids.append(fact(f"teoria_ideal.{word}", spec["ideal"][word], "probabilidade",
                               "ideal", 6, f"/theoretical_probabilities/ideal/{word}"))
    observations, progress_ids, progress_text = [], [], []
    for condition in CONDITIONS:
        row = summary["conditions"][condition]
        prefix = f"/summary/conditions/{condition}/"
        repetition_id = fact(f"{condition}.repeticoes", row["completed_repetitions"],
                             "repetições", condition, 0, prefix + "completed_repetitions")
        progress_ids.append(repetition_id)
        progress_text.append(f"{LABELS[condition]} concluiu {row['completed_repetitions']} "
                             f"de {config['repetitions']} repetições")
        count_ids = []
        for word in spec["words"]:
            count_ids.append(fact(f"{condition}.contagem.{word}", row["counts"][word],
                                  "medições", condition, 0, prefix + f"counts/{word}"))
        fact(f"{condition}.total", row["total_shots"], "medições", condition, 0, prefix + "total_shots")
        if not row["total_shots"]:
            continue
        fact(f"{condition}.validos", row["valid_shots"], "medições", condition, 0, prefix + "valid_shots")
        fact(f"{condition}.taxa", row["valid_fraction"] * 100, "%", condition, 4,
             prefix + "valid_fraction", "100 × proporção")
        for index, suffix in enumerate(("inferior", "superior")):
            fact(f"{condition}.wilson_{suffix}", row["wilson95"][index] * 100, "%", condition, 4,
                 prefix + f"wilson95/{index}", "100 × proporção")
        fact(f"{condition}.tvd", row["tvd"], "adimensional", condition, 6, prefix + "tvd")
        fact(f"{condition}.mediana", row["median_ms"], "ms", condition, 3, prefix + "median_ms")
        fact(f"{condition}.iqr", row["iqr_ms"], "ms", condition, 3, prefix + "iqr_ms")
        theory = sum(document["theoretical_probabilities"][condition][word]
                     for word in spec["words"] if spec["ideal"][word])
        fact(f"{condition}.taxa_teorica", theory * 100, "%", condition, 4,
             f"/theoretical_probabilities/{condition}", "100 × soma no suporte ideal")
        support = ", ".join(word for word in spec["words"] if spec["ideal"][word])
        observations.append(node(f"{condition}.taxa", [f"{condition}.{suffix}" for suffix in
            ("validos", "total", "taxa", "wilson_inferior", "wilson_superior", "taxa_teorica")] + count_ids + ["intervalo_metodo"],
            f"{LABELS[condition]} registrou {_number(row['valid_shots'])} de "
            f"{_number(row['total_shots'])} medições no conjunto esperado ({support}), "
            f"equivalentes a {_number(row['valid_fraction'] * 100, 4)}%. "
            f"O intervalo de Wilson de 95% vai de {_number(row['wilson95'][0] * 100, 4)}% "
            f"a {_number(row['wilson95'][1] * 100, 4)}%. "
            f"A taxa teórica para esta condição é {_number(theory * 100, 4)}%."))
        observations.append(node(f"{condition}.tvd", [f"{condition}.tvd", "circuito"] + count_ids + theory_ids,
            f"{LABELS[condition]} tem TVD de {_number(row['tvd'], 6)} em relação à distribuição "
            "teórica ideal. A TVD é adimensional e considera todas as palavras de bits."))
        observations.append(node(f"{condition}.tempo", [f"{condition}.mediana", f"{condition}.iqr"],
            f"{LABELS[condition]} tem tempo mediano local de {_number(row['median_ms'], 3)} ms "
            f"e intervalo interquartil de {_number(row['iqr_ms'], 3)} ms."))
    state = "completo" if summary["complete"] else "parcial" if summary["total_shots"] else "inconclusivo"
    overview = node(f"resumo.{state}", ["circuito", "total_shots", "shots_por_repeticao",
                    "repeticoes_por_condicao"] + progress_ids,
                    f"A comparação {spec['label']} está {state} e registra "
                    f"{_number(summary['total_shots'])} medições avaliadas. " + ". ".join(progress_text) + ".")
    if state == "completo":
        delta = (summary["conditions"]["readout_2pct"]["valid_fraction"] -
                 summary["conditions"]["ideal"]["valid_fraction"]) * 100
        fact("variacao_taxa", delta, "p.p.", "ambas", 4, "/summary/conditions",
             "100 × (readout_2pct.valid_fraction − ideal.valid_fraction)")
        direction = "menor" if delta < 0 else "maior" if delta > 0 else "igual"
        observations.append(node(f"variacao_taxa.{direction}",
            ["ideal.taxa", "readout_2pct.taxa", "variacao_taxa"],
            f"A taxa no conjunto esperado foi {direction} com ruído. "
            f"A variação observada, ruído menos ideal, foi {_number(delta, 4)} p.p. "
            "Esta diferença descritiva, sozinha, não demonstra uma causa em hardware físico."))
    limitations = [
        node("limite.simulacao", ["simulador", "ruido_por_bit"],
             "Os dados vêm de simulação local em CPU, com erro de leitura sintético de 2% por bit. "
             "Este ensaio não comprova vantagem quântica nem desempenho de um processador físico."),
        node("limite.tempo", ["simulador"],
             "O tempo cobre a chamada local ao Aer e a recuperação das contagens na máquina usada. "
             "Fila, compilação e aquecimento ficam fora desta mediana."),
        node("limite.incerteza", ["shots_por_repeticao", "intervalo_metodo"],
             "O intervalo de Wilson descreve a incerteza da proporção observada sob o modelo binomial. "
             "Ele não mede a fidelidade do estado quântico."),
    ]
    if circuit in ("bell", "ghz"):
        limitations.append(node("limite.base_z", ["base_medicao", "circuito"],
            "As contagens na base Z mostram correlações nas leituras. "
            "Essas medições isoladas não atestam emaranhamento."))
    if state != "completo":
        limitations.append(node("limite.parcial", progress_ids + ["repeticoes_por_condicao"],
            "Faltam medições ou aquecimentos do protocolo. " + ". ".join(progress_text) + ". "
            "O relato não conclui a comparação entre as condições."))
    next_test = node("hipotese.outra_semente", ["circuito"],
        "Hipótese para um próximo teste, repetir a configuração com outra semente pode ajudar "
        "a examinar a variação de amostragem. Iniciar a execução depende de sua ação na bancada.") if state == "completo" else None
    report = {"schema_version": SCHEMA_VERSION, "prompt_revision": PROMPT_REVISION,
              "origem_dados": "simulador-local-cpu", "origem_texto": "deterministico", "modelo": model_id,
              "fallback_reason": fallback_reason, "job_id": job_id, "run_id": str(UUID(document["run_id"])),
              "result_sha256": result_sha256, "circuit": circuit,
              "estado": state, "resumo": overview, "observacoes": observations,
              "limitacoes": limitations, "proximo_teste": next_test, "fatos": facts}
    if proposal is not None and fallback_reason is None:
        try:
            if model_id is None:
                raise ValueError("Modelo não identificado.")
            report["observacoes"] = _selection(proposal, report)
            report["origem_texto"] = "modelo_local"
        except (ValueError, TypeError, KeyError):
            report["fallback_reason"] = "proposta_invalida"
    return report


def report_to_markdown(report):
    """Exportar o mesmo texto e suas evidências, sem interpretar HTML do modelo."""
    metadata = report
    lines = ["# Radar Quantum Bench · relatório de evidências", "",
             f"Estado {report['estado']}", f"Origem do texto {metadata['origem_texto']}",
             f"Trabalho `{metadata['job_id']}`", f"Execução `{metadata['run_id']}`",
             f"SHA-256 do resultado `{metadata['result_sha256']}`",
             f"Esquema `{metadata['schema_version']}`, instruções `{metadata['prompt_revision']}`",
             f"Modelo `{metadata['modelo'] or 'sem modelo'}`", ""]
    if report.get("modelo_versao"):
        identity = report["modelo_versao"]
        lines.extend([f"Digest do modelo informado pelo Ollama `{identity['digest']}`",
                      f"Versão do Ollama `{identity['server_version']}`", ""])
    if metadata["fallback_reason"]:
        lines.extend([f"Resumo local usado por `{metadata['fallback_reason']}`.", ""])
    for title, section in (("Resumo", [report["resumo"]]), ("Observações", report["observacoes"]),
                           ("Limitações", report["limitacoes"]),
                           ("Próximo teste", [report["proximo_teste"]] if report["proximo_teste"] else [])):
        if section:
            lines.extend([f"## {title}", ""])
            for item in section:
                ids = ", ".join(f"`{identifier}`" for identifier in item["fato_ids"])
                lines.extend([item["texto"], f"Evidências {ids}.", ""])
    lines.extend(["## Fatos usados", "", "| ID | Valor | Unidade | Condição | Origem no JSON | Cálculo |",
                  "| --- | --- | --- | --- | --- | --- |"])
    for entry in report["fatos"]:
        value = (_number(entry["valor"], entry["precisao"]) if entry["precisao"] is not None
                 else entry["valor"])
        lines.append(f"| `{entry['id']}` | {value} | {entry['unidade']} | {entry['condicao'] or 'protocolo'} "
                     f"| `{entry['origem']}` | {entry.get('calculo', 'valor da origem')} |")
    return "\n".join(lines) + "\n"
