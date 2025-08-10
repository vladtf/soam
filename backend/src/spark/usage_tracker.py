"""
Background aggregation and persistence of normalization rule usage.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import logging
import threading
from queue import SimpleQueue
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import SessionLocal
from src.database.models import NormalizationRule

logger = logging.getLogger(__name__)


class NormalizationRuleUsageTracker:
    """Aggregates rule usage in-memory and flushes periodically in background."""

    _queue: SimpleQueue[str] = SimpleQueue()
    _stop_event: threading.Event = threading.Event()
    _thread: Optional[threading.Thread] = None
    _flush_interval_sec: float = 5.0
    _max_batch_size: int = 500

    @classmethod
    def increment(cls, raw_keys: List[str]) -> None:
        """Queue raw keys for usage counting; non-blocking for producer."""
        q = cls._queue
        for rk in raw_keys:
            q.put(rk.lower())

    @classmethod
    def _worker(cls) -> None:
        logger.info("Normalization usage tracker started")
        while not cls._stop_event.wait(timeout=cls._flush_interval_sec):
            try:
                cls._flush_now()
            except Exception as e:
                logger.error("Error flushing rule usage: %s", e)
        # final flush
        try:
            cls._flush_now()
        except Exception as e:
            logger.error("Error on final flush of rule usage: %s", e)
        logger.info("Normalization usage tracker stopped")

    @classmethod
    def _flush_now(cls) -> None:
        # Drain queue into local counter
        pending: Dict[str, int] = {}
        drained = 0
        while drained < cls._max_batch_size:
            if cls._queue.empty():
                break
            key = cls._queue.get()
            pending[key] = pending.get(key, 0) + 1
            drained += 1

        if not pending:
            return

        now = datetime.now(timezone.utc)
        try:
            db: Session = SessionLocal()
            try:
                for rk, inc in pending.items():
                    rule = (
                        db.query(NormalizationRule)
                        .filter(func.lower(NormalizationRule.raw_key) == rk)
                        .first()
                    )
                    if not rule:
                        continue
                    rule.applied_count = (getattr(rule, "applied_count", 0) or 0) + int(inc)
                    rule.last_applied_at = now
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("DB commit failed for rule usage flush: %s", e)
            finally:
                db.close()
        except Exception as e:
            logger.error("DB access error in rule usage flush: %s", e)

    @classmethod
    def start(cls) -> None:
        if cls._thread and cls._thread.is_alive():
            return
        cls._stop_event.clear()
        cls._thread = threading.Thread(target=cls._worker, name="norm-usage-tracker", daemon=True)
        cls._thread.start()

    @classmethod
    def stop(cls, timeout: float = 5.0) -> None:
        if not cls._thread:
            return
        cls._stop_event.set()
        cls._thread.join(timeout=timeout)
        cls._thread = None
