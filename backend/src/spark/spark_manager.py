"""
Main SparkManager class that orchestrates all Spark operations.
"""
import logging
from typing import Dict, Any

from .session import SparkSessionManager
from .streaming import StreamingManager
from .data_access import DataAccessManager
from .diagnostics import SparkDiagnostics
from .master_client import SparkMasterClient

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
    """
    
    def __init__(self, spark_host: str, spark_port: str, minio_endpoint: str, 
                 minio_access_key: str, minio_secret_key: str, minio_bucket: str, 
                 spark_ui_port: str):
        """Initialize SparkManager with all components."""
        # Store configuration
        self.minio_bucket = minio_bucket
        
        # Initialize core components
        self.session_manager = SparkSessionManager(
            spark_host, spark_port, minio_endpoint, 
            minio_access_key, minio_secret_key
        )
        
        self.streaming_manager = StreamingManager(self.session_manager, minio_bucket)
        self.data_access = DataAccessManager(self.session_manager, minio_bucket)
        self.diagnostics = SparkDiagnostics(self.session_manager, minio_bucket)
        self.master_client = SparkMasterClient(spark_host, spark_ui_port)
        
        # Initialize streaming if data is available
        self._initialize_streaming()

    def _initialize_streaming(self) -> None:
        """Initialize streaming jobs if data directory is available."""
        if self.streaming_manager.is_data_directory_ready():
            self.streaming_manager.start_streams_safely()
        else:
            logger.warning("Sensors data directory not ready. Streaming will be started when data becomes available.")

    def get_spark_master_status(self) -> Dict[str, Any]:
        """Fetch Spark master status from the web UI API."""
        return self.master_client.get_spark_master_status()

    # ================================================================
    # Data Access Methods
    # ================================================================
    
    def get_streaming_average_temperature(self, minutes: int = 30) -> Dict[str, Any]:
        """Get streaming average temperature data for the specified time window."""
        # Ensure streams are running
        self.streaming_manager.ensure_streams_running()
        return self.data_access.get_streaming_average_temperature(minutes)

    def get_temperature_alerts(self, since_minutes: int = 60) -> Dict[str, Any]:
        """Get recent temperature alerts."""
        # Ensure streams are running
        self.streaming_manager.ensure_streams_running()
        return self.data_access.get_temperature_alerts(since_minutes)

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