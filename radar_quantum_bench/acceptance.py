"""Registrar evidências privadas do piloto e calcular seus critérios publicados.

O registro conserva declarações humanas e anexos identificados por SHA-256.
Receber uma declaração não verifica a identidade de quem a forneceu e não
substitui a revisão humana ou uma autorização de distribuição do software.
"""

import argparse
from contextlib import contextmanager
from datetime import date
import fcntl
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
from statistics import median
import tempfile

from .release import (
    DEVELOPMENT_POLICY, LEGACY_READINESS, READINESS, SCHEMA as RELEASE_SCHEMA,
    validate_development_policy, verify_release,
)


LEGACY_SCHEMA = "rqb-pilot-acceptance/1"
SCHEMA = "rqb-pilot-acceptance/2"
CHECKS = ("license", "wsl_pc", "second_computer", "scientific_review", "screen_reader", "local_model")
SEEDS = {"A": {"bell": 20261120, "ghz": 20261220, "bv": 20261320},
         "B": {"bell": 20261121, "ghz": 20261221, "bv": 20261321}}
MAX_ATTACHMENT = 2 * 1024 * 1024
_DEFAULT = Path("local-data/acceptance")
_BINDING = {"candidate_sha256", "source_revision"}


def _fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("Campos incompatíveis com o contrato do piloto.")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Campo JSON duplicado.")
        result[key] = value
    return result


def _decode(raw):
    def invalid(_):
        raise ValueError("Número JSON não finito.")
    if len(raw) > 128 * 1024:
        raise ValueError("Registro JSON excede o tamanho permitido.")
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=invalid)


def _encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _digest(value, length=64):
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", value):
        raise ValueError("Identificador de conteúdo inválido.")


def _binding(record, state):
    for key, length in (("candidate_sha256", 64), ("source_revision", 40)):
        _digest(record[key], length)
        if record[key] != state[key]:
            raise ValueError("A evidência pertence a outra candidata.")


def _date(value):
    if type(value) is not str:
        raise ValueError("Informe uma data no formato AAAA-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Informe uma data no formato AAAA-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValueError("Informe uma data no formato AAAA-MM-DD.")


def _code(value):
    if type(value) is not str or not re.fullmatch(r"R[0-9]{2}", value):
        raise ValueError("Use um código de responsável R seguido de dois dígitos.")


def _common(record, state, schema):
    if record["schema"] != schema:
        raise ValueError("Versão de registro desconhecida.")
    _binding(record, state)
    _digest(record["evidence_sha256"])
    _date(record["observed_on"])
    _code(record["observer_code"])


def _check(record, state):
    _fields(record, _BINDING | {"schema", "check", "result", "basis", "observed_on",
                               "observer_code", "evidence_sha256"})
    _common(record, state, "rqb-pilot-check/1")
    if record["check"] not in CHECKS[:-1] or record["result"] not in ("passed", "failed"):
        raise ValueError("Verificação ou resultado desconhecido.")
    if record["basis"] != "recorded_human_attestation":
        raise ValueError("Um registro humano deve ser identificado como declaração humana.")


def _method(value):
    _fields(value, {"seed_list", "duration_seconds", "help_count", "export_completed"})
    if value["seed_list"] not in SEEDS:
        raise ValueError("Lista de sementes desconhecida.")
    duration = value["duration_seconds"]
    if type(duration) not in (int, float) or not isfinite(duration) or not 0 < duration <= 86400:
        raise ValueError("A duração deve estar em segundos, acima de zero e até um dia.")
    if type(value["help_count"]) is not int or not 0 <= value["help_count"] <= 100:
        raise ValueError("Contagem de ajudas inválida.")
    if type(value["export_completed"]) is not bool:
        raise ValueError("A conclusão da exportação precisa ser booleana.")


def _session(record, state):
    _fields(record, _BINDING | {"schema", "participant", "lab", "circuit", "order",
                               "notebook", "platform", "interpretation", "peer_recalculation",
                               "observed_on", "observer_code", "evidence_sha256"})
    _common(record, state, "rqb-pilot-session/1")
    if record["participant"] not in tuple(f"P{i:02}" for i in range(1, 6)) or record["lab"] not in ("A", "B"):
        raise ValueError("Use participantes P01 a P05 e laboratórios A ou B.")
    if record["circuit"] not in ("bell", "ghz", "bv") or record["order"] not in ("notebook_first", "platform_first"):
        raise ValueError("Circuito ou ordem de tarefa desconhecido.")
    _method(record["notebook"])
    _method(record["platform"])
    if record["notebook"]["seed_list"] == record["platform"]["seed_list"]:
        raise ValueError("As tarefas pareadas precisam das listas A e B.")
    _fields(record["interpretation"], {"observed", "theory", "limitation"})
    if any(type(value) is not bool for value in record["interpretation"].values()) \
            or type(record["peer_recalculation"]) is not bool:
        raise ValueError("A compreensão e a conferência exigem valores booleanos.")
    if record["peer_recalculation"] and not record["platform"]["export_completed"]:
        raise ValueError("O recálculo do colega exige a exportação concluída na plataforma.")


def _second_round(record, state):
    _fields(record, _BINDING | {"schema", "lab", "responsible_code", "scheduled_on",
                               "commercial_interest", "observed_on", "observer_code", "evidence_sha256"})
    _common(record, state, "rqb-pilot-second-round/1")
    if record["lab"] not in ("A", "B") or record["commercial_interest"] not in ("accepted_discussion", "undecided", "not_interested"):
        raise ValueError("Laboratório ou interesse desconhecido.")
    _code(record["responsible_code"])
    _date(record["scheduled_on"])
    if record["scheduled_on"] < record["observed_on"]:
        raise ValueError("A segunda rodada precisa de uma data a partir da observação registrada.")


def _technical(receipt, state, expected_kind=None):
    if type(receipt) is not dict:
        raise ValueError("Recibo técnico inválido.")
    kind = {"rqb-local-model-verification/1": "local_model",
            "rqb-workstation-verification/1": "workstation"}.get(receipt.get("schema"))
    if kind is None or expected_kind not in (None, kind) or receipt.get("status") != "passed":
        raise ValueError("O recibo técnico não registra uma verificação aprovada.")
    source = receipt.get("source")
    _fields(source, {"candidate_sha256", "source_revision", "content_matches_manifest"})
    _binding(source, state)
    if source["content_matches_manifest"] is not True:
        raise ValueError("A origem do recibo não foi conferida.")
    if kind == "local_model":
        _fields(receipt, {"schema", "status", "source", "model", "timeout_seconds", "warmup",
                          "environment", "reopened_without_model", "cases", "real_model_selected",
                          "scope", "new_scientific_executions", "preparatory"})
        if (receipt["real_model_selected"] is not True or receipt["reopened_without_model"] is not True
                or receipt["preparatory"] is not False
                or type(receipt["new_scientific_executions"]) is not int
                or receipt["new_scientific_executions"] != 0
                or receipt["scope"] != "selecao_de_frases_do_catalogo_sem_avaliacao_de_texto_livre"):
            raise ValueError("O recibo não confirma a seleção local prevista.")
        model = receipt["model"]
        if type(model) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}", model):
            raise ValueError("Modelo inválido no recibo.")
        timeout = receipt["timeout_seconds"]
        if type(timeout) not in (int, float) or not isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("Prazo inválido no recibo.")
        rows = receipt["cases"]
        if type(rows) is not list or len(rows) != 3:
            raise ValueError("O recibo precisa conferir os três circuitos.")
        seen = set()
        for row in rows:
            _fields(row, {"circuit", "status", "origin", "fallback_reason", "elapsed_ms", "model_identity",
                          "source_result_sha256", "selected_phrase_ids", "facts_preserved",
                          "limits_preserved", "exports_match"})
            if (row["circuit"] not in ("bell", "ghz", "bv") or row["circuit"] in seen
                    or row["status"] != "passed" or row["origin"] != "modelo_local"
                    or row["fallback_reason"] is not None
                    or any(row[key] is not True for key in ("facts_preserved", "limits_preserved", "exports_match"))):
                raise ValueError("Resultado local incompleto no recibo.")
            seen.add(row["circuit"])
            elapsed = row["elapsed_ms"]
            if type(elapsed) not in (int, float) or not isfinite(elapsed) or not 0 <= elapsed <= 180000:
                raise ValueError("Duração inválida no recibo.")
            _digest(row["source_result_sha256"])
            _fields(row["model_identity"], {"name", "digest", "server_version"})
            if row["model_identity"]["name"] != model:
                raise ValueError("Identidade do modelo divergente.")
            _digest(row["model_identity"]["digest"])
            version = row["model_identity"]["server_version"]
            if type(version) is not str or not re.fullmatch(r"[A-Za-z0-9._+:-]{1,80}", version):
                raise ValueError("Versão do modelo inválida.")
            phrases = row["selected_phrase_ids"]
            if (type(phrases) is not list or not 1 <= len(phrases) <= 16
                    or any(type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", value)
                           for value in phrases) or len(set(phrases)) != len(phrases)):
                raise ValueError("Seleção de frases inválida no recibo.")
    else:
        _fields(receipt, {"schema", "status", "prerequisites", "target", "source", "probe", "scope"})
        target = receipt["target"]
        if (type(target) is not dict or target.get("os") != "Linux" or target.get("architecture") != "x86_64"
                or type(target.get("python")) is not str or not target["python"].startswith("3.12.")
                or type(target.get("is_wsl")) is not bool
                or type(receipt["probe"]) is not dict or receipt["probe"].get("status") != "passed"
                or receipt["scope"] != "environment-automation-not-human-review"):
            raise ValueError("Ambiente técnico incompatível com esta candidata.")
    return kind


def import_technical(directory, path):
    raw = Path(path).read_bytes()
    receipt = _decode(raw)
    with _locked(directory) as root:
        state = _load(root)
        kind = _technical(receipt, state)
        entries = state["technical_receipts"][kind]
        digest = sha256(raw).hexdigest()
        if digest in entries:
            return
        if len(entries) >= 20:
            raise ValueError("O histórico técnico atingiu seu limite.")
        _attachment(root, digest, path)
        entries.append(digest)
        _save(root, state)


def _root(directory):
    root = Path(directory).resolve()
    project = Path(__file__).resolve().parents[1]
    if root.is_relative_to(project) and not root.is_relative_to(project / "local-data"):
        raise ValueError("Dentro do projeto, guarde os registros somente em local-data.")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


@contextmanager
def _locked(directory):
    root = _root(directory)
    with (root / ".acceptance.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield root


def _save(root, state):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".record-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(_encoded(state))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(root / "acceptance.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _attachment(root, digest, path=None):
    folder = root / "attachments"
    folder.mkdir(mode=0o700, exist_ok=True)
    stored = folder / digest
    source = Path(path) if path is not None else stored
    if source.is_symlink() or source.stat().st_size > MAX_ATTACHMENT:
        raise ValueError("Anexo ausente, simbólico ou grande demais.")
    raw = source.read_bytes()
    if not raw or sha256(raw).hexdigest() != digest:
        raise ValueError("O anexo difere da evidência declarada.")
    if path is not None and not stored.exists():
        with stored.open("xb") as stream:
            os.chmod(stored, 0o600)
            stream.write(raw)
    elif stored.exists() and sha256(stored.read_bytes()).hexdigest() != digest:
        raise ValueError("O anexo guardado requer revisão.")


def _load(root):
    state = _decode((root / "acceptance.json").read_bytes())
    if type(state) is not dict:
        raise ValueError("Registro do piloto inválido.")
    base_fields = {"schema", "candidate_sha256", "source_revision", "candidate_readiness",
                   "model_enabled", "checks", "sessions", "second_round", "technical_receipts"}
    current = state.get("schema") == SCHEMA
    _fields(state, base_fields | {"candidate_license", "development_policy"} if current else base_fields)
    if state["schema"] not in (LEGACY_SCHEMA, SCHEMA) or type(state["model_enabled"]) is not bool:
        raise ValueError("Registro do piloto inválido.")
    _digest(state["candidate_sha256"])
    _digest(state["source_revision"], 40)
    if state["candidate_readiness"] != (READINESS if current else LEGACY_READINESS):
        raise ValueError("Política da candidata incompatível com esta versão.")
    if current:
        _fields(state["candidate_license"], {"spdx", "license_sha256", "notice_sha256", "scope_sha256"})
        if state["candidate_license"]["spdx"] != "Apache-2.0":
            raise ValueError("Licença incompatível.")
        validate_development_policy(state["development_policy"])
        for key in ("license_sha256", "notice_sha256", "scope_sha256"):
            _digest(state["candidate_license"][key])
    _fields(state["technical_receipts"], {"local_model", "workstation"})
    for kind, digests in state["technical_receipts"].items():
        if type(digests) is not list or len(digests) > 20:
            raise ValueError("Histórico técnico inválido.")
        for digest in digests:
            _digest(digest)
            _attachment(root, digest)
            _technical(_decode((root / "attachments" / digest).read_bytes()), state, kind)
    _fields(state["checks"], CHECKS)
    for check, entries in state["checks"].items():
        if type(entries) is not list or len(entries) > 20:
            raise ValueError("Histórico de verificações inválido.")
        for record in entries:
            _check(record, state)
            if record["check"] != check:
                raise ValueError("Histórico de outra verificação.")
            _attachment(root, record["evidence_sha256"])
    if type(state["sessions"]) is not list or len(state["sessions"]) > 5:
        raise ValueError("Número de sessões inválido.")
    participants = set()
    for record in state["sessions"]:
        _session(record, state)
        if record["participant"] in participants:
            raise ValueError("Participante repetido.")
        participants.add(record["participant"])
        _attachment(root, record["evidence_sha256"])
    if state["second_round"] is not None:
        _second_round(state["second_round"], state)
        _attachment(root, state["second_round"]["evidence_sha256"])
    return state


def initialize(candidate, directory=_DEFAULT, *, expected_sha256, model_enabled=False):
    if type(model_enabled) is not bool:
        raise ValueError("A escolha do modelo precisa ser booleana.")
    path = Path(candidate)
    _digest(expected_sha256)
    manifest = verify_release(path, expected_sha256=expected_sha256)
    current = manifest.get("schema") == RELEASE_SCHEMA
    state = {"schema": SCHEMA if current else LEGACY_SCHEMA,
             "candidate_sha256": sha256(path.read_bytes()).hexdigest(),
             "source_revision": manifest["source_revision"], "candidate_readiness": manifest["readiness"],
             "model_enabled": model_enabled, "checks": {key: [] for key in CHECKS},
             "sessions": [], "second_round": None,
             "technical_receipts": {"local_model": [], "workstation": []}}
    if current:
        state["candidate_license"] = manifest["license"]
        state["development_policy"] = manifest["development_policy"]
    with _locked(directory) as root:
        if (root / "acceptance.json").exists():
            raise ValueError("Um registro já existe neste diretório.")
        _save(root, state)
    return state


def _add(directory, record, attachment, validator, kind):
    with _locked(directory) as root:
        state = _load(root)
        validator(record, state)
        if kind == "session" and any(old["participant"] == record["participant"] for old in state["sessions"]):
            raise ValueError("O participante já possui uma sessão registrada.")
        if kind == "check" and len(state["checks"][record["check"]]) >= 20:
            raise ValueError("O histórico desta verificação atingiu seu limite.")
        if kind == "round" and state["second_round"] is not None:
            raise ValueError("A segunda rodada já possui um registro.")
        _attachment(root, record["evidence_sha256"], attachment)
        if kind == "session":
            state["sessions"].append(record)
        elif kind == "check":
            state["checks"][record["check"]].append(record)
        else:
            state["second_round"] = record
        _save(root, state)


def add_check(directory, record, attachment):
    _add(directory, record, attachment, _check, "check")


def add_session(directory, record, attachment):
    _add(directory, record, attachment, _session, "session")


def add_second_round(directory, record, attachment):
    _add(directory, record, attachment, _second_round, "round")


def summarize(directory=_DEFAULT):
    with _locked(directory) as root:
        state = _load(root)
    sessions = state["sessions"]
    checks = {key: ("not_required" if key == "local_model" and not state["model_enabled"] else
                    entries[-1]["result"] if entries else "pending")
              for key, entries in state["checks"].items()}
    exports = sum(row["platform"]["export_completed"] and row["platform"]["duration_seconds"] <= 600
                  and row["platform"]["help_count"] == 0 for row in sessions)
    interpretation = sum(all(row["interpretation"].values()) for row in sessions)
    peers = sum(row["peer_recalculation"] for row in sessions)
    completed_pairs = [row for row in sessions
                       if row["platform"]["export_completed"] and row["notebook"]["export_completed"]]
    deltas = [row["platform"]["duration_seconds"] - row["notebook"]["duration_seconds"]
              for row in completed_pairs]
    rounds = state["second_round"]
    second_round = rounds is not None and rounds["commercial_interest"] == "accepted_discussion"
    balanced = len(sessions) == 5 and sum(row["order"] == "notebook_first" for row in sessions) == 3 \
        and all({row[method]["seed_list"] for row in sessions} == {"A", "B"}
                for method in ("notebook", "platform"))
    criteria = {"five_participants_two_labs": len(sessions) == 5 and len({row["lab"] for row in sessions}) == 2,
                "balanced_task_order": balanced, "four_exports_without_help_within_600s": exports >= 4,
                "four_correct_interpretations": interpretation >= 4,
                "five_peer_recalculations": peers == 5, "second_round_recorded": second_round}
    technical = {key: "technical_receipt_recorded" if entries else "pending"
                 for key, entries in state["technical_receipts"].items()}
    if state["model_enabled"] and state["technical_receipts"]["local_model"]:
        checks["local_model"] = "technical_receipt_recorded"
    current = state["schema"] == SCHEMA
    if current:
        # This confirms the package license bytes checked at initialization.
        # It is not a human identity or a commercial/pilot validation.
        checks["license"] = "verified_from_candidate"
    pending = [key for key, result in checks.items()
               if result not in ("not_required", "passed", "technical_receipt_recorded", "verified_from_candidate")]
    return {"schema": "rqb-pilot-summary/1", "candidate_sha256": state["candidate_sha256"],
            "source_revision": state["source_revision"], "candidate_readiness": state["candidate_readiness"],
            "decision": "pending_human_acceptance" if current else "blocked_by_candidate_policy",
            "license": state["candidate_license"] if current else None,
            "buyer_validation": state["development_policy"]["buyer_validation"] if current else "not_recorded",
            "paid_execution": state["development_policy"]["paid_execution"] if current else None,
            "human_attestations_independently_verified": False,
            "checks": checks, "pending_checks": pending, "criteria": criteria,
            "technical_receipts": technical, "technical_receipts_authenticated": False,
            "manual_attestations_complete": all(value == "passed" for key, value in checks.items()
                                                 if key not in (("local_model", "license") if current else ("local_model",))),
            "sessions_recorded": len(sessions), "exports_without_help_within_600s": exports,
            "completed_pairs_count": len(completed_pairs),
            "correct_interpretations": interpretation, "peer_recalculations": peers,
            "median_platform_minus_notebook_seconds": median(deltas) if deltas else None,
            "scope": "registro_de_evidencias_do_piloto_sem_aprovacao_automatica"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Registrar evidências privadas do piloto")
    parser.add_argument("--directory", type=Path, default=_DEFAULT)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--candidate", type=Path, required=True)
    init.add_argument("--sha256", required=True, help="digest esperado do registro da candidata")
    init.add_argument("--with-local-model", action="store_true")
    for name in ("check", "add-session", "second-round"):
        command = commands.add_parser(name)
        command.add_argument("--record", type=Path, required=True)
        command.add_argument("--attachment", type=Path, required=True)
    technical = commands.add_parser("import-technical")
    technical.add_argument("--receipt", "--evidence-path", dest="receipt", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.candidate, args.directory, expected_sha256=args.sha256, model_enabled=args.with_local_model)
        elif args.command == "import-technical":
            import_technical(args.directory, args.receipt)
        elif args.command != "status":
            action = {"check": add_check, "add-session": add_session, "second-round": add_second_round}[args.command]
            action(args.directory, _decode(args.record.read_bytes()), args.attachment)
        result = summarize(args.directory)
        if args.command == "status" and args.output:
            if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
                raise ValueError("Exporte o resumo para fora do repositório e revise antes de publicar.")
            with args.output.open("xb") as stream:
                stream.write(_encoded(result))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except OSError:
        print("Registro recusado. Não foi possível ler ou guardar os arquivos privados.")
        return 1
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Registro recusado: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
