"""
Utilities for cleaning and normalizing raw sensor data before enrichment.
"""
from src.spark.usage_tracker import NormalizationRuleUsageTracker as Usage
from typing import Dict, List, Optional
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.database import SessionLocal
from src.database.models import NormalizationRule
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DataCleaner:
    """Cleans up incoming raw sensor dataframes.

    Responsibilities:
    - Make all incoming sensor keys case-insensitive by lowering column names.
    - Normalize known raw keys to canonical column names used by the pipeline.
    """

    # Seed-only: default rules to initialize the database on startup.
    # At runtime, mapping is loaded from DB and these are NOT applied directly.
    KEY_NORMALIZATION_MAP: Dict[str, str] = {
        # sensor id variants
        "sensorid": "sensorId",
        "sensor_id": "sensorId",
        "sensor-id": "sensorId",
        # ingestion id variants
        "ingestionid": "ingestion_id",
        "ingestion_id": "ingestion_id",
        "ingestion-id": "ingestion_id",
        # temperature
        "temperature": "temperature",
        # humidity
        "humidity": "humidity",
        # event timestamp from device
        "timestamp": "timestamp",
        "time": "timestamp",
        "ts": "timestamp",
    }

    @staticmethod
    def lower_columns(df: DataFrame) -> DataFrame:
        """Return a dataframe with all top-level column names lower-cased.

        If multiple columns differ only by case (e.g., "sensorId" and "SENSORID"),
        keep the first occurrence and drop the rest to avoid duplicate names.
        """
        seen = set()
        cols = []
        for c in df.columns:
            lc = c.lower()
            if lc in seen:
                # skip duplicates that collide after lower-casing
                continue
            seen.add(lc)
            cols.append(F.col(c).alias(lc))
        return df.select(cols)

    def _load_dynamic_rules(self, ingestion_id: Optional[str] = None) -> Dict[str, str]:
        """Load enabled normalization rules from the database (raw->canonical).
        
        Priority order:
        1. Rules specific to the ingestion_id
        2. Global rules (ingestion_id is NULL) as fallback
        """
        try:
            db: Session = SessionLocal()
            # Use a single query to fetch all enabled rules for the given ingestion_id or global
            dynamic_map = {}
            query = db.query(NormalizationRule).filter(NormalizationRule.enabled == True)
            if ingestion_id:
                query = query.filter(
                    (NormalizationRule.ingestion_id == ingestion_id) |
                    (NormalizationRule.ingestion_id.is_(None))
                )
            else:
                query = query.filter(NormalizationRule.ingestion_id.is_(None))
            rules = query.all()

            # Apply precedence: ingestion-specific rules override global rules
            for r in rules:
                raw_key_lower = r.raw_key.lower()
                # Only override if not already set, or if this rule is ingestion-specific
                if (r.ingestion_id == ingestion_id) or (raw_key_lower not in dynamic_map):
                    dynamic_map[raw_key_lower] = r.canonical_key

            logger.debug("Total normalization rules loaded: %d", len(dynamic_map))
            return dynamic_map
        except Exception as e:
            logger.warning("Failed to load normalization rules from DB: %s", e)
            return {}
        finally:
            try:
                db.close()
            except Exception:
                pass

    def normalize_sensor_columns(self, df: DataFrame, ingestion_id: Optional[str] = None) -> DataFrame:
        """Lower-case all columns, then alias known keys to canonical names.

        Args:
            df: Input DataFrame with raw sensor data
            ingestion_id: Source identifier for loading specific normalization rules

        Unknown columns are preserved (kept lower-case) to avoid data loss.
        Ingestion-specific rules override global rules when both exist.
        """
        lowered = self.lower_columns(df)
        # Load rules from DB with ingestion_id specificity
        effective_map = self._load_dynamic_rules(ingestion_id)
        matched_keys = [c for c in lowered.columns if c in effective_map]
        
        if effective_map:
            logger.info("Applying %d normalization rules for ingestion_id='%s' (matched %d keys)", 
                       len(effective_map), ingestion_id or "global", len(matched_keys))
        else:
            logger.info("No normalization rules found; leaving columns as-is (lower-cased)")

        # Buffer usage for matched rules (non-blocking, aggregated)
        if matched_keys:
            self._increment_rule_usage(matched_keys)

        return lowered.select([
            F.col(c).alias(effective_map.get(c, c))
            for c in lowered.columns
        ])

    def _increment_rule_usage(self, matched_raw_keys: List[str]) -> None:
        """Buffer usage increments; a background worker flushes to DB.

        This counts one application per matched column per call, non-blocking.
        """
        try:
            Usage.increment(matched_raw_keys)
        except Exception as e:
            # Do not block normalization on metrics issues
            logger.debug("Failed to buffer rule usage: %s", e)

    # Aggregator lifecycle is managed by NormalizationRuleUsageTracker

    @classmethod
    def seed_normalization_rules(cls) -> int:
        """Seed static KEY_NORMALIZATION_MAP into DB if missing.

        Returns the number of rules inserted. No-op for existing entries.
        """
        inserted = 0
        try:
            db: Session = SessionLocal()
            try:
                for raw_key, canonical_key in cls.KEY_NORMALIZATION_MAP.items():
                    rk = raw_key.strip().lower()
                    exists = (
                        db.query(NormalizationRule.id)
                        .filter(func.lower(NormalizationRule.raw_key) == rk)
                        .first()
                    )
                    if exists:
                        continue
                    db.add(
                        NormalizationRule(
                            raw_key=rk,
                            canonical_key=canonical_key,
                            enabled=True,
                        )
                    )
                    inserted += 1
                if inserted:
                    db.commit()
                    logger.info("Seeded %d normalization rules from static map", inserted)
            except Exception as e:
                db.rollback()
                logger.error("Failed seeding normalization rules: %s", e)
                raise
            finally:
                db.close()
        except Exception as e:
            logger.error("Error accessing DB for seeding normalization rules: %s", e)
        return inserted
