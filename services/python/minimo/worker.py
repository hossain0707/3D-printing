"""Durable single-host reconstruction queue and retention cleanup."""
import logging
import shutil
import time
import threading
from datetime import datetime, timezone
from .db import connect, initialize
from .photogrammetry import run_reconstruction
from .preflight import inspect
from .settings import Settings

logger=logging.getLogger(__name__)
def now(): return datetime.now(timezone.utc).isoformat()

def process_next(settings):
    with connect(settings.data_dir) as db:
        db.execute("BEGIN IMMEDIATE")
        job=db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not job:
            db.execute("COMMIT");return False
        db.execute("UPDATE jobs SET state='running',stage='starting',updated_at=? WHERE id=?",(now(),job["id"]))
        db.execute("COMMIT")
    def stage(name):
        logger.info("job=%s stage=%s",job["id"],name)
        with connect(settings.data_dir) as db:
            db.execute("UPDATE jobs SET stage=?,updated_at=? WHERE id=?",(name,now(),job["id"]))
    try:
        result=run_reconstruction(settings.data_dir/"projects"/job["project_id"],
            job["id"],job["version_id"],job["target_height_mm"],job["quality"],settings,stage)
        with connect(settings.data_dir) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO versions(id,project_id,job_id,preview_path,package_path,report_path,created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (job["version_id"],job["project_id"],job["id"],
                 result["preview_path"],result["package_path"],result["report_path"],now()))
            db.execute("UPDATE jobs SET state='completed',stage='ready_for_review',updated_at=? WHERE id=?",
                       (now(),job["id"]))
            db.execute("COMMIT")
    except Exception:
        logger.exception("Realistic reconstruction failed for %s",job["id"])
        with connect(settings.data_dir) as db:
            db.execute("UPDATE jobs SET state='failed',stage='failed',error=?,updated_at=? WHERE id=?",
                       ("Reconstruction failed. Check overlapping photos or processing hardware.",now(),job["id"]))
    return True

def purge_expired(settings):
    with connect(settings.data_dir) as db:
        db.execute("BEGIN IMMEDIATE")
        rows=db.execute("SELECT id FROM projects WHERE expires_at<? AND "
          "id NOT IN(SELECT project_id FROM jobs WHERE state IN ('queued','running'))",
          (now(),)).fetchall()
        ids=[r["id"] for r in rows]
        for pid in ids: db.execute("DELETE FROM projects WHERE id=?",(pid,))
        db.execute("COMMIT")
    for pid in ids:
        shutil.rmtree(settings.data_dir/"projects"/pid,ignore_errors=True)
    return len(ids)

def heartbeat_forever(settings):
    while True:
        with connect(settings.data_dir) as db:
            db.execute(
                "INSERT INTO worker_heartbeat(id,last_seen,colmap_available,blender_available) VALUES(1,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen,"
                "colmap_available=excluded.colmap_available,blender_available=excluded.blender_available",
                (now(), int(bool(shutil.which(settings.colmap))), int(bool(shutil.which(settings.blender))))
            )
        time.sleep(10)


def main():
    logging.basicConfig(level=logging.INFO)
    settings=Settings.load()
    initialize(settings.data_dir)
    preflight=inspect(settings)
    if not preflight["processing_host_ready_for_pilot"]:
        raise SystemExit("GPU worker preflight failed. Run: python -m minimo.preflight")
    threading.Thread(target=heartbeat_forever,args=(settings,),daemon=True).start()
    with connect(settings.data_dir) as db:
        db.execute("UPDATE jobs SET state='queued',stage='worker_restart' WHERE state='running'")
    last_purge=0
    while True:
        if time.monotonic()-last_purge>3600:
            purge_expired(settings);last_purge=time.monotonic()
        if not process_next(settings):time.sleep(1.5)

if __name__=="__main__":main()
