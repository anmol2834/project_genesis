"""
emailservice — Worker Process Entry Point
=========================================
Run each worker as an independent process:

  python run_worker.py gmail_fetch
  python run_worker.py outlook_fetch
  python run_worker.py smtp_fetch
  python run_worker.py filter_dedup
  python run_worker.py storage
  python run_worker.py ai_handoff
  python run_worker.py history_recovery
  python run_worker.py smtp_poller
  python run_worker.py watch_sync

Each process is completely isolated:
  - Own Kafka consumer group instance
  - Own bloom filter (DB constraint is cross-process dedup)
  - Own DB connection pool
  - Crash in one worker never affects others

For production: run multiple instances of each worker behind a process manager
(systemd, supervisord, Kubernetes Deployment with replicas).
"""
from __future__ import annotations
import asyncio, logging, sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.logger import setup_logging
from shared.database import init_database, close_database
from shared.cache import init_redis, close_redis

logger = logging.getLogger("emailservice.run_worker")


async def _run(worker_type: str) -> None:
    setup_logging(f"emailservice-{worker_type}")
    await init_database()
    await init_redis()

    # Start Prometheus metrics server on each worker process
    import config as cfg
    from metrics import start_metrics_server
    if cfg.METRICS_ENABLED:
        # Each worker gets a unique port offset to avoid conflicts
        port_offset = {
            "gmail_fetch": 0, "outlook_fetch": 1, "smtp_fetch": 2,
            "filter_dedup": 3, "storage": 4, "ai_handoff": 5,
            "history_recovery": 6, "watch_sync": 7, "smtp_poller": 8,
        }.get(worker_type, 9)
        start_metrics_server(cfg.METRICS_PORT + port_offset)

    try:
        if worker_type == "gmail_fetch":
            from workers.gmail_fetch_worker import GmailFetchWorker
            await GmailFetchWorker().start()

        elif worker_type == "outlook_fetch":
            from workers.outlook_fetch_worker import OutlookFetchWorker
            await OutlookFetchWorker().start()

        elif worker_type == "smtp_fetch":
            from workers.smtp_fetch_worker import SmtpFetchWorker, SmtpPoller
            worker = SmtpFetchWorker()
            poller = SmtpPoller()
            # Run both concurrently in the same process
            await asyncio.gather(worker.start(), poller.run())

        elif worker_type == "filter_dedup":
            from workers.filter_dedup_worker import FilterDedupWorker
            await FilterDedupWorker().start()

        elif worker_type == "storage":
            from workers.storage_worker import StorageWorker
            await StorageWorker().start()

        elif worker_type == "ai_handoff":
            from workers.ai_handoff_worker import AIHandoffWorker
            await AIHandoffWorker().start()

        elif worker_type == "history_recovery":
            from workers.history_recovery_worker import HistoryRecoveryWorker
            await HistoryRecoveryWorker().run_forever(interval_seconds=1800)

        elif worker_type == "watch_sync":
            from workers.watch_manager import WatchManager
            manager = WatchManager()
            # Run once immediately, then every 6 hours
            while True:
                await manager.sync_all_watches()
                await asyncio.sleep(6 * 3600)

        elif worker_type == "smtp_poller":
            from workers.smtp_fetch_worker import SmtpPoller
            await SmtpPoller().run()

        else:
            logger.error("Unknown worker type: %s", worker_type)
            logger.error("Valid types: gmail_fetch, outlook_fetch, smtp_fetch, "
                         "filter_dedup, storage, ai_handoff, history_recovery, "
                         "watch_sync, smtp_poller")
            sys.exit(1)

    finally:
        await close_database()
        await close_redis()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_worker.py <worker_type>")
        sys.exit(1)

    worker_type = sys.argv[1]
    asyncio.run(_run(worker_type))
