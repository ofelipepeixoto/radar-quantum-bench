"""Iniciar a API e o executor da instalação local."""

import argparse
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Radar Quantum Bench · serviço local")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="abrir API no endereço 127.0.0.1")
    serve.add_argument("--data-dir", type=Path, default=Path("local-data"))
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--report-model", help="modelo já instalado no Ollama local, uso explícito pela tela")
    worker = commands.add_parser("worker", help="executar a fila em CPU")
    worker.add_argument("--data-dir", type=Path, default=Path("local-data"))
    worker.add_argument("--once", action="store_true", help="processar no máximo um trabalho")
    worker.add_argument("--timeout-seconds", type=float, default=120,
                        help="prazo total por comparação em segundos, padrão 120")
    worker.add_argument("--memory-mib", type=int, default=2048,
                        help="teto de memória virtual do subprocesso em MiB, padrão 2048")
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            if not 1 <= args.port <= 65535:
                raise ValueError("A porta deve estar entre 1 e 65535.")
            import uvicorn
            from .api import create_app
            advisor = None
            if args.report_model:
                from .ollama import OllamaAdvisor
                advisor = OllamaAdvisor(args.report_model)
            uvicorn.run(create_app(args.data_dir, advisor=advisor), host="127.0.0.1", port=args.port)
            return 0
        from .store import Store
        from .worker import run_worker
        from .execution import WorkerLimits
        limits = WorkerLimits(timeout_seconds=args.timeout_seconds, memory_mib=args.memory_mib)
        return run_worker(Store(args.data_dir), once=args.once, limits=limits)
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print(f"Falha ao iniciar o serviço local: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
