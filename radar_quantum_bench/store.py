"""Fila SQLite local. Cada operação vê uma única transação, inclusive entre processos."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .metrics import specifications


class Conflict(Exception):
    """A chave de envio já foi usada com outros parâmetros."""


class QueueFull(Exception):
    """O número de trabalhos ativos atingiu a capacidade configurada."""


class NotFound(Exception):
    """O identificador não corresponde a um trabalho."""


class InvalidState(Exception):
    """A transição solicitada não é válida para a tentativa atual."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validate_id(jobid):
    try:
        parsed = UUID(jobid)
    except (ValueError, AttributeError, TypeError):
        raise NotFound("Identificador de trabalho inválido.") from None
    if parsed.version != 4 or str(parsed) != jobid:
        raise NotFound("Identificador de trabalho inválido.")


_PUBLIC_FIELDS = "id, circuit, base_seed, status, created_at, updated_at, result_sha256"
_ATTEMPT_FIELDS = "id, status, error_code, started_at, finished_at"


class Store:
    def __init__(self, root: Path, capacity=32):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("A capacidade da fila deve ser um inteiro positivo.")
        self.capacity = capacity
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.root / "results").mkdir(mode=0o700, exist_ok=True)
        self._db = self.root / "jobs.sqlite3"
        with self._transaction(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, submission_key TEXT NOT NULL UNIQUE,
                circuit TEXT NOT NULL, base_seed INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            if "result_sha256" not in {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}:
                db.execute("ALTER TABLE jobs ADD COLUMN result_sha256 TEXT")
            db.execute("""CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
                error_code TEXT, started_at TEXT NOT NULL, finished_at TEXT)""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_running_attempt
                          ON attempts(job_id) WHERE status = 'running'""")
            db.execute("CREATE INDEX IF NOT EXISTS attempts_job ON attempts(job_id)")
            db.execute("CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status,updated_at)")
            db.execute("""CREATE TABLE IF NOT EXISTS retries (
                job_id TEXT NOT NULL REFERENCES jobs(id), retry_key TEXT NOT NULL,
                PRIMARY KEY(job_id, retry_key))""")

    @contextmanager
    def _transaction(self, *, write=False):
        db = sqlite3.connect(self._db, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        finally:
            # Closing an uncommitted connection rolls back the whole operation.
            db.close()

    def _job(self, db, jobid):
        row = db.execute(f"SELECT {_PUBLIC_FIELDS} FROM jobs WHERE id=?", (jobid,)).fetchone()
        if row is None:
            raise NotFound("Trabalho não encontrado.")
        job = dict(row)
        rows = db.execute(f"SELECT {_ATTEMPT_FIELDS} FROM attempts WHERE job_id=? ORDER BY rowid",
                          (jobid,))
        job["attempts"] = [dict(attempt) for attempt in rows]
        return job

    def _check_capacity(self, db):
        active = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
        if active >= self.capacity:
            raise QueueFull("A fila está cheia.")

    def submit(self, key, circuit, seed):
        if not isinstance(key, str) or not key.strip():
            raise ValueError("A chave de envio é obrigatória.")
        specifications(circuit)
        if type(seed) is not int or not 0 <= seed <= 0xffffffff:
            raise ValueError("A semente deve estar entre 0 e 4294967295.")
        with self._transaction(write=True) as db:
            existing = db.execute("SELECT id,circuit,base_seed FROM jobs WHERE submission_key=?",
                                  (key,)).fetchone()
            if existing is not None:
                if (existing["circuit"], existing["base_seed"]) != (circuit, seed):
                    raise Conflict("A chave de envio já identifica outros parâmetros.")
                return self._job(db, existing["id"])
            self._check_capacity(db)
            jobid, now = str(uuid4()), _now()
            db.execute("""INSERT INTO jobs (id,submission_key,circuit,base_seed,status,created_at,updated_at)
                          VALUES (?,?,?,?,'queued',?,?)""", (jobid, key, circuit, seed, now, now))
            return self._job(db, jobid)

    def get(self, jobid):
        _validate_id(jobid)
        with self._transaction() as db:
            return self._job(db, jobid)

    def list_jobs(self, limit=20, offset=0):
        if type(limit) is not int or type(offset) is not int or min(limit, offset) < 0:
            raise ValueError("Limite e posição devem ser inteiros não negativos.")
        with self._transaction() as db:
            rows = db.execute("SELECT id FROM jobs ORDER BY rowid DESC LIMIT ? OFFSET ?", (limit, offset))
            return [self._job(db, row["id"]) for row in rows]

    def retry(self, jobid, key):
        _validate_id(jobid)
        if not isinstance(key, str) or not key.strip():
            raise ValueError("A chave de retentativa é obrigatória.")
        with self._transaction(write=True) as db:
            job = self._job(db, jobid)
            if db.execute("SELECT 1 FROM retries WHERE job_id=? AND retry_key=?",
                          (jobid, key)).fetchone():
                return job
            if job["status"] != "failed":
                raise InvalidState("Somente um trabalho com falha pode voltar à fila.")
            self._check_capacity(db)
            db.execute("INSERT INTO retries (job_id,retry_key) VALUES (?,?)", (jobid, key))
            db.execute("UPDATE jobs SET status='queued', updated_at=? WHERE id=?", (_now(), jobid))
            return self._job(db, jobid)

    def claim(self):
        with self._transaction(write=True) as db:
            row = db.execute("""SELECT id FROM jobs WHERE status='queued'
                                ORDER BY updated_at,rowid LIMIT 1""").fetchone()
            if row is None:
                return None
            jobid, attempt_id, now = row["id"], str(uuid4()), _now()
            db.execute("UPDATE jobs SET status='running', updated_at=? WHERE id=?", (now, jobid))
            db.execute("""INSERT INTO attempts (id,job_id,status,started_at) VALUES (?,?,'running',?)""",
                       (attempt_id, jobid, now))
            return {**self._job(db, jobid), "attempt_id": attempt_id}

    def finish(self, jobid, attempt_id, success, error_code=None, result_sha256=None):
        _validate_id(jobid)
        if type(success) is not bool:
            raise ValueError("O resultado da tentativa deve indicar sucesso ou falha.")
        if result_sha256 is not None and (
            not isinstance(result_sha256, str) or len(result_sha256) != 64 or
            any(char not in "0123456789abcdef" for char in result_sha256)
        ):
            raise ValueError("O hash do resultado deve ser SHA-256 hexadecimal.")
        status = "completed" if success else "failed"
        now = _now()
        with self._transaction(write=True) as db:
            job = db.execute("SELECT status FROM jobs WHERE id=?", (jobid,)).fetchone()
            if job is None:
                raise NotFound("Trabalho não encontrado.")
            if job["status"] != "running":
                raise InvalidState("O trabalho não está em execução.")
            changed = db.execute("""UPDATE attempts SET status=?, finished_at=?, error_code=?
                                    WHERE id=? AND job_id=? AND status='running'""",
                                 (status, now, None if success else error_code, attempt_id, jobid))
            if changed.rowcount != 1:
                raise InvalidState("Esta tentativa já não está em execução.")
            db.execute("UPDATE jobs SET status=?, updated_at=?, result_sha256=? WHERE id=?",
                       (status, now, result_sha256 if success else None, jobid))

    def recover(self):
        """Chamar apenas após adquirir o bloqueio exclusivo do executor deste diretório."""
        with self._transaction(write=True) as db:
            now = _now()
            db.execute("""UPDATE attempts SET status='failed', error_code='Interrupted', finished_at=?
                          WHERE status='running'""", (now,))
            rows = db.execute("UPDATE jobs SET status='queued',updated_at=? WHERE status='running'", (now,))
            return rows.rowcount

    def result_path(self, jobid):
        _validate_id(jobid)
        return self.root / "results" / f"{jobid}.json"
