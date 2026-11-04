"""Single-host durable job runner. Run as a separate process from the API."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from .db import connect, initialize
from .geometry import create_bundle
from .settings import Settings

logger = logging.getLogger(__name__)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def process_next(settings: Settings) -> bool:
    with connect(settings.data_dir) as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            db.execute("COMMIT")
            return False
        db.execute("UPDATE jobs SET state='running',updated_at=? WHERE id=?",(utc(),row["id"]))
        db.execute("COMMIT")
        project=db.execute("SELECT * FROM projects WHERE id=?",(row["project_id"],)).fetchone()
    try:
        if not project:
            raise ValueError("Project disappeared")
        path=settings.data_dir/"exports"/(row["version_id"]+".zip")
        result=create_bundle(Path(project["source_path"]),path,
                             row["project_id"],row["version_id"],json.loads(row["params_json"]))
        with connect(settings.data_dir) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO versions(id,project_id,job_id,zip_path,manifest_json,created_at) VALUES(?,?,?,?,?,?)",
                (row["version_id"],row["project_id"],row["id"],str(path),
                 json.dumps(result["manifest"]),utc()))
            db.execute("UPDATE jobs SET state='completed',updated_at=? WHERE id=?",(utc(),row["id"]))
            db.execute("COMMIT")
        logger.info("Job completed: %s",row["id"])
    except Exception:
        logger.exception("Generation failed: %s",row["id"])
        with connect(settings.data_dir) as db:
            db.execute("UPDATE jobs SET state='failed',error=?,updated_at=? WHERE id=?",
                       ("Generation failed; contact the operator",utc(),row["id"]))
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings=Settings.load()
    initialize(settings.data_dir)
    # Jobs interrupted by a worker restart are retried.
    with connect(settings.data_dir) as db:
        db.execute("UPDATE jobs SET state='queued' WHERE state='running'")
    logger.info("MINIMO CPU worker started")
    while True:
        if not process_next(settings):
            time.sleep(1.5)


if __name__ == "__main__":
    main()
