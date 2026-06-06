"""RQ worker entry point.

Usage:
    python -m workers.worker

Connects to Redis using REDIS_URL from .env and processes jobs from the
default queue plus the evidence, import, and deliverables queues.
Registers a heartbeat scheduled job on startup.
"""
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

import redis
from rq import Queue, Worker
from rq_scheduler import Scheduler

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUEUES = ["evidence", "import", "deliverables", "default"]
HEARTBEAT_INTERVAL = timedelta(minutes=1)


def _heartbeat() -> dict:
    """Lightweight health probe persisted in Redis by rq-scheduler."""
    import time
    return {"status": "ok", "ts": time.time()}


def register_heartbeat(conn: redis.Redis) -> None:
    scheduler = Scheduler(queue_name="default", connection=conn)
    # Cancel any existing heartbeat jobs before re-registering to avoid duplicates
    for job in scheduler.get_jobs():
        if getattr(job, "meta", {}).get("heartbeat"):
            scheduler.cancel(job)
    scheduler.schedule(
        scheduled_time=datetime.now(timezone.utc),
        func="workers.worker._heartbeat",
        interval=int(HEARTBEAT_INTERVAL.total_seconds()),
        repeat=None,
        meta={"heartbeat": True},
    )
    logger.info("Heartbeat scheduled every %s", HEARTBEAT_INTERVAL)


def main() -> None:
    conn = redis.from_url(settings.redis_url)
    register_heartbeat(conn)
    queues = [Queue(name, connection=conn) for name in QUEUES]
    logger.info("Starting worker; queues: %s", QUEUES)
    worker = Worker(queues, connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
