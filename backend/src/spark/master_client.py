"""
Spark Master API client for retrieving cluster status information.
"""
import logging
import requests
from typing import Dict, Any

from .config import SparkConfig
from .spark_models import SparkMasterStatus

logger = logging.getLogger(__name__)


class SparkMasterClient:
    """Client for interacting with Spark Master web UI API."""
    
    def __init__(self, spark_host: str):
        """Initialize SparkMasterClient."""
        self.spark_master_url = f"http://{spark_host}:8080"
    
    def get_spark_master_status(self) -> Dict[str, Any]:
        """Fetch Spark master status from the web UI API."""
        try:
            response = requests.get(
                f"{self.spark_master_url}/json/", 
                timeout=SparkConfig.SPARK_MASTER_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse using the SparkMasterStatus model
            master_status = SparkMasterStatus.from_dict(data)
            
            return {
                "status": "success",
                "data": master_status
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Spark master status: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect to Spark master: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error parsing Spark master status: {e}")
            return {
                "status": "error",
                "message": f"Error processing Spark master response: {str(e)}"
            }
