from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Response
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
)
from scalar_fastapi import get_scalar_api_reference

from app.api.router import master_router
from app.core.exceptions import add_exception_handlers
from app.utils import APP_DIR


@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    yield

# FastAPI App
app = FastAPI(
    # Server start/stop listener
    lifespan=lifespan_handler,
)

app.include_router(master_router)
add_exception_handlers(app)


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
        title="Scalar API",
    )
