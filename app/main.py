from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
)
from scalar_fastapi import get_scalar_api_reference

from app.api.docs import DESCRIPTION, TAGS_METADATA, operation_id
from app.api.router import master_router
from app.config import app_settings
from app.core.exceptions import add_exception_handlers
from app.core.log_config import setup_logging
from app.core.middleware import log_requests
from app.utils import APP_DIR


@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    yield

# FastAPI App
app = FastAPI(
    title="FastShip API",
    summary="Shipment delivery for sellers and delivery partners",
    description=DESCRIPTION,
    # The API's own version, change it when the API changes
    version="0.1.0",
    terms_of_service="https://fastship.example.com/terms",
    contact={
        "name": "FastShip Support",
        "url": "https://fastship.example.com/support",
        "email": "support@fastship.example.com",
    },
    openapi_tags=TAGS_METADATA,
    generate_unique_id_function=operation_id,
    # We use Scalar at /scalar, so ReDoc isn't needed. Swagger stays at /docs
    redoc_url=None,
    # Server start/stop listener
    lifespan=lifespan_handler,
)


app.include_router(master_router)
add_exception_handlers(app)

setup_logging()

# The LAST middleware added runs FIRST on each request (it wraps the others)

# Lets browser apps on these origins call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    # Response headers that browser JavaScript is allowed to read
    expose_headers=["X-Request-ID", "Server-Timing"],
    # We send tokens in the Authorization header, not cookies, so no credentials
    allow_credentials=False,
    # Browsers may cache the preflight answer for 10 minutes
    max_age=600,
)

# Compress responses bigger than 1 KB for clients that support gzip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Added last, so it runs first and times everything, including CORS and GZip
app.middleware("http")(log_requests)


@app.get(
    "/time",
    response_class=JSONResponse,
)
def get_current_time():
    return {
        "timestamp": datetime.now(),
    }

@app.get(
    "/file",
    response_class=FileResponse,
)
def get_file():
    return APP_DIR/"path/to/file"  # as Path

@app.get("/timenow", response_class=RedirectResponse)
def get_time_now():
    return "/utcnow"

@app.get("/utcnow")
def get_utc_time():
    return {"timestamp": datetime.now(UTC)}

class UpperResponse(Response):
    # Initialize the default response attributes
    def __init__(
        self,
        content=None,
        status_code=200,
        headers=None,
        media_type=None,
        background=None,
    ):
        super().__init__(content, status_code, headers, media_type, background)

    # Render the response and make changes to the content as needed
    def render(self, content):
        content = content.upper()
        return super().render(content)
    
@app.get(
    "/custom",
    response_class=UpperResponse,
)
def get_custom_response():
    return "be bold!"

    
### Scalar API Documentation
@app.get("/scalar", include_in_schema=False)
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )
