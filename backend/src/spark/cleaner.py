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

    def normalize_to_union_schema(self, df: DataFrame, ingestion_id: Optional[str] = None) -> DataFrame:
        """Transform DataFrame to union schema format with normalization applied.
        
        Args:
            df: Input DataFrame with raw sensor data
            ingestion_id: Source identifier for loading specific normalization rules
            
        Returns:
            DataFrame with union schema structure (ingestion_id, timestamp, sensor_data, normalized_data)
        """
        from .union_schema import UnionSchemaTransformer
        
        # First apply legacy normalization to get clean column names
        normalized_legacy = self.normalize_sensor_columns(df, ingestion_id)
        
        # Convert to union schema format
        union_df = UnionSchemaTransformer.legacy_to_union(normalized_legacy, "ingestion_id")
        
        # Apply additional normalization rules specific to union schema
        normalization_rules = self._load_dynamic_rules(ingestion_id)
        if normalization_rules:
            union_df = UnionSchemaTransformer.apply_normalization_to_union(union_df, normalization_rules)
        
        return union_df

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
            
            # Log the specific rules being applied
            for raw_key in matched_keys:
                canonical_key = effective_map[raw_key]
                logger.info(f"Normalization rule: '{raw_key}' -> '{canonical_key}' for ingestion_id='{ingestion_id or 'global'}'")
                
            # Special debug for temperature field
            temp_related = [k for k in lowered.columns if 'temp' in k.lower()]
            if temp_related:
                logger.info(f"Temperature-related columns found in raw data: {temp_related}")
                for temp_col in temp_related:
                    if temp_col in effective_map:
                        logger.info(f"Temperature column '{temp_col}' will be normalized to '{effective_map[temp_col]}'")
                    else:
                        logger.warning(f"Temperature column '{temp_col}' has no normalization rule!")
        else:
            logger.info("No normalization rules found; leaving columns as-is (lower-cased)")

        # Buffer usage for matched rules (non-blocking, aggregated)
        if matched_keys:
            self._increment_rule_usage(matched_keys)

        # Build column selections, handling potential duplicates from mapping multiple raw keys to same canonical key
        canonical_to_raw = {}
        for c in lowered.columns:
            canonical_name = effective_map.get(c, c)
            if canonical_name not in canonical_to_raw:
                canonical_to_raw[canonical_name] = []
            canonical_to_raw[canonical_name].append(c)

        # Select columns, using coalesce for canonical names that have multiple raw key sources
        select_cols = []
        for canonical_name, raw_keys in canonical_to_raw.items():
            if len(raw_keys) == 1:
                # Single source, simple alias
                select_cols.append(F.col(raw_keys[0]).alias(canonical_name))
            else:
                # Multiple sources, use coalesce to pick first non-null value
                coalesce_cols = [F.col(raw_key) for raw_key in raw_keys]
                select_cols.append(F.coalesce(*coalesce_cols).alias(canonical_name))
                logger.debug(f"Merged {len(raw_keys)} columns into '{canonical_name}': {raw_keys}")

        return lowered.select(select_cols)

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
                            created_by="system",  # System-created seed rules
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
