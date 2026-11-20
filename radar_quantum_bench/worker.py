"""Execute local benchmark jobs, with one active worker per queue directory."""

import fcntl
from hashlib import sha256
from math import isfinite
from time import sleep

from . import experiment
from .store import Store


def run_worker(store: Store, once: bool = False, poll_seconds: float = 1.0) -> int:
    """Recover interrupted jobs and consume the queue; once limits work to one job."""
    if not isfinite(poll_seconds) or poll_seconds < 0:
        raise ValueError("O intervalo de consulta precisa ser finito e não negativo.")

    # Keep this inode in place: removing the file would allow competing locks.
    with (store.root / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Já existe um processo executando esta fila.") from exc

        store.recover()
        while True:
            job = store.claim()
            if job is None:
                if once:
                    return 0
                sleep(poll_seconds)
                continue

            error_code = None
            result_digest = None
            try:
                path = store.result_path(job["id"])
                experiment.run(
                    path, base_seed=job["base_seed"], resume=path.exists(),
                    circuit=job["circuit"],
                )
                result_digest = sha256(path.read_bytes()).hexdigest()
            except Exception as exc:
                error_code = type(exc).__name__
            # Process interruptions and failures to commit the outcome leave a
            # running claim for the next worker to recover under this same lock.
            store.finish(job["id"], job["attempt_id"], error_code is None, error_code,
                         result_sha256=result_digest)
            if once:
                return int(error_code is not None)
