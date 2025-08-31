"""
Main SparkManager class that orchestrates all Spark operations.
"""
import logging
import time
from typing import Dict, Any, List

from .session import SparkSessionManager
from .streaming import StreamingManager
from .data_access import DataAccessManager
from .diagnostics import SparkDiagnostics
from .master_client import SparkMasterClient
from ..schema_inference.manager import SchemaInferenceManager

logger = logging.getLogger(__name__)


class SparkManager:
    """
    Main manager for Spark operations in the SOAM smart city platform.

    Orchestrates:
    - Spark session management
    - Real-time streaming operations
    - Data access operations
    - Diagnostic and testing capabilities
    - Spark master status monitoring
    - Schema inference operations (async)
    """

    def __init__(self, spark_host: str, spark_port: str, minio_endpoint: str,
                 minio_access_key: str, minio_secret_key: str, minio_bucket: str,
                 spark_ui_port: str) -> None:
        """Initialize SparkManager with all components.

        Args:
            spark_host: Spark master host
            spark_port: Spark master port
            minio_endpoint: MinIO endpoint
            minio_access_key: MinIO access key
            minio_secret_key: MinIO secret key
            minio_bucket: MinIO bucket name
            spark_ui_port: Spark UI port
        """
        # Store configuration
        self.minio_bucket: str = minio_bucket

        # Initialize core components
        self.session_manager: SparkSessionManager = SparkSessionManager(
            spark_host, spark_port, minio_endpoint,
            minio_access_key, minio_secret_key
        )

        self.streaming_manager: StreamingManager = StreamingManager(
            self.session_manager, minio_bucket)
        self.data_access = DataAccessManager(
            self.session_manager, minio_bucket)
        self.diagnostics = SparkDiagnostics(self.session_manager, minio_bucket)
        self.master_client = SparkMasterClient(spark_host, spark_ui_port)

        # Initialize async schema inference manager
        self.schema_inference_manager = SchemaInferenceManager(
            self.session_manager.spark)

        # Initialize streaming if data is available
        self._initialize_streaming()

    def _initialize_streaming(self) -> None:
        """Initialize streaming jobs if data directory is available."""
        if self.streaming_manager.is_data_directory_ready():
            self.streaming_manager.start_streams_safely()
        else:
            logger.warning(
                "Sensors data directory not ready. Streaming will be started when data becomes available.")
        
        # Start async schema inference stream
        try:
            self.schema_inference_manager.start_inference_stream_sync()
            logger.info("✅ Async schema inference stream started")
        except Exception as e:
            logger.error(f"❌ Failed to start schema inference stream: {e}")

    def get_spark_master_status(self) -> Dict[str, Any]:
        """Fetch Spark master status from the web UI API."""
        return self.master_client.get_spark_master_status()

    def get_running_streams_status(self) -> Dict[str, Any]:
        """Get status information about all running Spark streams."""
        try:
            spark = self.session_manager.spark
            active_streams = []
            
            # Get all active streaming queries
            for query in spark.streams.active:
                stream_info = {
                    "id": query.id,
                    "name": query.name or "Unnamed Stream",
                    "runId": query.runId,
                    "isActive": query.isActive,
                    "status": "ACTIVE" if query.isActive else "TERMINATED"
                }
                
                # Try to get progress information
                try:
                    progress = query.lastProgress
                    if progress:
                        stream_info.update({
                            "inputRowsPerSecond": progress.get("inputRowsPerSecond", 0),
                            "processedRowsPerSecond": progress.get("processedRowsPerSecond", 0),
                            "batchDuration": progress.get("durationMs", {}).get("triggerExecution", 0),
                            "timestamp": progress.get("timestamp", ""),
                            "batchId": progress.get("batchId", 0),
                            "numInputRows": progress.get("numInputRows", 0)
                        })
                        
                        # Get sources information
                        sources = progress.get("sources", [])
                        if sources:
                            stream_info["sources"] = [
                                {
                                    "description": source.get("description", "Unknown"),
                                    "inputRowsPerSecond": source.get("inputRowsPerSecond", 0),
                                    "processedRowsPerSecond": source.get("processedRowsPerSecond", 0),
                                    "numInputRows": source.get("numInputRows", 0)
                                }
                                for source in sources
                            ]
                            
                        # Get sink information
                        sink = progress.get("sink", {})
                        if sink:
                            stream_info["sink"] = {
                                "description": sink.get("description", "Unknown"),
                                "numOutputRows": sink.get("numOutputRows", 0)
                            }
                    
                    # Get exception if any
                    exception = query.exception()
                    if exception:
                        stream_info["exception"] = str(exception)
                        stream_info["status"] = "ERROR"
                        
                except Exception as e:
                    logger.warning(f"Could not get progress for stream {query.id}: {e}")
                    stream_info["progressError"] = str(e)
                
                active_streams.append(stream_info)
            
            # Get information about specific streams we manage
            managed_streams = {}
            
            # Check enrichment stream
            if hasattr(self.streaming_manager, 'enrichment_manager') and self.streaming_manager.enrichment_manager:
                enrich_query = getattr(self.streaming_manager.enrichment_manager, 'enrich_query', None)
                if enrich_query:
                    managed_streams["enrichment"] = {
                        "id": enrich_query.id,
                        "name": enrich_query.name or "Sensor Data Enrichment",
                        "isActive": enrich_query.isActive,
                        "type": "enrichment"
                    }
            
            # Check schema inference stream
            if hasattr(self, 'schema_inference_manager') and self.schema_inference_manager:
                schema_query = getattr(self.schema_inference_manager, 'query', None)
                if schema_query:
                    managed_streams["schema_inference"] = {
                        "id": schema_query.id,
                        "name": schema_query.name or "bronze_layer_schema_discovery",
                        "isActive": schema_query.isActive,
                        "type": "schema_inference"
                    }
            
            return {
                "totalActiveStreams": len(active_streams),
                "activeStreams": active_streams,
                "managedStreams": managed_streams,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Error getting running streams status: {e}")
            return {
                "error": str(e),
                "totalActiveStreams": 0,
                "activeStreams": [],
                "managedStreams": {},
                "timestamp": time.time()
            }

    # ================================================================
    # Data Access Methods
    # ================================================================

    def get_streaming_average_temperature(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """Get streaming average temperature data for the specified time window."""
        # Ensure streams are running
        self.streaming_manager.ensure_streams_running()
        return self.data_access.get_streaming_average_temperature(minutes)

    def get_temperature_alerts(self, since_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get recent temperature alerts."""
        # Ensure streams are running
        self.streaming_manager.ensure_streams_running()
        return self.data_access.get_temperature_alerts(since_minutes)

    def get_enrichment_summary(self, minutes: int = 10) -> Dict[str, Any]:
        """Summarize enrichment inputs and recent activity."""
        # Ensure enrichment has been attempted
        self.streaming_manager.ensure_streams_running()
        return self.data_access.get_enrichment_summary(minutes)

    # ================================================================
    # Testing and Diagnostics
    # ================================================================

    def test_spark_basic_computation(self) -> Dict[str, Any]:
        """Test basic Spark functionality."""
        return self.diagnostics.test_spark_basic_computation()

    def test_sensor_data_access(self) -> Dict[str, Any]:
        """Test access to sensor data in MinIO."""
        return self.diagnostics.test_sensor_data_access()

    # ================================================================
    # Lifecycle Management
    # ================================================================

    def close(self) -> None:
        """Clean shutdown of SparkManager."""
        logger.info("Shutting down SparkManager...")

        # Stop streaming queries
        self.streaming_manager.stop_streams()

        # Stop Spark session
        self.session_manager.stop()

        logger.info("SparkManager shutdown complete")
