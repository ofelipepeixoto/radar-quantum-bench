"""API da instalação local, com fila durável e execução em processo separado."""

from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .bundle import build_bundle
from .experiment import load_result
from .metrics import specifications
from .store import Conflict, InvalidState, NotFound, QueueFull, Store

_DEFAULT_SEEDS = {"bell": 20261120, "ghz": 20261220, "bv": 20261320}
_CONTENT_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    circuit: Literal["bell", "ghz", "bv"]
    base_seed: Annotated[StrictInt, Field(ge=0, le=4294967295)] | None = None


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^\S+$")]


def create_app(data_dir: Path, capacity: int = 32, ui_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Radar Quantum Bench · API local", version="0.3.0",
                  docs_url=None, redoc_url=None)
    store = Store(Path(data_dir), capacity=capacity)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def local_response(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            response = JSONResponse(status_code=403, content={"detail": "Origem não autorizada."})
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CONTENT_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    for error, code, detail in (
        (NotFound, 404, "Comparação não encontrada."),
        (Conflict, 409, "A chave já identifica uma configuração diferente."),
        (InvalidState, 409, "Operação incompatível com o estado da comparação."),
        (QueueFull, 429, "A fila atingiu sua capacidade. Tente novamente depois."),
    ):
        async def handler(request, exception, status=code, message=detail):
            return JSONResponse(status_code=status, content={"detail": message})
        app.add_exception_handler(error, handler)

    def result_document(job_id):
        path = store.result_path(job_id)
        if not path.exists():
            raise HTTPException(409, "As medições ainda estão pendentes.")
        try:
            job = store.get(job_id)
            document = load_result(path)
            config = document["config"]
            if (config["circuit"], config["base_seed"]) != (job["circuit"], job["base_seed"]):
                raise ValueError("O resultado pertence a outra configuração.")
            digest = job["result_sha256"]
            if digest is not None and sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("O resultado difere do arquivo concluído pelo executor.")
            return document
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise HTTPException(409, "O resultado requer revisão antes da exportação.") from exc

    @app.get("/health")
    def health():
        return {"status": "ok", "execution": "local-cpu"}

    @app.get("/api/v1/experimentos")
    def experiments():
        return [
            {"id": circuit, "label": specifications(circuit)["label"], "revision": 1,
             "shots": 1024, "repetitions": 10,
             "base_seed": _DEFAULT_SEEDS[circuit], **specifications(circuit)}
            for circuit in _DEFAULT_SEEDS
        ]

    @app.post("/api/v1/comparacoes", status_code=202)
    def submit(body: ComparisonRequest, idempotency_key: IdempotencyKey):
        seed = _DEFAULT_SEEDS[body.circuit] if body.base_seed is None else body.base_seed
        return store.submit(idempotency_key, body.circuit, seed)

    @app.get("/api/v1/comparacoes")
    def history(limit: Annotated[int, Field(ge=1, le=100)] = 20,
                offset: Annotated[int, Field(ge=0, le=2147483647)] = 0):
        return store.list_jobs(limit=limit, offset=offset)

    @app.get("/api/v1/comparacoes/{job_id}")
    def comparison(job_id: UUID):
        job = store.get(str(job_id))
        path = store.result_path(str(job_id))
        job["progress"] = result_document(str(job_id))["summary"] if path.exists() else None
        return job

    @app.get("/api/v1/comparacoes/{job_id}/metricas")
    def metrics(job_id: UUID):
        store.get(str(job_id))
        return result_document(str(job_id))["summary"]

    @app.post("/api/v1/comparacoes/{job_id}/retentativas", status_code=202)
    def retry(job_id: UUID, idempotency_key: IdempotencyKey):
        return store.retry(str(job_id), idempotency_key)

    @app.get("/api/v1/comparacoes/{job_id}/exportacao")
    def export(job_id: UUID):
        job = store.get(str(job_id))
        document = result_document(str(job_id))
        if job["status"] != "completed" or not document["summary"]["complete"]:
            raise HTTPException(409, "A comparação precisa estar concluída para exportar.")
        export_root = Path(data_dir).resolve() / "exports"
        export_root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="download-", dir=export_root))
        archive = folder / "reproducao.zip"
        try:
            build_bundle(store.result_path(str(job_id)), archive)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            shutil.rmtree(folder)
            raise HTTPException(409, "As fontes e os resultados precisam ser revisados juntos.") from exc
        return FileResponse(
            archive, media_type="application/zip",
            filename=f"Radar-Quantum-Bench-{job['circuit'].upper()}.zip",
            background=BackgroundTask(shutil.rmtree, folder),
        )

    frontend = ui_dir if ui_dir is not None else Path(__file__).resolve().parents[1] / "web" / "dist"
    if (frontend / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="interface")
    else:
        @app.get("/", include_in_schema=False)
        def frontend_unavailable():
            raise HTTPException(
                503, "Para abrir a interface, execute npm ci e npm run build na pasta web "
                "e reinicie o serviço local. A API está disponível em /api/v1/experimentos.",
            )

    return app
