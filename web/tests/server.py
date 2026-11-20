"""Start the real CLI and worker against one disposable queue for browser tests."""

import os
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from subprocess import Popen, TimeoutExpired
import sys
from tempfile import TemporaryDirectory
from threading import Event


def main():
    root = Path(__file__).resolve().parents[2]
    if not (root / "web/dist/index.html").is_file():
        sys.exit("Compile a interface com npm run build antes de rodar o Playwright.")

    python = os.environ.get("RQB_TEST_PYTHON", sys.executable)
    port = os.environ.get("RQB_E2E_PORT", "8765")
    stopping = Event()
    for signum in (SIGINT, SIGTERM):
        signal(signum, lambda *_: stopping.set())

    with TemporaryDirectory(prefix="rqb-browser-") as data_dir:
        processes = []
        try:
            for arguments in (["serve", "--port", port], ["worker"]):
                processes.append(Popen(
                    [python, "-m", "radar_quantum_bench.local", *arguments, "--data-dir", data_dir],
                    cwd=root,
                ))
            while not stopping.wait(0.2):
                for process in processes:
                    if process.poll() is not None:
                        raise RuntimeError(f"O processo de teste encerrou com código {process.returncode}.")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
