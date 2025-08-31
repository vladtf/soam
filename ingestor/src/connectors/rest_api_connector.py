"""
REST API data source connector with polling support.
Supports various authentication methods and data extraction patterns.
"""
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from .base import BaseDataConnector, DataMessage, ConnectorStatus


class RestApiConnector(BaseDataConnector):
    """REST API data source connector with polling support."""
    
    def __init__(self, source_id: str, config: Dict[str, Any], data_handler):
        super().__init__(source_id, config, data_handler)
        self.session: Optional[aiohttp.ClientSession] = None
        self.poll_interval = config.get("poll_interval", 60)  # seconds
        self._last_success: Optional[str] = None
    
    async def connect(self) -> bool:
        """Initialize HTTP session."""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            
            # Setup headers
            headers = self.config.get("headers", {})
            auth_type = self.config.get("auth_type", "none")
            
            if auth_type == "bearer" and self.config.get("auth_token"):
                headers["Authorization"] = f"Bearer {self.config['auth_token']}"
            elif auth_type == "api_key" and self.config.get("auth_token"):
                api_key_header = self.config.get("api_key_header", "X-API-Key")
                headers[api_key_header] = self.config["auth_token"]
            
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
            
            # Test connection with a health check
            if await self._test_connection():
                self.logger.info("✅ REST API connector connected successfully")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"❌ REST API connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            self.logger.info("🔌 REST API session closed")
    
    async def start_ingestion(self) -> None:
        """Start polling REST API for data."""
        self.logger.info(f"🔍 Starting REST API polling (interval: {self.poll_interval}s)")
        
        while self._running:
            try:
                await self._fetch_data()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error during REST API polling: {e}")
                await asyncio.sleep(min(self.poll_interval, 30))  # Error backoff
    
    async def stop_ingestion(self) -> None:
        """Stop REST API polling."""
        pass  # Handled by the ingestion loop
    
    async def health_check(self) -> Dict[str, Any]:
        """REST API connector health check."""
        try:
            is_healthy = await self._test_connection() if self.session else False
            return {
                "status": self.status.value,
                "endpoint": self.config.get("url"),
                "method": self.config.get("method", "GET").upper(),
                "poll_interval": self.poll_interval,
                "last_successful_poll": self._last_success,
                "healthy": is_healthy,
                "running": self._running
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "healthy": False,
                "running": False
            }
    
    async def _test_connection(self) -> bool:
        """Test if the REST API is accessible."""
        try:
            url = self.config["url"]
            method = self.config.get("method", "GET").upper()
            
            if method == "GET":
                async with self.session.get(url) as response:
                    is_ok = response.status < 400
                    if not is_ok:
                        self.logger.warning(f"⚠️ Health check returned HTTP {response.status}")
                    return is_ok
            else:
                # For other methods, we might need to be more careful
                return True  # Assume OK for now
                
        except Exception as e:
            self.logger.error(f"❌ REST API test connection failed: {e}")
            return False
    
    async def _fetch_data(self) -> None:
        """Fetch data from REST API and emit it."""
        try:
            url = self.config["url"]
            method = self.config.get("method", "GET").upper()
            params = self.config.get("params", {})
            
            # Handle POST data if provided
            data = None
            if method == "POST" and self.config.get("body"):
                data = json.dumps(self.config["body"]) if isinstance(self.config["body"], dict) else self.config["body"]
            
            self.logger.debug(f"🔍 Fetching data from {method} {url}")
            
            async with self.session.request(method, url, params=params, data=data) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    self.logger.error(f"❌ HTTP {response.status}: {error_text}")
                    return
                
                content_type = response.headers.get('content-type', '').lower()
                
                if 'application/json' in content_type:
                    response_data = await response.json()
                else:
                    text_data = await response.text()
                    try:
                        response_data = json.loads(text_data)
                    except json.JSONDecodeError:
                        # Handle as plain text
                        response_data = {"content": text_data, "content_type": content_type}
                
                # Handle different response structures
                records = self._extract_records(response_data)
                
                for record in records:
                    message = DataMessage(
                        data=record,
                        metadata={
                            "source_url": url,
                            "http_status": response.status,
                            "content_type": content_type,
                            "source_type": "rest_api",
                            "fetch_timestamp": datetime.utcnow().isoformat(),
                            "method": method
                        },
                        source_id=self.source_id,
                        timestamp=record.get("timestamp") if isinstance(record, dict) else datetime.now(timezone.utc).isoformat(),
                        raw_payload=json.dumps(record) if isinstance(record, dict) else str(record)
                    )
                    
                    self._emit_data(message)
                
                self._last_success = datetime.now(timezone.utc).isoformat()
                self.logger.debug(f"✅ Successfully processed {len(records)} records from REST API")
                
        except Exception as e:
            self.logger.error(f"❌ Error fetching REST API data: {e}")
    
    def _extract_records(self, data: Any) -> List[Dict[str, Any]]:
        """Extract individual records from API response."""
        data_path = self.config.get("data_path", "")
        
        if not data_path:
            # If no path specified, treat entire response as single record or array
            if isinstance(data, list):
                return data
            else:
                return [data]
        
        # Navigate nested structure using dot notation (e.g., "data.items")
        current = data
        for key in data_path.split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit():
                # Support array indexing like "items.0.data"
                index = int(key)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    self.logger.warning(f"⚠️ Array index {key} out of range in path '{data_path}'")
                    return [data]  # Return original data as fallback
            else:
                self.logger.warning(f"⚠️ Data path '{data_path}' not found in response")
                return [data]  # Return original data as fallback
        
        # Ensure result is a list
        if isinstance(current, list):
            return current
        else:
            return [current]
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return configuration schema for REST API connector."""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "REST API endpoint URL"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "default": "GET",
                    "description": "HTTP method to use"
                },
                "poll_interval": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 3600,
                    "default": 60,
                    "description": "Polling interval in seconds"
                },
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Additional HTTP headers to include"
                },
                "params": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Query parameters to include"
                },
                "body": {
                    "type": "object",
                    "description": "Request body for POST requests"
                },
                "data_path": {
                    "type": "string",
                    "description": "JSONPath to extract data records (e.g., 'data.items')"
                },
                "auth_type": {
                    "type": "string",
                    "enum": ["none", "bearer", "api_key", "basic"],
                    "default": "none",
                    "description": "Authentication type"
                },
                "auth_token": {
                    "type": "string",
                    "description": "Authentication token/API key"
                },
                "api_key_header": {
                    "type": "string",
                    "default": "X-API-Key",
                    "description": "Header name for API key authentication"
                }
            },
            "required": ["url"]
        }
    
    @classmethod
    def get_display_info(cls) -> Dict[str, Any]:
        """Return display information for REST API connector."""
        return {
            "name": "REST API",
            "description": "Poll REST APIs for periodic data ingestion",
            "icon": "🌐",
            "category": "Web Services",
            "supported_formats": ["JSON", "XML", "Plain Text"],
            "real_time": False
        }
