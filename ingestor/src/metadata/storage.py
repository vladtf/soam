"""
SQLite storage for metadata information.
"""
import json
import logging
import sqlite3
import threading
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


class MetadataStorage:
    """SQLite storage for dataset metadata."""
    
    def __init__(self, db_path: str = "/data/metadata.db"):
        """
        Initialize SQLite storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        logger.info(f"Initialized metadata storage at {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _init_database(self):
        """Initialize database tables."""
        with self.lock:
            with self._get_connection() as conn:
                # Dataset metadata table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dataset_metadata (
                        ingestion_id TEXT PRIMARY KEY,
                        topic TEXT NOT NULL,
                        record_count INTEGER DEFAULT 0,
                        first_seen TEXT,
                        last_seen TEXT,
                        unique_sensor_count INTEGER DEFAULT 0,
                        unique_sensor_ids TEXT, -- JSON array
                        data_size_bytes INTEGER DEFAULT 0,
                        schema_fields TEXT, -- JSON array of schema fields
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Schema field evolution tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_evolution (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ingestion_id TEXT NOT NULL,
                        field_name TEXT NOT NULL,
                        field_type TEXT NOT NULL,
                        first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                        sample_values TEXT, -- JSON array
                        FOREIGN KEY (ingestion_id) REFERENCES dataset_metadata (ingestion_id)
                    )
                """)
                
                # Data quality metrics
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_quality (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ingestion_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL,
                        measurement_time TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (ingestion_id) REFERENCES dataset_metadata (ingestion_id)
                    )
                """)
                
                # Create indexes for better query performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_dataset_metadata_topic 
                    ON dataset_metadata (topic)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_schema_evolution_ingestion_field 
                    ON schema_evolution (ingestion_id, field_name)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_data_quality_ingestion_metric 
                    ON data_quality (ingestion_id, metric_name)
                """)
                
                conn.commit()
                logger.info("Database tables initialized successfully")
    
    def store_metadata_batch(self, metadata_list: List[Dict[str, Any]]) -> None:
        """
        Store a batch of metadata updates.
        
        Args:
            metadata_list: List of metadata dictionaries
        """
        if not metadata_list:
            return
            
        with self.lock:
            with self._get_connection() as conn:
                for metadata in metadata_list:
                    self._upsert_metadata(conn, metadata)
                conn.commit()
                
        logger.debug(f"Stored {len(metadata_list)} metadata updates")
    
    def _upsert_metadata(self, conn: sqlite3.Connection, metadata: Dict[str, Any]) -> None:
        """Upsert metadata for a single ingestion_id."""
        # Prepare data
        unique_sensor_ids_json = json.dumps(metadata.get("unique_sensor_ids", []))
        schema_fields_json = json.dumps(metadata.get("schema_fields", []))
        
        # Upsert main metadata
        conn.execute("""
            INSERT OR REPLACE INTO dataset_metadata (
                ingestion_id, topic, record_count, first_seen, last_seen,
                unique_sensor_count, unique_sensor_ids, data_size_bytes,
                schema_fields, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata.get("ingestion_id"),
            metadata.get("topic"),
            metadata.get("record_count", 0),
            metadata.get("first_seen"),
            metadata.get("last_seen"),
            metadata.get("unique_sensor_count", 0),
            unique_sensor_ids_json,
            metadata.get("data_size_bytes", 0),
            schema_fields_json,
            metadata.get("updated_at")
        ))
        
        # Update schema evolution tracking
        self._update_schema_evolution(conn, metadata)
    
    def _update_schema_evolution(self, conn: sqlite3.Connection, metadata: Dict[str, Any]) -> None:
        """Update schema evolution tracking."""
        ingestion_id = metadata.get("ingestion_id")
        schema_fields = metadata.get("schema_fields", [])
        
        for field in schema_fields:
            field_name = field.get("name")
            field_type = field.get("type")
            sample_values = json.dumps(field.get("sample_values", []))
            
            # Check if field already exists
            existing = conn.execute("""
                SELECT id FROM schema_evolution 
                WHERE ingestion_id = ? AND field_name = ? AND field_type = ?
            """, (ingestion_id, field_name, field_type)).fetchone()
            
            if not existing:
                # New field or type change
                conn.execute("""
                    INSERT INTO schema_evolution (
                        ingestion_id, field_name, field_type, sample_values
                    ) VALUES (?, ?, ?, ?)
                """, (ingestion_id, field_name, field_type, sample_values))
    
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """Get all dataset metadata."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM dataset_metadata 
                ORDER BY last_seen DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                metadata = dict(row)
                # Parse JSON fields
                metadata["unique_sensor_ids"] = json.loads(metadata.get("unique_sensor_ids", "[]"))
                metadata["schema_fields"] = json.loads(metadata.get("schema_fields", "[]"))
                results.append(metadata)
            
            return results
    
    def get_metadata_by_ingestion_id(self, ingestion_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for specific ingestion_id."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM dataset_metadata WHERE ingestion_id = ?
            """, (ingestion_id,))
            
            row = cursor.fetchone()
            if row:
                metadata = dict(row)
                metadata["unique_sensor_ids"] = json.loads(metadata.get("unique_sensor_ids", "[]"))
                metadata["schema_fields"] = json.loads(metadata.get("schema_fields", "[]"))
                return metadata
            
            return None
    
    def get_schema_evolution(self, ingestion_id: str) -> List[Dict[str, Any]]:
        """Get schema evolution for specific ingestion_id."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM schema_evolution 
                WHERE ingestion_id = ? 
                ORDER BY first_seen ASC
            """, (ingestion_id,))
            
            results = []
            for row in cursor.fetchall():
                evolution = dict(row)
                evolution["sample_values"] = json.loads(evolution.get("sample_values", "[]"))
                results.append(evolution)
            
            return results
    
    def get_topics_summary(self) -> List[Dict[str, Any]]:
        """Get summary statistics by topic."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    topic,
                    COUNT(*) as dataset_count,
                    SUM(record_count) as total_records,
                    SUM(data_size_bytes) as total_size_bytes,
                    SUM(unique_sensor_count) as total_unique_sensors,
                    MIN(first_seen) as earliest_data,
                    MAX(last_seen) as latest_data
                FROM dataset_metadata 
                GROUP BY topic
                ORDER BY total_records DESC
            """)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def store_data_quality_metric(self, ingestion_id: str, metric_name: str, metric_value: float) -> None:
        """Store a data quality metric."""
        with self.lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO data_quality (ingestion_id, metric_name, metric_value)
                    VALUES (?, ?, ?)
                """, (ingestion_id, metric_name, metric_value))
                conn.commit()
    
    def get_data_quality_metrics(self, ingestion_id: str) -> List[Dict[str, Any]]:
        """Get data quality metrics for specific ingestion_id."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT metric_name, metric_value, measurement_time
                FROM data_quality 
                WHERE ingestion_id = ?
                ORDER BY measurement_time DESC
            """, (ingestion_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old data quality metrics to prevent database bloat."""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM data_quality 
                    WHERE measurement_time < datetime('now', '-' || ? || ' days')
                """, (days_to_keep,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
        logger.info(f"Cleaned up {deleted_count} old data quality records")
        return deleted_count
