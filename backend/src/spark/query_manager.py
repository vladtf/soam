"""
Shared streaming query lifecycle management.

Provides reusable methods for finding, stopping, and reattaching to
Spark streaming queries — eliminating duplication across StreamingManager
and EnrichmentManager.
"""
import time
from typing import Optional

from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery

from src.utils.logging import get_logger

logger = get_logger(__name__)


class StreamingQueryManager:
    """Manages Spark streaming query lifecycle operations.
    
    Usage:
        qm = StreamingQueryManager(spark_session)
        existing = qm.get_by_name("my_query")
        qm.stop_gracefully("my_query", timeout_seconds=15)
        qm.stop_all()
    """

    def __init__(self, spark: SparkSession):
        self._spark = spark

    def get_by_name(self, name: str) -> Optional[StreamingQuery]:
        """Return active StreamingQuery by name if present.
        
        Args:
            name: Query name to search for
            
        Returns:
            StreamingQuery if found and active, None otherwise
        """
        try:
            for q in self._spark.streams.active:
                try:
                    if q.name == name:
                        return q
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def stop_gracefully(self, query_name: str, timeout_seconds: int = 15) -> None:
        """Stop a streaming query by name with a graceful shutdown period.
        
        Args:
            query_name: Name of the query to stop
            timeout_seconds: Maximum seconds to wait for graceful shutdown
        """
        existing = self.get_by_name(query_name)
        if not existing or not existing.isActive:
            return

        logger.info("🛑 Gracefully stopping query: %s", query_name)
        try:
            existing.stop()

            waited = 0
            while existing.isActive and waited < timeout_seconds:
                time.sleep(1)
                waited += 1

            if existing.isActive:
                logger.warning("⚠️ Query %s did not stop within %ds", query_name, timeout_seconds)
            else:
                logger.info("✅ Query %s stopped successfully", query_name)
        except Exception as e:
            logger.warning("⚠️ Error stopping query %s: %s", query_name, e)

    def stop_all(self) -> None:
        """Stop all active streaming queries."""
        logger.info("🛑 Stopping all active streaming queries...")
        try:
            active_queries = self._spark.streams.active
            for query in active_queries:
                try:
                    query_name = getattr(query, "name", "unnamed")
                    logger.info("🛑 Stopping query: %s", query_name)
                    query.stop()
                except Exception as e:
                    logger.warning("⚠️ Error stopping query: %s", e)

            if active_queries:
                time.sleep(2)
        except Exception as e:
            logger.warning("⚠️ Error stopping streaming queries: %s", e)

    def start_or_reattach(
        self,
        query_name: str,
        start_fn,
    ) -> Optional[StreamingQuery]:
        """Start a new query or reattach to an existing one.
        
        Args:
            query_name: Name of the query
            start_fn: Callable that starts and returns the new StreamingQuery
            
        Returns:
            The active StreamingQuery, or None if start failed
        """
        existing = self.get_by_name(query_name)
        if existing and existing.isActive:
            logger.info("✅ Reattached to existing query: %s", query_name)
            return existing

        # Stop stale query before starting fresh
        self.stop_gracefully(query_name)

        try:
            query = start_fn()
            logger.info("✅ Started query: %s", query_name)
            return query
        except Exception as e:
            if "already active" in str(e) or "Cannot start query with name" in str(e):
                logger.warning("⚠️ Query %s conflict, reattaching", query_name)
                return self.get_by_name(query_name)
            raise
