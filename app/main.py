from contextlib import asynccontextmanager

from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference

from app.api.router import master_router



@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    yield

# FastAPI App
app = FastAPI(
    # Server start/stop listener
    lifespan=lifespan_handler,
)

app.include_router(master_router)


### Scalar API Documentation
@app.get("/scalar", include_in_schema=False)
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API",
    )
