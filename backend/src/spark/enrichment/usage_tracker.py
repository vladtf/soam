"""
Normalization rule usage tracking via Prometheus metrics.
Exposes rule application counts for Grafana visualization.
"""
from __future__ import annotations

import os
import logging
from typing import List

from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Get pod name from environment (set by Kubernetes)
POD_NAME = os.getenv("POD_NAME", os.getenv("HOSTNAME", "unknown"))

# Prometheus counter for normalization rule applications
NORMALIZATION_RULE_APPLIED = Counter(
    "normalization_rule_applied_total",
    "Total times a normalization rule was applied during enrichment",
    ["pod", "raw_key"]
)


class NormalizationRuleUsageTracker:
    """
    Tracks normalization rule usage via Prometheus metrics.
    
    No background thread or database I/O - just increments in-memory counters
    that Prometheus scrapes via the /metrics endpoint.
    """

    @classmethod
    def increment(cls, raw_keys: List[str]) -> None:
        """
        Increment usage counter for each raw key.
        
        This is now a lightweight operation - just incrementing Prometheus counters.
        """
        for rk in raw_keys:
            NORMALIZATION_RULE_APPLIED.labels(pod=POD_NAME, raw_key=rk.lower()).inc()

    @classmethod
    def start(cls) -> None:
        """No-op for backward compatibility. Metrics are always available."""
        logger.info("✅ Normalization rule usage tracker initialized (Prometheus metrics)")

    @classmethod
    def stop(cls, timeout: float = 5.0) -> None:
        """No-op for backward compatibility. Metrics persist until process exit."""
        pass
