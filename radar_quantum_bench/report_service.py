"""Relatórios locais persistem somente seleções validadas, ligadas ao resultado."""

import json
import os
from pathlib import Path
import re
import tempfile
from threading import Lock

from .experiment import _unique_fields
from .ollama import AdvisorError
from .report import build_report, model_input


class ReportBusy(Exception):
    """Uma solicitação explícita já está usando o relator desta instalação."""


_REASONS = {
    "registro_invalido", "modelo_desativado", "modelo_remoto_bloqueado",
    "resposta_invalida", "modelo_indisponivel", "tempo_esgotado", "proposta_invalida",
}


def _identity(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"name", "digest", "server_version"}:
        raise ValueError("Identificação do modelo inválida.")
    patterns = {"name": r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}",
                "digest": r"[0-9a-f]{64}", "server_version": r"[A-Za-z0-9._+:-]{1,80}"}
    if any(not isinstance(value[key], str) or not re.fullmatch(pattern, value[key])
           for key, pattern in patterns.items()):
        raise ValueError("Identificação do modelo inválida.")
    return dict(value)


class Reports:
    def __init__(self, root: Path, advisor=None):
        self.root = Path(root) / "reports"
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.advisor = advisor
        self._lock = Lock()

    @staticmethod
    def _base(document, job_id, digest, **kwargs):
        report = build_report(document, job_id=job_id, result_sha256=digest, **kwargs)
        report["modelo_versao"] = None
        return report

    def read(self, document, job_id, digest):
        base = self._base(document, job_id, digest)
        path = self.root / f"{base['job_id']}.json"
        if not path.exists():
            return base
        try:
            with path.open("rb") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError("Registro grande demais.")
            record = json.loads(raw, object_pairs_hook=_unique_fields)
            if set(record) != {"job_id", "run_id", "result_sha256", "schema_version",
                               "prompt_revision", "proposal", "identity", "fallback_reason"}:
                raise ValueError("Registro desconhecido.")
            for key in ("job_id", "run_id", "result_sha256", "schema_version", "prompt_revision"):
                if record[key] != base[key]:
                    raise ValueError("O registro pertence a outro resultado ou revisão.")
            identity = _identity(record["identity"])
            reason = record["fallback_reason"]
            if reason is not None and reason not in _REASONS:
                raise ValueError("Motivo desconhecido.")
            if record["proposal"] is not None and (identity is None or reason is not None):
                raise ValueError("Seleção sem identificação válida.")
            report = self._base(
                document, job_id, digest, proposal=record["proposal"],
                model_id=identity["name"] if identity else None, fallback_reason=reason,
            )
            if record["proposal"] is not None and report["origem_texto"] != "modelo_local":
                raise ValueError("A seleção guardada não corresponde às evidências.")
            report["modelo_versao"] = identity
            return report
        except (ValueError, OSError, KeyError, TypeError):
            return self._base(document, job_id, digest, fallback_reason="registro_invalido")

    def _save(self, report):
        record = {key: report[key] for key in (
            "job_id", "run_id", "result_sha256", "schema_version", "prompt_revision",
        )}
        record.update(
            proposal=model_input(report)["proposta_base"]
            if report["origem_texto"] == "modelo_local" else None,
            identity=report["modelo_versao"], fallback_reason=report["fallback_reason"],
        )
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                             prefix=".report-", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(record, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.root / f"{report['job_id']}.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def generate(self, document, job_id, digest):
        if not self._lock.acquire(blocking=False):
            raise ReportBusy
        try:
            if self.advisor is None:
                report = self._base(document, job_id, digest, fallback_reason="modelo_desativado")
            else:
                cached = self.read(document, job_id, digest)
                if cached["origem_texto"] == "modelo_local" and cached["modelo"] == self.advisor.model:
                    return cached
                base = self._base(document, job_id, digest)
                try:
                    proposal = self.advisor.propose(model_input(base))
                    identity = _identity(self.advisor.identity)
                    if identity is None or identity["name"] != self.advisor.model:
                        raise ValueError("O modelo não foi identificado.")
                    report = self._base(document, job_id, digest, proposal=proposal,
                                        model_id=identity["name"])
                    report["modelo_versao"] = identity
                except AdvisorError as exc:
                    reason = exc.code if exc.code in _REASONS else "resposta_invalida"
                    report = self._base(document, job_id, digest, fallback_reason=reason)
                except (ValueError, TypeError):
                    report = self._base(document, job_id, digest, fallback_reason="resposta_invalida")
            self._save(report)
            return report
        finally:
            self._lock.release()
