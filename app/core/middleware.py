import logging
import re
import time
from uuid import uuid4

from fastapi import Request
from opentelemetry import trace

logger = logging.getLogger("fastship.requests")

# Letters, digits, dashes and underscores only, so a client can't break the log lines
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


async def log_requests(request: Request, call_next):
    # Code before call_next runs on the way in, code after it on the way out

    # Keep the caller's request ID if it sent a valid one, so one ID can follow a
    # request through several services. Otherwise make a new one
    request_id = request.headers.get("X-Request-ID", "")
    if not REQUEST_ID_PATTERN.match(request_id):
        request_id = uuid4().hex
    # request.state is shared with routes and exception handlers for this request
    request.state.request_id = request_id
    trace.get_current_span().set_attribute("request_id", request_id)
    
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # A bug in a route: log it, then let the 500 handler answer the client
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "%s %s 500 %.1fms id=%s",
            request.method,
            request.url.path,
            duration_ms,
            request_id,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    # Standard header, browsers show it in DevTools > Network > Timing
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"

    # Only the path: query strings and headers can contain tokens or personal data
    logger.info(
        "%s %s %s %.1fms id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response
