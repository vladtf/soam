"""
Spark session management and connectivity utilities.
"""
import os
import logging
from typing import Optional
from pyspark.sql import SparkSession
from cachetools import TTLCache, cached

logger = logging.getLogger(__name__)

# Shared TTL cache for connection checks (1 entry, 5 second TTL)
_connection_cache: TTLCache = TTLCache(maxsize=1, ttl=5.0)


class SparkSessionManager:
    """Manages Spark session lifecycle and connectivity."""
    
    def __init__(self, spark_host: str, spark_port: str, minio_endpoint: str,
                 minio_access_key: str, minio_secret_key: str):
        """Initialize SparkSessionManager with connection parameters."""
        self.spark_host = spark_host
        self.spark_port = spark_port
        self.minio_endpoint = minio_endpoint
        self.minio_access_key = minio_access_key
        self.minio_secret_key = minio_secret_key
        self._spark: Optional[SparkSession] = None
    
    @property
    def spark(self) -> SparkSession:
        """Get the current Spark session."""
        if self._spark is None:
            self._spark = self.create_session()
        return self._spark
    
    def create_session(self) -> SparkSession:
        """Create and configure a new Spark session."""
        # Get driver configuration from environment
        driver_host = os.getenv("SPARK_DRIVER_HOST", "backend")
        driver_bind_address = os.getenv("SPARK_DRIVER_BIND_ADDRESS", "0.0.0.0")
        driver_port = os.getenv("SPARK_DRIVER_PORT", "41397")
        block_manager_port = os.getenv("SPARK_BLOCK_MANAGER_PORT", "41398")
        
        spark = (
            SparkSession.builder
            .appName("SmartCityBackend")
            .master(f"spark://{self.spark_host}:{self.spark_port}")
            .config("spark.eventLog.enabled", "true")
            .config("spark.driver.host", driver_host)
            .config("spark.driver.bindAddress", driver_bind_address)
            .config("spark.driver.port", driver_port)
            .config("spark.blockManager.port", block_manager_port)
            .config("spark.hadoop.fs.s3a.endpoint", f"http://{self.minio_endpoint}")
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.access.key", self.minio_access_key)
            .config("spark.hadoop.fs.s3a.secret.key", self.minio_secret_key)
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.jars", os.getenv("SPARK_JARS", ""))
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            .config("spark.sql.mapKeyDedupPolicy", "LAST_WIN")  # Handle duplicate map keys
            .config("spark.sql.session.timeZone", "UTC")  # Use UTC for all timestamp operations
            # Performance tuning - reduce shuffle partitions to match executor count
            .config("spark.sql.shuffle.partitions", "8")  # Default 200 is too high for small clusters
            .config("spark.default.parallelism", "8")  # Match shuffle partitions
            .getOrCreate()
        )
        
        spark.sparkContext.setLogLevel("WARN")
        
        # Specifically suppress py4j verbose logging
        py4j_logger = logging.getLogger("py4j")
        py4j_logger.setLevel(logging.WARNING)
        py4j_clientserver_logger = logging.getLogger("py4j.clientserver")
        py4j_clientserver_logger.setLevel(logging.WARNING)
        
        return spark
    
    @cached(_connection_cache)
    def is_connected(self) -> bool:
        """
        Check if Spark session is available and working.
        
        Results are cached for 5 seconds to avoid frequent expensive SQL queries.
        """
        try:
            self.spark.sql("SELECT 1").collect()
            return True
        except Exception as e:
            logger.error(f"Spark connection check failed: {e}")
            return False
    
    def reconnect(self) -> bool:
        """Attempt to reconnect the Spark session."""
        try:
            # Stop existing session
            if self._spark is not None:
                self._spark.stop()
        except Exception as e:
            logger.warning(f"Error stopping existing Spark session: {e}")
        
        try:
            # Create new session
            self._spark = self.create_session()
            logger.info("Spark session reconnected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reconnect Spark session: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the Spark session and all active streaming queries."""
        try:
            if self._spark is not None:
                # First, stop all active streaming queries
                logger.info("Stopping all active streaming queries...")
                try:
                    active_queries = self._spark.streams.active
                    for query in active_queries:
                        try:
                            query_name = getattr(query, 'name', 'unnamed')
                            logger.info(f"Stopping streaming query: {query_name}")
                            query.stop()
                        except Exception as e:
                            logger.warning(f"Error stopping query: {e}")
                    
                    # Give time for queries to fully stop
                    if active_queries:
                        time.sleep(2)
                except Exception as e:
                    logger.warning(f"Error stopping streaming queries: {e}")
                
                # Then stop the Spark session
                self._spark.stop()
                self._spark = None
                logger.info("Spark session stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping Spark session: {e}")
