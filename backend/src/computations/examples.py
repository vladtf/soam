"""Example computation definitions for user guidance."""
from typing import List, Dict, Any

# Example definitions to guide frontend users (datasets are validated separately)
EXAMPLE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "id": "hot-temps",
        "title": "Top hot temperatures (gold_temp_avg)",
        "description": "Find readings with avg_temp > 25, sorted by avg_temp desc.",
        "dataset": "gold_temp_avg",
        "definition": {
            "select": ["sensorId", "avg_temp", "time_start"],
            "where": [
                {"col": "avg_temp", "op": ">", "value": 25}
            ],
            "orderBy": [
                {"col": "avg_temp", "dir": "desc"}
            ],
            "limit": 50
        }
    },
    {
        "id": "sensor-summary-table",
        "title": "Sensor Activity Summary Table",
        "description": "Complete sensor activity table with statistics, readings count, and latest values.",
        "dataset": "enriched",
        "definition": {
            "select": [
                "ingestion_id",
                "sensor_data.sensorId as sensor_id", 
                "normalized_data.temperature as latest_temp",
                "normalized_data.humidity as latest_humidity", 
                "ingest_date",
                "source"
            ],
            "where": [
                {"col": "ingest_date", "op": ">=", "value": "2024-08-20"}
            ],
            "orderBy": [
                {"col": "ingest_ts", "dir": "desc"}
            ],
            "limit": 100
        }
    },
    {
        "id": "daily-readings-summary",
        "title": "Daily Sensor Readings Summary",
        "description": "Aggregated table showing daily sensor statistics with min, max, and average values.",
        "dataset": "enriched", 
        "definition": {
            "select": [
                "ingest_date",
                "ingestion_id",
                "COUNT(*) as reading_count",
                "AVG(normalized_data.temperature) as avg_temperature",
                "MIN(normalized_data.temperature) as min_temperature", 
                "MAX(normalized_data.temperature) as max_temperature",
                "AVG(normalized_data.humidity) as avg_humidity"
            ],
            "where": [
                {"col": "normalized_data.temperature", "op": "IS NOT NULL"},
                # {"col": "ingest_date", "op": ">=", "value": "2024-08-01"}
            ],
            "groupBy": ["ingest_date", "ingestion_id"],
            "orderBy": [
                {"col": "ingest_date", "dir": "desc"},
                {"col": "reading_count", "dir": "desc"}
            ],
            "limit": 50
        }
    },
    {
        "id": "alerts-keyword",
        "title": "Alerts containing 'overheat' (alerts)",
        "description": "Filter alerts where message contains keyword.",
        "dataset": "alerts",
        "definition": {
            "select": ["id", "level", "message", "ts"],
            "where": [
                {"col": "message", "op": "contains", "value": "overheat"}
            ],
            "orderBy": [
                {"col": "ts", "dir": "desc"}
            ],
            "limit": 20
        }
    },
    {
        "id": "below-zero",
        "title": "Negative temperature metrics (sensors)",
        "description": "Metric == temperature and value < 0.",
        "dataset": "sensors",
        "definition": {
            "where": [
                {"col": "metric", "op": "==", "value": "temperature"},
                {"col": "value", "op": "<", "value": 0}
            ],
            "orderBy": [
                {"col": "ts", "dir": "desc"}
            ],
            "limit": 100
        }
    },
    {
        "id": "average-temperature",
        "title": "Average Temperature by 1-Minute Windows",
        "description": "Calculate average temperature readings grouped by 1-minute time windows from enriched data.",
        "dataset": "enriched",
        "recommended_tile_type": "timeseries",
        "definition": {
            "select": [
                "window(ingest_ts, '1 minute').start as time_start",
                "window(ingest_ts, '1 minute').end as time_end",
                "AVG(normalized_data.temperature) as avg_temperature",
                "COUNT(*) as reading_count",
                "MIN(normalized_data.temperature) as min_temperature",
                "MAX(normalized_data.temperature) as max_temperature"
            ],
            "where": [
                {"col": "normalized_data.temperature", "op": "IS NOT NULL"},
                # {"col": "ingest_date", "op": ">=", "value": "2024-08-01"}
            ],
            "groupBy": ["window(ingest_ts, '1 minute')"],
            "orderBy": [
                {"col": "time_start", "dir": "asc"}
            ],
            "limit": 50
        }
    },
    {
        "id": "temperature-alerts",
        "title": "Temperature Alerts (gold_alerts)",
        "description": "Current temperature alerts where readings exceed the configured threshold.",
        "dataset": "gold_alerts",
        "recommended_tile_type": "table",
        "definition": {
            "select": [
                "sensorId",
                "temperature", 
                "event_time",
                "alert_type"
            ],
            "where": [
                {"col": "alert_type", "op": "==", "value": "TEMP_OVER_LIMIT"}
            ],
            "orderBy": [
                {"col": "event_time", "dir": "desc"}
            ],
            "limit": 100
        }
    },
    {
        "id": "temperature-over-threshold",
        "title": "Temperature Over Threshold Detection (Throttled)",
        "description": "Detect temperature readings that exceed the configured threshold (30°C default) with time-based throttling. Shows max one alert per sensor per minute, matching the streaming alert detector logic.",
        "dataset": "enriched",
        "recommended_tile_type": "table",
        "definition": {
            "select": [
                "ingestion_id as sensorId",
                "MAX(normalized_data.temperature) as temperature", 
                "MAX(ingest_ts) as event_time",
                "window(ingest_ts, '1 minute').start as window_start",
                "window(ingest_ts, '1 minute').end as window_end"
            ],
            "where": [
                {"col": "normalized_data.temperature", "op": "IS NOT NULL"},
                {"col": "normalized_data.temperature", "op": ">", "value": "30.0"}
            ],
            "groupBy": ["window(ingest_ts, '1 minute')", "ingestion_id"],
            "orderBy": [
                {"col": "window_start", "dir": "desc"}
            ],
            "limit": 100
        }
    }
]


def get_example_by_id(example_id: str) -> Dict[str, Any] | None:
    """Get an example computation by ID."""
    return next((ex for ex in EXAMPLE_DEFINITIONS if ex["id"] == example_id), None)


def get_dsl_info() -> Dict[str, Any]:
    """Get DSL information for the frontend."""
    return {
        "keys": ["select", "where", "orderBy", "limit", "groupBy"],
        "ops": [">", ">=", "<", "<=", "==", "!=", "contains", "IS NOT NULL", "IS NULL"],
        "notes": "All where conditions are ANDed. Dataset is chosen separately. GroupBy enables aggregation functions in select."
    }
