"""
Utilities for cleaning and normalizing raw sensor data before enrichment.
"""
from typing import Dict
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


class DataCleaner:
    """Cleans up incoming raw sensor dataframes.

    Responsibilities:
    - Make all incoming sensor keys case-insensitive by lowering column names.
    - Normalize known raw keys to canonical column names used by the pipeline.
    """

    # Map lower-cased raw keys to canonical column names used downstream
    KEY_NORMALIZATION_MAP: Dict[str, str] = {
        # sensor id variants
        "sensorid": "sensorId",
        "sensor_id": "sensorId",
        "sensor-id": "sensorId",
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

    def normalize_sensor_columns(self, df: DataFrame) -> DataFrame:
        """Lower-case all columns, then alias known keys to canonical names.

        Unknown columns are preserved (kept lower-case) to avoid data loss.
        """
        lowered = self.lower_columns(df)
        return lowered.select([
            F.col(c).alias(self.KEY_NORMALIZATION_MAP.get(c, c))
            for c in lowered.columns
        ])
