"""
Abstract base connector for all data source types.
Provides standardized interface for data ingestion.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging


class ConnectorStatus(Enum):
    """Connector status enumeration."""
    INACTIVE = "inactive"
    CONNECTING = "connecting" 
    ACTIVE = "active"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class DataMessage:
    """Standard data message format from any connector."""
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    source_id: str
    timestamp: str
    raw_payload: Optional[str] = None


@dataclass
class ConnectorHealthResponse:
    """Standardized health response for all data connectors."""
    # Core status fields - required for all connectors
    status: str                    # ConnectorStatus enum value
    healthy: bool                  # Overall health indicator (includes connectivity status)
    running: bool                  # Whether connector is actively running
    
    # Optional common fields
    last_successful_operation: Optional[str] = None  # ISO timestamp of last successful operation
    error: Optional[str] = None                      # Current error message if any
    
    # Connector-specific fields (will vary by connector type)
    connection_details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "status": self.status,
            "healthy": self.healthy,
            "running": self.running
        }
        
        # Add optional fields if they have values
        if self.last_successful_operation:
            result["last_successful_operation"] = self.last_successful_operation
        if self.error:
            result["error"] = self.error
        if self.connection_details:
            result.update(self.connection_details)
            
        return result
    
    @classmethod
    def create_error_response(cls, error_message: str, status: str = "error") -> "ConnectorHealthResponse":
        """Create a standardized error response."""
        return cls(
            status=status,
            healthy=False,
            running=False,
            error=error_message
        )
    
    @classmethod
    def create_healthy_response(cls, status: str = "active", **connection_details) -> "ConnectorHealthResponse":
        """Create a standardized healthy response."""
        return cls(
            status=status,
            healthy=True,
            running=True,
            connection_details=connection_details if connection_details else None
        )


class BaseDataConnector(ABC):
    """Abstract base class for all data source connectors."""
    
    def __init__(self, source_id: str, config: Dict[str, Any], 
                 data_handler: Callable[[DataMessage], None]):
        self.source_id = source_id
        self.config = config
        self.data_handler = data_handler
        self.status = ConnectorStatus.INACTIVE
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{source_id}")
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.last_error: Optional[str] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the data source. Returns True if successful."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the data source."""
        pass
    
    @abstractmethod
    async def start_ingestion(self) -> None:
        """Start the data ingestion process."""
        pass
    
    @abstractmethod
    async def stop_ingestion(self) -> None:
        """Stop the data ingestion process."""
        pass
    
    @abstractmethod
    async def health_check(self) -> ConnectorHealthResponse:
        """Return connector health status using standardized response model."""
        pass
    
    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return JSON schema for connector configuration validation."""
        pass
    
    @classmethod
    @abstractmethod
    def get_display_info(cls) -> Dict[str, Any]:
        """Return connector display information for UI."""
        pass
    
    # Common lifecycle methods
    async def start(self) -> bool:
        """Start the connector (connect + begin ingestion)."""
        try:
            self.logger.info("🔌 Starting connector...")
            self.status = ConnectorStatus.CONNECTING
            
            if await self.connect():
                self.status = ConnectorStatus.ACTIVE
                self._running = True
                self._task = asyncio.create_task(self._ingestion_loop())
                self.logger.info("✅ Connector started successfully")
                return True
            else:
                self.status = ConnectorStatus.ERROR
                self.logger.error("❌ Failed to connect")
                return False
        except Exception as e:
            self.logger.error(f"❌ Failed to start connector: {e}")
            self.status = ConnectorStatus.ERROR
            return False
    
    async def stop(self) -> None:
        """Stop the connector."""
        self.logger.info("🛑 Stopping connector...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        await self.disconnect()
        self.status = ConnectorStatus.STOPPED
        self.logger.info("✅ Connector stopped successfully")
    
    async def _ingestion_loop(self) -> None:
        """Internal ingestion loop - calls start_ingestion."""
        try:
            await self.start_ingestion()
        except asyncio.CancelledError:
            self.logger.info("🔍 Ingestion loop cancelled")
        except Exception as e:
            self.logger.error(f"❌ Ingestion loop error: {e}")
            self.status = ConnectorStatus.ERROR
        finally:
            self._running = False
    
    def _emit_data(self, message: DataMessage) -> None:
        """Emit processed data to the data handler."""
        try:
            self.data_handler(message)
        except Exception as e:
            self.logger.error(f"❌ Data handler error: {e}")
    
    def is_running(self) -> bool:
        """Check if connector is currently running."""
        return self._running and self.status == ConnectorStatus.ACTIVE
