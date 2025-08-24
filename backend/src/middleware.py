import logging
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .logging_config import set_request_id

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id: str = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(req_id)
        start: float = time.perf_counter()
        try:
            response: Response = await call_next(request)
        finally:
            duration_ms: float = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s -> %s in %.1fms",
                request.method,
                request.url.path,
                getattr(request.state, "status_code", "-"),
                duration_ms,
            )
        response.headers["X-Request-ID"] = req_id
        return response
