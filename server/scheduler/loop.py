import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session
from server.db.session import SessionLocal, bind_session
from server.db.repo import PlatformRepo
from server.db.models import Transaction
from server.adapters.clock import clock
from server.settings import settings

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, timer_handler: Optional[Callable[[str, str], Any]] = None):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.timer_handler = timer_handler

    def set_handler(self, handler: Callable[[str, str], Any]) -> None:
        self.timer_handler = handler

    def run_due_jobs_once(self, db: Optional[Session] = None) -> List[Dict[str, str]]:
        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True

        repo = PlatformRepo(db)
        due = repo.due_jobs(clock.now())
        results = []

        try:
            for job in due:
                job_id = job.id
                merchant_id = job.merchant_id
                reason = job.reason

                repo.update_job_status(job_id, "running")
                try:
                    if self.timer_handler:
                        with bind_session(db):
                            self.timer_handler(merchant_id, reason)
                    elif reason == "activation_check":
                        # Platform fallback logic for activation check if agent is not yet wired
                        # Checks if 0 transactions, nudges or escalates
                        txns = repo.db.query(Transaction).filter(
                            Transaction.merchant_id == merchant_id,
                            Transaction.status == "success"
                        ).count()
                        if txns == 0:
                            repo.save_action(
                                merchant_id=merchant_id,
                                action_type="SEND_ACTIVATION_NUDGE",
                                params={"nudge_num": 1},
                                reasoning="Device installed with 0 transactions in 24h. Sending activation nudge.",
                                autonomy_level="L3",
                                status="executed"
                            )
                    repo.update_job_status(job_id, "done")
                    results.append({"job_id": job_id, "merchant_id": merchant_id, "status": "done"})
                except Exception as e:
                    repo.update_job_status(job_id, "failed")
                    results.append({"job_id": job_id, "merchant_id": merchant_id, "status": "failed", "error": str(e)})
        finally:
            if owns_session:
                db.close()

        return results

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                self.run_due_jobs_once()
            except Exception:
                logger.exception("Scheduler iteration failed")
            await asyncio.sleep(settings.SCHEDULER_TICK_SECONDS)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

scheduler = Scheduler()
