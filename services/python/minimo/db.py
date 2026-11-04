"""SQLite persistence for a **single-host** API + one durable worker.

Never place this database in an ephemeral Vercel function. For distributed
workers/servers replace this module with a PostgreSQL transactional queue.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

CREATE = """
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, source_path TEXT NOT NULL,
 created_at TEXT NOT NULL, approved_version TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 state TEXT NOT NULL CHECK(state IN ('queued','running','completed','failed')),
 params_json TEXT NOT NULL, version_id TEXT NOT NULL, error TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 job_id TEXT NOT NULL, zip_path TEXT NOT NULL, manifest_json TEXT NOT NULL,
 created_at TEXT NOT NULL, production_state TEXT NOT NULL DEFAULT 'unreviewed'
);
CREATE INDEX IF NOT EXISTS jobs_project_idx ON jobs(project_id, created_at);
CREATE INDEX IF NOT EXISTS versions_project_idx ON versions(project_id, created_at);
"""


def initialize(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "images").mkdir(exist_ok=True)
    (data_dir / "exports").mkdir(exist_ok=True)
    with connect(data_dir) as db:
        db.executescript(CREATE)


@contextmanager
def connect(data_dir: Path):
    db = sqlite3.connect(str(data_dir / "minimo.sqlite3"), timeout=20, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    try:
        yield db
    finally:
        db.close()
