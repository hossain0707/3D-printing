"""Transactional SQLite store for a single API host and a single reconstruction worker.

For distributed production use, migrate the queue/metadata to PostgreSQL and
object storage; do not run SQLite against an ephemeral serverless filesystem.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  consent_at TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'received'
);
CREATE TABLE IF NOT EXISTS photos(
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  UNIQUE(project_id, sha256)
);
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('queued','running','completed','failed')),
  stage TEXT NOT NULL,
  target_height_mm INTEGER NOT NULL,
  quality TEXT NOT NULL,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions(
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  preview_path TEXT NOT NULL,
  package_path TEXT NOT NULL,
  report_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  customer_approved INTEGER NOT NULL DEFAULT 0,
  operator_status TEXT NOT NULL DEFAULT 'review_required'
);
CREATE INDEX IF NOT EXISTS photos_project_idx ON photos(project_id);
CREATE INDEX IF NOT EXISTS jobs_project_idx ON jobs(project_id, created_at);
CREATE INDEX IF NOT EXISTS versions_project_idx ON versions(project_id, created_at);
"""


def initialize(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "projects").mkdir(exist_ok=True)
    with connect(data_dir) as db:
        db.executescript(SCHEMA)


@contextmanager
def connect(data_dir: Path):
    con = sqlite3.connect(str(data_dir / "replica.sqlite3"), timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
    finally:
        con.close()
