"""Ensaiar uma cópia da candidata com API, fila, exportação e restauração reais.

Use o Python do ambiente limpo já instalado. O script não instala pacotes, não
consulta modelos e grava somente uma evidência reduzida no destino informado.
"""

import argparse
from contextlib import contextmanager
from hashlib import sha256
import http.client
from importlib.metadata import distribution, version
from io import BytesIO
import json
from math import isfinite
import os
from pathlib import Path
import platform
import re
import shutil
import site
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from uuid import uuid4
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
CIRCUITS = ("bell", "ghz", "bv")


class ProbeFailure(Exception):
    """Código de falha fixo, sem reproduzir dados ou mensagens recebidas."""


def require(condition, code):
    if not condition:
        raise ProbeFailure(code)


def run(arguments, *, timeout=90):
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, timeout=timeout,
                            env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    require(result.returncode == 0, "subprocesso_reprovado")
    return result


def exchange(port, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = None if body is None else json.dumps(body).encode("utf-8")
    try:
        connection.request(method, path, body=data,
                           headers={"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        content = response.read(2 * 1024 * 1024 + 1)
        require(len(content) <= 2 * 1024 * 1024, "resposta_excessiva")
        return response.status, {key.lower(): value for key, value in response.getheaders()}, content
    finally:
        connection.close()


def get_json(port, path):
    status, _, content = exchange(port, "GET", path)
    require(status == 200, "leitura_http_reprovada")
    return json.loads(content)


@contextmanager
def services(data, *, worker):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    commands = [[sys.executable, "-m", "radar_quantum_bench.local", "serve",
                 "--data-dir", str(data), "--port", str(port)]]
    if worker:
        commands.append([sys.executable, "-m", "radar_quantum_bench.local", "worker",
                         "--data-dir", str(data)])
    processes = []
    try:
        for command in commands:
            processes.append(subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL))
        deadline = monotonic() + 20
        while True:
            require(all(process.poll() is None for process in processes), "servico_encerrou")
            try:
                if get_json(port, "/health")["status"] == "ok":
                    break
            except (OSError, ProbeFailure):
                require(monotonic() < deadline, "servico_indisponivel")
                sleep(0.05)
        yield port
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def inspect(port, identifier):
    route = f"/api/v1/comparacoes/{identifier}"
    job = get_json(port, route)
    metrics = get_json(port, route + "/metricas")
    report = get_json(port, route + "/relatorio")
    require(job["status"] == "completed" and metrics["complete"] is True, "trabalho_incompleto")
    require(metrics["total_shots"] == 20480, "shots_incorretos")
    require(report["estado"] == "completo" and report["origem_texto"] == "deterministico",
            "relato_incompativel")
    require(report["job_id"] == identifier and report["result_sha256"] == job["result_sha256"],
            "vinculo_relatorio_incorreto")
    for extension in ("json", "md"):
        status, headers, content = exchange(port, "GET", route + "/relatorio." + extension)
        require(status == 200 and "attachment;" in headers.get("content-disposition", ""),
                "download_relatorio_reprovado")
        if extension == "json":
            require(json.loads(content) == report, "json_relatorio_divergente")
        else:
            text = content.decode("utf-8")
            require(report["result_sha256"] in text and report["resumo"]["texto"] in text,
                    "markdown_relatorio_divergente")
    status, _, archive = exchange(port, "GET", route + "/exportacao")
    require(status == 200, "download_cientifico_reprovado")
    with ZipFile(BytesIO(archive)) as package:
        raw = package.read("result.json")
        document = json.loads(raw)
    require(sha256(raw).hexdigest() == job["result_sha256"], "digest_pacote_divergente")
    require(document["run_id"] == report["run_id"] and document["summary"] == metrics,
            "dados_pacote_divergentes")
    return {"job": job, "metrics": metrics, "report": report,
            "package_sha256": sha256(archive).hexdigest(), "package": archive}


def _public_snapshot(snapshot):
    return {"circuit": snapshot["job"]["circuit"], "completed": True,
            "shots": snapshot["metrics"]["total_shots"],
            "counts": {name: row["counts"] for name, row in snapshot["metrics"]["conditions"].items()},
            "report_and_downloads_agree": True, "scientific_package_checked": True}


def provenance():
    path = ROOT / "RELEASE-MANIFEST.json"
    if not path.is_file():
        return {"origin": "source_directory", "source_revision": None,
                "manifest_sha256": None, "content_matches_manifest": False}
    raw = path.read_bytes()
    manifest = json.loads(raw)
    require(manifest["schema"] == "rqb-review-candidate/1", "manifesto_incompativel")
    require(re.fullmatch(r"[0-9a-f]{40}", manifest["source_revision"]) is not None,
            "revisao_manifesto_invalida")
    require(isinstance(manifest["files"], dict) and 0 < len(manifest["files"]) <= 4096,
            "arquivos_manifesto_invalidos")
    for name, row in manifest["files"].items():
        file = ROOT / name
        require(file.resolve().is_relative_to(ROOT) and not file.is_symlink(),
                "caminho_manifesto_invalido")
        content = file.read_bytes()
        require(len(content) == row["bytes"] and sha256(content).hexdigest() == row["sha256"],
                "conteudo_manifesto_divergente")
    return {"origin": "extracted_review_candidate", "source_revision": manifest["source_revision"],
            "manifest_sha256": sha256(raw).hexdigest(), "content_matches_manifest": True,
            "readiness": manifest["readiness"]}


def receipt_summary(paths):
    receipts = [json.loads(path.read_bytes()) for path in paths]
    for receipt in receipts:
        require(receipt["schema_version"] == "rqb-execution/1" and receipt["status"] == "completed"
                and receipt["exit_code"] == 0 and receipt["error_code"] is None,
                "recibo_execucao_incompativel")
        for value in (receipt["elapsed_ms"], receipt["limits"]["wall_seconds"],
                      receipt["limits"]["virtual_memory_mib"]):
            require(type(value) in (int, float) and isfinite(value) and value > 0,
                    "unidade_recibo_invalida")
        peak = receipt["peak_rss_kib"]
        require(peak is None or type(peak) is int and peak > 0, "pico_memoria_invalido")
    peaks = [receipt["peak_rss_kib"] for receipt in receipts if receipt["peak_rss_kib"] is not None]
    return {"count": len(receipts), "all_completed": True,
            "max_elapsed_ms": max(receipt["elapsed_ms"] for receipt in receipts),
            "max_peak_rss_kib": max(peaks) if peaks else None,
            "configured_limits": [receipt["limits"] for receipt in receipts]}


def offline_probe():
    # This guard blocks Python socket entry points. It is intentionally not
    # described as an OS network namespace or a firewall for native libraries.
    class NetworkBlocked(Exception):
        pass

    def blocked(*_args, **_kwargs):
        raise NetworkBlocked

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked
    canary = False
    with socket.socket() as test_socket:
        try:
            test_socket.connect(("127.0.0.1", 9))
        except NetworkBlocked:
            canary = True
    require(canary, "bloqueio_socket_nao_confirmado")
    sys.path.insert(0, str(ROOT))
    from radar_quantum_bench.bundle import build_bundle, check_bundle
    from radar_quantum_bench.experiment import load_result, run as experiment

    with TemporaryDirectory(prefix="rqb-offline-") as folder:
        root = Path(folder)
        observed, total_shots = {}, 0
        for circuit in CIRCUITS:
            result = root / f"{circuit}.json"
            experiment(result, circuit=circuit)
            document = load_result(result)
            require(document["summary"]["complete"], "offline_incompleto")
            total_shots += document["summary"]["total_shots"]
            observed[circuit] = {name: row["counts"]
                                 for name, row in document["summary"]["conditions"].items()}
            archive = root / f"{circuit}.zip"
            build_bundle(result, archive)
            check_bundle(archive)
        tampered = json.loads(result.read_bytes())
        tampered["summary"]["conditions"]["ideal"]["counts"]["000"] += 1
        result.write_text(json.dumps(tampered), encoding="utf-8")
        try:
            load_result(result)
        except ValueError:
            rejected = True
        else:
            rejected = False
        require(rejected, "medicao_adulterada_aceita")
    return {"status": "passed", "guard": "python_socket_entrypoints_only",
            "os_network_isolation": False, "canary_blocked": True,
            "circuits": list(CIRCUITS), "counts": observed, "evaluated_shots": total_shots,
            "tampered_measurement_rejected": True}


def probe():
    require((ROOT / "web/dist/index.html").is_file(), "build_interface_ausente")
    source = provenance()
    with TemporaryDirectory(prefix="rqb-candidate-") as temporary:
        root = Path(temporary)
        original = root / "original"
        with services(original, worker=True) as port:
            require(exchange(port, "GET", "/")[0] == 200, "interface_http_reprovada")
            identifiers = []
            for circuit in CIRCUITS:
                status, _, content = exchange(port, "POST", "/api/v1/comparacoes",
                                               {"circuit": circuit},
                                               {"Idempotency-Key": str(uuid4())})
                require(status == 202, "envio_reprovado")
                identifiers.append(json.loads(content)["id"])
            deadline = monotonic() + 180
            while True:
                jobs = [get_json(port, f"/api/v1/comparacoes/{identifier}") for identifier in identifiers]
                require(all(job["status"] != "failed" for job in jobs), "experimento_falhou")
                if all(job["status"] == "completed" for job in jobs):
                    break
                require(monotonic() < deadline, "execucao_excedeu_prazo")
                sleep(0.05)
            status, _, fallback = exchange(port, "POST", f"/api/v1/comparacoes/{identifiers[0]}/relatorio")
            require(status == 200 and json.loads(fallback)["fallback_reason"] == "modelo_desativado",
                    "resumo_local_desativado_divergente")
            snapshots = [inspect(port, identifier) for identifier in identifiers]
            for index, snapshot in enumerate(snapshots):
                archive = root / f"package-{index}.zip"
                archive.write_bytes(snapshot["package"])
                run([sys.executable, "-m", "radar_quantum_bench", "check-package", str(archive)])
        restored = root / "restored"
        shutil.copytree(original, restored)
        require(all((restored / "results" / f"{identifier}.json").is_file()
                    for identifier in identifiers), "copia_incompleta")
        receipts = sorted((original / "executions").rglob("*.json"))
        require(len(receipts) == 3, "recibos_execucao_ausentes")
        resource_evidence = receipt_summary(receipts)
        for receipt in receipts:
            require(receipt.read_bytes() == (restored / receipt.relative_to(original)).read_bytes(),
                    "recibo_restaurado_divergente")
        shutil.rmtree(original)
        with services(restored, worker=False) as port:
            for identifier, previous in zip(identifiers, snapshots):
                require(inspect(port, identifier) == previous, "restauracao_divergente")
            path = restored / "results" / f"{identifiers[0]}.json"
            changed = json.loads(path.read_bytes())
            changed["environment"]["hardware"]["cpu"] = "marcador-ficticio-de-adulteracao"
            path.write_text(json.dumps(changed), encoding="utf-8")
            require(exchange(port, "GET", f"/api/v1/comparacoes/{identifiers[0]}/relatorio")[0] == 409,
                    "resultado_adulterado_nao_recusado")
        offline_result = root / "offline.json"
        run([sys.executable, str(Path(__file__).resolve()), "--offline-probe", "--output", str(offline_result)])
        offline = json.loads(offline_result.read_bytes())
        for snapshot in snapshots:
            circuit = snapshot["job"]["circuit"]
            counts = {name: row["counts"] for name, row in snapshot["metrics"]["conditions"].items()}
            require(offline["counts"][circuit] == counts, "repeticao_offline_divergente")
        return {"schema": "radar-quantum-bench/candidate-verification-v1", "status": "passed",
                "source": source,
                "environment": {"python": platform.python_version(), "system": platform.system(),
                                "architecture": platform.machine(),
                                "virtualenv_active": sys.prefix != sys.base_prefix,
                                "user_site_enabled": site.ENABLE_USER_SITE,
                                "distributions_within_virtualenv": all(
                                    Path(distribution(name).locate_file("")).resolve().is_relative_to(
                                        Path(sys.prefix).resolve())
                                    for name in ("qiskit", "qiskit-aer", "fastapi", "uvicorn")),
                                "packages": {name: version(name) for name in
                                             ("qiskit", "qiskit-aer", "numpy", "scipy", "fastapi", "uvicorn")}},
                "http_and_worker": {"status": "passed", "circuits": [_public_snapshot(s) for s in snapshots]},
                "restoration": {"status": "passed", "jobs_reopened": 3,
                                "source_copy_removed_before_reopen": True,
                                "identical_jobs_counts_reports_and_packages": True,
                                "execution_receipts_restored": len(receipts),
                                "local_fallback_record_restored": True,
                                "modified_result_rejected": True},
                "execution_resources": resource_evidence,
                "offline": {**offline, "counts_identical_to_http_run": True}, "real_llm_used": False,
                "windows_pc_or_screen_reader_tested": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Conferir a candidata local em ambiente limpo já instalado")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline-probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("O destino já existe. Escolha um arquivo novo para preservar a evidência anterior.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        document = offline_probe() if args.offline_probe else probe()
    except (ProbeFailure, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        code = str(exc) if isinstance(exc, ProbeFailure) else type(exc).__name__
        document = {"schema": "radar-quantum-bench/candidate-verification-v1",
                    "status": "failed", "failure_code": code}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print("Verificação concluída." if document["status"] == "passed" else "Verificação reprovada.")
    return 0 if document["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
