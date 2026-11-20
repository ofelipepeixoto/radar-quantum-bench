"""Interface de linha de comando do primeiro marco."""
import argparse
import json
import sys
from pathlib import Path

from .experiment import load_result, run


def show(doc):
    summary = doc["summary"]
    print(f"Bell em CPU | {doc['run_id']} | {summary['total_shots']} medições avaliadas")
    for name, item in summary["conditions"].items():
        print(f"{name}: {json.dumps(item['counts'])}")
        if item["valid_fraction"] is not None:
            lo, hi = item["wilson95"]
            print(f"  Bits iguais {item['valid_fraction']:.4%}, IC 95% [{lo:.4%}, {hi:.4%}], "
                  f"TVD {item['tvd']:.6f}, mediana {item['median_ms']:.3f} ms")
    print("Referência teórica: bits iguais 100% (ideal) e 96,08% (com ruído). "
          "TVD teórica: 0 e 0,0392.")
    print("Estado:", "completo" if summary["complete"] else "incompleto")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Radar Quantum Bench · Bell com Qiskit Aer")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("run", help="medir em CPU")
    collect.add_argument("--output", required=True, type=Path)
    collect.add_argument("--seed", type=int, help="semente base de 32 bits (padrão 20261120)")
    collect.add_argument("--resume", action="store_true", help="retomar o mesmo arquivo")
    commands.add_parser("verify", help="recalcular as métricas sem Aer").add_argument("result", type=Path)
    pack = commands.add_parser("pack", help="montar o pacote de reprodução")
    pack.add_argument("result", type=Path)
    pack.add_argument("destination", type=Path)
    commands.add_parser("check-package", help="verificar o ZIP sem extração").add_argument(
        "archive", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            show(run(args.output, args.seed, args.resume))
        elif args.command == "verify":
            doc = load_result(args.result)
            show(doc)
            if not doc["summary"]["complete"]:
                return 2
        elif args.command == "pack":
            from .bundle import build_bundle
            build_bundle(args.result, args.destination)
            print(args.destination)
        else:
            from .bundle import check_bundle
            check_bundle(args.archive)
            print("Pacote conferido:", args.archive)
    except (ValueError, OSError, KeyError, TypeError, ImportError, RuntimeError) as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
