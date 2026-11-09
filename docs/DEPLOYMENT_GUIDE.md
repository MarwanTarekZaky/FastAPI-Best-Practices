# FastShip: Pagination, Docker, Render, Telemetry and AWS

A step-by-step guide. You type every change yourself; each step says **what** to do and **why**.
Every file and command here was built and run in a copy of your project first (see Part 11 for exactly what was tested, and what could not be).

## What you will build

```
Part 1   Pagination and sorting       GET /seller/shipments?limit=20&offset=40&sort_by=weight
Part 2   Make the app container-ready   ENVIRONMENT setting, logs on stdout, /health, requirements split
Part 3   Your first Docker image        Dockerfile, .dockerignore, build, tag, run, a fat vs slim image
Part 4   A bridge network by hand       API + Postgres + Redis containers that find each other by name
Part 5   Docker Compose                 db, redis, rabbitmq, migrate, api, worker, beat with one command
Part 6   The React app in a container   multi-stage build: Node builds it, nginx serves it
Part 7   Docker Hub                     a multi-platform image (your Mac is ARM, Render is Intel/AMD)
Part 8   Render (free)                  Postgres, Key Value (Redis), migrations, pgAdmin, the API from
                                        your Docker Hub image, the frontend as a static site, logs
Part 9   Telemetry                      OpenTelemetry + Logfire: traces, SQL spans, logs, API -> worker
Part 10  AWS, only the free parts       IAM, ECR, API Gateway (import OpenAPI, integrations, throttling,
                                        caching), and why App Runner is not in this guide
Parts 11-14                             What was tested, best practices, interview questions, next steps
```

This is how the pieces fit together at the end:

```
                         Your Mac (Docker Compose)
  browser ──► web (nginx :8080) ──/api──► api (FastAPI :8000) ──► db (Postgres 18)
                                              │      │
                                              │      └──► redis (tokens, codes, task results)
                                              └──► rabbitmq ──► worker (Celery) ──► Gmail
                                                                beat (daily task)

                         The internet (free)
  browser ──► Render static site (React)
          └─► Render web service (your Docker Hub image) ──► Render Postgres, Render Key Value
          └─► AWS API Gateway (rate limits, cache) ──────────► the same Render web service
  api, worker ──► Logfire (traces and logs, a website to read them)
```

## Before you start

1. **The frontend guide is done and pushed** (your commit `f580584`). This guide builds on it: Part 1 changes endpoints that `docs/FRONTEND_GUIDE.md` Part 1 added, and Part 8 deploys `frontend/` from GitHub. While testing, your frontend code built cleanly inside Docker (`tsc -b && vite build`) and its login and dashboard worked in Chrome.
2. **The images are already on your Mac.** I pulled these while testing, so your builds won't download them again: `python:3.14`, `python:3.14-slim`, `postgres:18-alpine`, `redis:8-alpine`, `rabbitmq:4-management-alpine`, `node:26-alpine`, `nginx:1.29-alpine`. Check with `docker images`.
3. **Docker Desktop must be running** (the whale icon in the menu bar). Your `docker` command comes from Rancher Desktop's folder, but it talks to Docker Desktop; that's fine, `docker context ls` shows `desktop-linux *`.
4. **Stop `fastapi dev` before you run containers on port 8000** (Ctrl+C in its terminal). macOS lets both listen on port 8000 at the same time, and then `localhost:8000` can reach the wrong one. Your Homebrew Postgres, Redis and RabbitMQ can keep running, the containers don't use their ports.
5. **Never paste secrets into chat**, the same rule as before. Commands below that need a password read it without showing it.

---

# Part 1: Pagination and sorting

## 1.1 Why

`GET /seller/shipments` returns **every** shipment of the seller. With 20 shipments that's fine. With 20,000 the response is megabytes, the database reads every row, and the browser freezes drawing a huge table. **Pagination** returns one page at a time.

There are two common styles:

| Style | Request | Good | Bad |
|---|---|---|---|
| **Offset** (we use this) | `?limit=20&offset=40` = "skip 40, give me 20" (page 3) | Simple, can jump to any page | The database still walks past the skipped rows, slow at offset 1,000,000 |
| **Cursor / keyset** | `?limit=20&after=<last id>` | Fast at any depth | Only "next page", no "jump to page 50" |

Offset is right for dashboards like ours. Cursor pagination is for infinite feeds (Twitter, logs).

**Where does the total go?** Two common designs:

- An envelope body: `{"items": [...], "total": 312, "limit": 20, "offset": 0}`
- The body stays a list, the total goes in a header: `X-Total-Count: 312` (GitHub's API works this way)

We use the **header**, because you asked not to touch the frontend yet: the body stays a list, so the React app keeps working unchanged. It simply gets the first page (50 by default). When we learn React, the dashboard will read `X-Total-Count` and show page buttons.

**Sorting** (`sort_by` + `order`) lets the user choose: newest first, delivery date, or heaviest first.

## 1.2 The query parameters, as one model

Open `app/api/schemas/shipment.py`. At the top, add the `StrEnum` import:

```python
from datetime import datetime
from enum import StrEnum
from uuid import UUID
```

At the **end** of the file, add:

```python
class ShipmentSort(StrEnum):
    created_at = "created_at"
    estimated_delivery = "estimated_delivery"
    weight = "weight"


class SortOrder(StrEnum):
    asc = "asc"
    desc = "desc"


class ShipmentListParams(BaseModel):
    """Which page of shipments to return, and in what order"""

    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="How many shipments to return, at most 100",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="How many to skip. Page 3 of 20 per page is offset=40",
    )
    sort_by: ShipmentSort = Field(
        default=ShipmentSort.created_at,
        description="The field to sort by",
    )
    order: SortOrder = Field(
        default=SortOrder.desc,
        description="`desc` is newest, latest or heaviest first",
    )
```

Why:
- **An enum for `sort_by`**, not a free string. If any string were allowed, someone could send `sort_by=password_hash` and learn things from the order. With an enum, FastAPI answers 422 for anything not in the list, before our code runs.
- **`le=100`** caps the page size. Without a cap, `?limit=1000000` brings back the "huge response" problem.
- **A Pydantic model for query parameters** (FastAPI calls it a *query parameter model*). The three endpoints share the same four parameters, so they're defined once. In the route we'll write `Annotated[ShipmentListParams, Query()]`: `Query()` tells FastAPI to fill the model from the query string, not the body.
- `StrEnum` (Python 3.11+) members are real strings, so they compare and print as `"weight"`.

## 1.3 One helper that paginates any shipment query

Create `app/services/pagination.py`:

```python
from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.schemas.shipment import ShipmentListParams, ShipmentSort, SortOrder
from app.database.models import Shipment

# Which column each sort option uses
SORT_COLUMNS = {
    ShipmentSort.created_at: col(Shipment.created_at),
    ShipmentSort.estimated_delivery: col(Shipment.estimated_delivery),
    ShipmentSort.weight: col(Shipment.weight),
}


async def paginate_shipments(
    session: AsyncSession,
    query: Select[Shipment],
    params: ShipmentListParams,
) -> tuple[Sequence[Shipment], int]:
    # How many match in total, so the client knows how many pages there are
    total = await session.scalar(select(func.count()).select_from(query.subquery()))

    column = SORT_COLUMNS[params.sort_by]
    ordering = column.asc() if params.order == SortOrder.asc else column.desc()

    shipments = await session.scalars(
        # id breaks ties: rows with the same weight must keep the same order
        # on every page, or one could show up twice and another never
        query.order_by(ordering, col(Shipment.id))
        .limit(params.limit)
        .offset(params.offset)
    )
    return shipments.all(), total or 0
```

Why each part:
- **`select(func.count()).select_from(query.subquery())`** counts the rows of *the same query* (same filters, same joins) before LIMIT. That's the total for `X-Total-Count`. It's one extra small query per request, the usual price of showing "page 3 of 16".
- **`SORT_COLUMNS`** maps each enum value to a real column. Only these three can ever reach `ORDER BY`.
- **`col(Shipment.id)` as a second sort key, the tie-breaker.** Postgres doesn't promise any order between rows with the same value. Two shipments of 2.5 kg could swap places between page 1 and page 2, then one shows twice and the other never. Sorting by a unique column at the end makes the order stable. This is a classic pagination bug, and an interview favorite.
- It takes a `Select` and returns `(shipments, total)`: the seller, partner and tag endpoints each build their own `WHERE` and reuse it. It lives in its own module because `tag.py` can't import from `shipment.py` (`shipment.py` already imports `tag.py`, that would be a circular import).

## 1.4 The services use it

In `app/services/shipment.py`, change the schema import:

```python
from app.api.schemas.shipment import (
    ShipmentCreate,
    ShipmentListParams,
    ShipmentUpdate,
)
```

Add the helper import next to the other local imports:

```python
from .base import BaseService
from .delivery_partner import DeliveryPartnerService
from .pagination import paginate_shipments
from .tag import TagService
```

Replace `get_by_seller` and `get_by_partner` with:

```python
    async def get_by_seller(
        self, seller: Seller, params: ShipmentListParams
    ) -> tuple[Sequence[Shipment], int]:
        return await paginate_shipments(
            self.session,
            select(Shipment).where(col(Shipment.seller_id) == seller.id),
            params,
        )

    async def get_by_partner(
        self, partner: DeliveryPartner, params: ShipmentListParams
    ) -> tuple[Sequence[Shipment], int]:
        return await paginate_shipments(
            self.session,
            select(Shipment).where(col(Shipment.delivery_partner_id) == partner.id),
            params,
        )
```

The `.order_by(...)` is gone from here on purpose: the helper adds the order the user asked for.

In `app/services/tag.py`, add the two imports:

```python
from app.api.schemas.shipment import ShipmentListParams
from app.core.exceptions import EntityNotFound
from app.database.models import Seller, Shipment, Tag, TagName

from .base import BaseService
from .pagination import paginate_shipments
```

and replace `get_shipments` with:

```python
    async def get_shipments(
        self, name: TagName, seller: Seller, params: ShipmentListParams
    ) -> tuple[Sequence[Shipment], int]:
        # JOIN through the link table: shipment -> shipment_tag -> tag.
        # Only the seller's own shipments
        return await paginate_shipments(
            self.session,
            select(Shipment)
            .join(Shipment.tags)  # type: ignore[arg-type]
            .where(col(Tag.name) == name, col(Shipment.seller_id) == seller.id),
            params,
        )
```

## 1.5 Document the header

In `app/api/docs.py`, under the `errors()` function, add:

```python
# For endpoints that return one page of a list: documents the header that says
# how many results there are on all pages together
TOTAL_COUNT: dict[int | str, dict[str, Any]] = {
    200: {
        "headers": {
            "X-Total-Count": {
                "description": "How many results match, on all pages together",
                "schema": {"type": "integer"},
            },
        },
    },
}
```

Why: Scalar and `/docs` read the OpenAPI document. Without this, nobody reading the docs would know the header exists. FastAPI merges this `200` entry with the normal success response, so the response schema stays.

## 1.6 The three endpoints

In `app/api/routers/seller.py`, change two imports:

```python
from fastapi import APIRouter, Depends, Query, Response, status
```

```python
from ..docs import TOTAL_COUNT, errors
from ..schemas.common import Message, Token
from ..schemas.seller import SellerCreate, SellerRead
from ..schemas.shipment import ShipmentListParams, ShipmentRead
```

and replace the `/shipments` endpoint:

```python
@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="My shipments",
    responses={**TOTAL_COUNT, **errors(401)},
)
async def get_seller_shipments(
    seller: SellerDep,
    service: ShipmentServiceDep,
    params: Annotated[ShipmentListParams, Query()],
    response: Response,
):
    """One page of the logged in seller's shipments, newest first by default."""
    shipments, total = await service.get_by_seller(seller, params)
    response.headers["X-Total-Count"] = str(total)
    return shipments
```

Why:
- **`response: Response`**: FastAPI gives you the response *before* it's sent. Headers you set on it are kept, while the body still comes from what you `return` (validated by `response_model`).
- **`str(total)`**: header values are always text.
- **`{**TOTAL_COUNT, **errors(401)}`** merges the two dicts into one `responses` dict.

Do the same in `app/api/routers/delivery_partner.py`. Imports:

```python
from fastapi import APIRouter, Depends, Query, Response, status
```

```python
from ..docs import TOTAL_COUNT, errors
```

```python
from ..schemas.shipment import ShipmentListParams, ShipmentRead
```

and the endpoint:

```python
@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="My assigned shipments",
    responses={**TOTAL_COUNT, **errors(401)},
)
async def get_partner_shipments(
    partner: DeliveryPartnerDep,
    service: ShipmentServiceDep,
    params: Annotated[ShipmentListParams, Query()],
    response: Response,
):
    """One page of the shipments assigned to the logged in partner."""
    shipments, total = await service.get_by_partner(partner, params)
    response.headers["X-Total-Count"] = str(total)
    return shipments
```

And `app/api/routers/tag.py`. The imports at the top become:

```python
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.database.models import TagName

from ..dependencies import SellerDep, TagServiceDep
from ..docs import TOTAL_COUNT, errors
from ..schemas.shipment import ShipmentListParams, ShipmentRead, TagRead
```

and the endpoint:

```python
@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="My shipments with a tag",
    responses={**TOTAL_COUNT, **errors(401)},
)
async def get_shipments_by_tag(
    tag_name: TagName,
    seller: SellerDep,
    service: TagServiceDep,
    params: Annotated[ShipmentListParams, Query()],
    response: Response,
):
    """One page of the logged in seller's shipments that have this tag."""
    shipments, total = await service.get_shipments(tag_name, seller, params)
    response.headers["X-Total-Count"] = str(total)
    return shipments
```

`tag_name` is a normal query parameter next to the model, FastAPI combines them.

> **A trap I hit while testing:** a query model can have `model_config = ConfigDict(extra="forbid")` to reject unknown parameters like `?limt=5`. But then FastAPI also rejects `tag_name`, because it isn't a field of the model. So we don't use `extra="forbid"`; unknown query parameters are ignored, as everywhere else in the API.

## 1.7 Let browser JavaScript read the header

In `app/main.py`, in the `CORSMiddleware` block:

```python
    expose_headers=["X-Request-ID", "Server-Timing", "X-Total-Count"],
```

Why: when the frontend runs on another domain (Part 8: `fastship-web.onrender.com` calling `fastship-api.onrender.com`), the browser hides every response header from JavaScript except a few basic ones, unless the server lists it in `Access-Control-Expose-Headers`.

## 1.8 The hidden cost pagination can't fix

While testing pagination, I measured how many database rows one request reads, with a seller who has 500 shipments:

| Request | Rows read before | Rows read after the change below |
|---|---|---|
| `GET /seller/me` | **1,502** | **1** |
| `GET /seller/shipments?limit=10` | **1,535** | **34** |

Even `/seller/me` read 1,502 rows. The cause is in `app/database/models.py`:

```python
class Seller(User, table=True):
    ...
    shipments: list[Shipment] = Relationship(
        back_populates="seller",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
```

`lazy="selectin"` means *"every time a Seller is loaded, also load all of its shipments"*. And each shipment loads its `timeline` and `tags` the same way. `get_current_seller` loads the seller on **every** request, so every request read the seller's whole history, and `LIMIT 10` could not help.

Nothing in the app reads `seller.shipments` (the paged query replaces it), so change it to:

```python
    shipments: list[Shipment] = Relationship(
        back_populates="seller",
        # Never load every shipment of the seller on each request, use the paged
        # GET /seller/shipments query instead. "raise" makes any access an error
        sa_relationship_kwargs={"lazy": "raise"},
    )
```

`lazy="raise"` doesn't load anything, and if code ever touches `seller.shipments`, SQLAlchemy raises an error instead of quietly running a big query. Loud beats slow-and-silent. This is a mapping change only, the table doesn't change, so **no migration** is needed (`alembic check` says "No new upgrade operations detected").

> **Not fixed in this guide: the partner side has the same problem** (`GET /partner/me` also read 1,502 rows). `DeliveryPartner.shipments` *is* used: `current_handling_capacity` counts the active shipments in Python. The fix is to count them with SQL instead (`SELECT count(*) ... WHERE` the newest event isn't delivered/cancelled), which changes the assignment logic and its tests. That's a good next exercise; I left it out so this guide stays about pagination.

## 1.9 Tests

Create `tests/api/test_pagination.py`:

```python
import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.delivery_partner import DeliveryPartnerCreate
from app.main import app
from app.services.delivery_partner import DeliveryPartnerService
from tests.helpers import PASSWORD, ZIP_CODE, login


def ids(response: Response) -> list[str]:
    return [shipment["id"] for shipment in response.json()]


@pytest.fixture
async def three_shipments(
    client: AsyncClient,
    session: AsyncSession,
    seller_headers: dict[str, str],
    shipment_data: dict,
) -> list[dict]:
    # The partner fixture only has room for 2, this one takes all three
    await DeliveryPartnerService(session).add(
        DeliveryPartnerCreate(
            name="Partner",
            email="partner@example.com",
            password=PASSWORD,
            serviceable_zip_codes=[ZIP_CODE],
            max_handling_capacity=10,
        )
    )
    created = []
    for weight in (2.0, 9.0, 5.0):
        response = await client.post(
            "/shipment/", json={**shipment_data, "weight": weight}, headers=seller_headers
        )
        created.append(response.json())
    # Oldest first
    return created


async def test_first_page(client: AsyncClient, seller_headers, three_shipments):
    response = await client.get(
        "/seller/shipments", params={"limit": 2}, headers=seller_headers
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "3"
    # Newest first by default
    assert ids(response) == [three_shipments[2]["id"], three_shipments[1]["id"]]


async def test_next_page(client: AsyncClient, seller_headers, three_shipments):
    response = await client.get(
        "/seller/shipments", params={"limit": 2, "offset": 2}, headers=seller_headers
    )

    assert response.headers["X-Total-Count"] == "3"
    assert ids(response) == [three_shipments[0]["id"]]


async def test_sort_by_weight(client: AsyncClient, seller_headers, three_shipments):
    response = await client.get(
        "/seller/shipments",
        params={"sort_by": "weight", "order": "asc"},
        headers=seller_headers,
    )

    assert [shipment["weight"] for shipment in response.json()] == [2.0, 5.0, 9.0]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"sort_by": "password_hash"},
        {"order": "up"},
    ],
)
async def test_wrong_page_params(client: AsyncClient, seller_headers, params):
    response = await client.get(
        "/seller/shipments", params=params, headers=seller_headers
    )

    assert response.status_code == 422


async def test_partner_shipments_page(client: AsyncClient, three_shipments):
    headers = await login(client, "partner", "partner@example.com")

    response = await client.get(
        "/partner/shipments", params={"limit": 1}, headers=headers
    )

    assert response.headers["X-Total-Count"] == "3"
    assert ids(response) == [three_shipments[2]["id"]]


async def test_tag_shipments_page(client: AsyncClient, seller_headers, three_shipments):
    for shipment in three_shipments[:2]:
        await client.post(
            "/shipment/tag",
            params={"id": shipment["id"], "tag_name": "gift"},
            headers=seller_headers,
        )

    response = await client.get(
        "/tag/shipments",
        params={"tag_name": "gift", "limit": 1},
        headers=seller_headers,
    )

    assert response.headers["X-Total-Count"] == "2"
    assert ids(response) == [three_shipments[1]["id"]]


async def test_browsers_can_read_total_count(client: AsyncClient, seller_headers):
    # Without this CORS header, frontend JavaScript on another origin can't read it
    response = await client.get(
        "/seller/shipments",
        headers={**seller_headers, "Origin": "http://localhost:5173"},
    )

    assert "X-Total-Count" in response.headers["Access-Control-Expose-Headers"]


def test_page_params_are_documented():
    operation = app.openapi()["paths"]["/seller/shipments"]["get"]

    assert {p["name"] for p in operation["parameters"]} == {
        "limit",
        "offset",
        "sort_by",
        "order",
    }
    assert "X-Total-Count" in operation["responses"]["200"]["headers"]
```

What they prove:
- **first page / next page**: `limit` and `offset` cut the list, and the header always holds the full total (3).
- **sort by weight**: `sort_by` and `order` work.
- **wrong parameters** (`@pytest.mark.parametrize` runs one test 5 times with different inputs): 0, 101, -1, an unknown column, an unknown order → all 422.
- **partner / tag**: the other two endpoints are paged too.
- **CORS**: the header is exposed to browsers.
- **docs**: OpenAPI lists the four parameters and the header.
- The `three_shipments` fixture creates its own partner with room for 10, because the shared `partner` fixture only has room for 2.

Run everything:

```bash
pytest
ruff check app tests
```

Expected: `91 passed` (79 before + 12 new), and Ruff clean.

## 1.10 Try it

`fastapi dev`, open http://localhost:8000/scalar, log in as a seller, then open **My shipments**. Scalar now shows `limit`, `offset`, `sort_by` (a dropdown) and `order`. Send `limit=2&sort_by=weight&order=asc` and look at the response headers: `x-total-count`.

Then **stop `fastapi dev`** (Ctrl+C) before Part 3.

---
# Part 2: Make the app container-ready

A container is a fresh, throwaway copy of your app. Deployments (Render, AWS) start and stop it whenever they want. That changes a few habits, and they're known as the **Twelve-Factor App** rules:

- **Settings come from environment variables**, not from files baked into the image. (Our `pydantic-settings` already reads environment variables first, then `.env`.)
- **Logs go to stdout** (the terminal). The platform collects them; files inside a container disappear with it.
- **No local state.** Anything written to the container's disk is lost on the next deploy.
- **A health check URL** so the platform knows the app is alive.
- **Dev tools stay out of production.**

## 2.1 An ENVIRONMENT setting

In `app/config.py`, add the import at the top:

```python
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
```

and the setting as the first field of `AppSettings`:

```python
class AppSettings(BaseSettings):
    # "production" turns off what is only meant for your own machine,
    # like printing every SQL query and writing logs/requests.log
    ENVIRONMENT: Literal["development", "production"] = "development"
```

Why `Literal`: only these two values are accepted. A typo like `ENVIRONMENT=prod` fails at startup with a clear error, instead of quietly running in development mode in production.

**Don't add `ENVIRONMENT` to your `.env`.** On your Mac the default (`development`) is right. The Docker image sets `production` itself (Part 3).

## 2.2 Print SQL only while developing

In `app/database/session.py`:

```python
from app.config import app_settings, db_settings

# Create a database engine to connect with database
engine = create_async_engine(
    url=db_settings.POSTGRES_URL,
    # Print every SQL query while developing. In production it's too much noise,
    # and the queries can contain personal data
    echo=app_settings.ENVIRONMENT == "development",
)
```

`echo=True` prints each query and its values (`('client@example.com',)`). Useful on your Mac, but on Render it would flood the logs with emails and phone numbers.

## 2.3 Logs on stdout

Replace all of `app/core/log_config.py` with:

```python
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import app_settings

# logs/ folder in the project root
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging():
    # Docker and hosting sites like Render collect what an app prints to the
    # terminal (stdout), that's where logs belong in a container
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(FORMAT))

    # "app" is the parent of every module logger in app/, like
    # app.services.notification, so they all print with the same format
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    # Don't add a second handler if this runs twice
    if not app_logger.handlers:
        app_logger.addHandler(console)
    app_logger.propagate = False

    requests_logger = logging.getLogger("fastship.requests")
    requests_logger.setLevel(logging.INFO)
    requests_logger.propagate = False
    if requests_logger.handlers:
        return

    if app_settings.ENVIRONMENT == "production":
        # A file inside a container is lost on every restart, print instead
        requests_logger.addHandler(console)
        return

    # On your machine: uvicorn already prints each request in the terminal,
    # keep these in a file. A new file starts at 1 MB, keeping the last 3
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / "requests.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(FORMAT))
    requests_logger.addHandler(file_handler)
```

Why:
- **`StreamHandler(sys.stdout)`** prints to the terminal. `docker logs`, `docker compose logs` and Render's Logs page all show exactly what the process prints.
- **The `"app"` logger** is the parent of every logger named `app.something`. `logging.getLogger(__name__)` in `app/services/notification.py` is called `app.services.notification`, so it uses this handler too. Before this change, its "Could not queue" errors had no handler and only reached the terminal through Python's last-resort fallback, without a time or level.
- **`propagate = False`** stops the line from also going to the root logger, which would print it twice.
- **The request log**: in production, to stdout (a file would be lost); in development, still to `logs/requests.log` as before, because uvicorn already prints each request in your terminal.
- **`%(name)s`** in the format shows which logger wrote the line, e.g. `app.services.notification`.

## 2.4 A health check endpoint

In `app/main.py`, just above `### Scalar API Documentation`, add:

```python
# Docker, Render and load balancers call this to check the app is running.
# Kept out of the docs, it's not part of the API
@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}
```

Why: Compose waits for it before starting the frontend, Render calls it after each deploy and only switches traffic to the new version once it answers 200, and AWS load balancers do the same. It doesn't touch the database on purpose: it answers "is the process alive?", and a slow database shouldn't make the platform restart the app over and over.

## 2.5 Production vs development requirements

`requirements.txt` came from `pip freeze`, so it also contains pytest, ruff, fakeredis... The image only needs what the app runs with. We split it:

- `requirements.txt`: what the app needs to run. The Docker image installs this.
- `requirements-dev.txt`: `-r requirements.txt` (meaning "everything in that file") plus the tools. Your Mac installs this.

These 10 lines in today's `requirements.txt` are dev-only. I found them by following the dependency tree of `[project].dependencies` in `pyproject.toml`; everything else is needed at run time:

```
coverage  fakeredis  iniconfig  pluggy  pytest  pytest-asyncio  pytest-cov
ruff  sortedcontainers  types-passlib
```

Create `requirements-dev.txt`. The pins must match your `requirements.txt` (`grep` copies them for you):

```bash
{
  printf '# The app plus the tools for tests, linting and type checks.\n# On your machine: pip install -r requirements-dev.txt\n-r requirements.txt\n'
  grep -i -E '^(coverage|fakeredis|iniconfig|pluggy|pytest|pytest-asyncio|pytest-cov|ruff|sortedcontainers|types-passlib)==' requirements.txt
} > requirements-dev.txt
cat requirements-dev.txt
```

What it does: `{ ...; } > file` writes the output of both commands into one file. `printf` writes the three header lines (`\n` is a new line). `grep -i -E '^(a|b|c)=='` prints the lines that start with one of these names followed by `==` (`-i` ignores upper/lower case, `-E` allows the `(a|b)` "or" syntax).

It should look like this (your versions):

```text
# The app plus the tools for tests, linting and type checks.
# On your machine: pip install -r requirements-dev.txt
-r requirements.txt
coverage==7.17.2
fakeredis==2.40.0
iniconfig==2.3.1
pluggy==1.7.0
pytest==9.2.0
pytest-asyncio==1.4.1.post1
pytest-cov==7.1.0
ruff==0.17.2
sortedcontainers==2.4.0
types-passlib==1.7.7.20260211
```

Now rebuild `requirements.txt` without them:

```bash
pip freeze $(grep "==" requirements-dev.txt | sed 's/==.*//; s/^/--exclude /') > requirements.txt
grep -c "==" requirements.txt
```

What it does, from the inside out:
- `grep "==" requirements-dev.txt` prints the 10 pinned lines, like `pytest==9.2.0`.
- `sed 's/==.*//; s/^/--exclude /'` turns each into `--exclude pytest`: the first rule deletes from `==` to the end, the second puts `--exclude ` at the start.
- `$( ... )` puts that output into the command line, so it runs `pip freeze --exclude coverage --exclude fakeredis ...`.
- `pip freeze --exclude X` lists everything installed except X.

Expected: about `109` (it was 119 with the dev tools). **Keep this command**: every time you `pip install` a new package for the app, run it again so `requirements.txt` stays without the dev tools. A new dev tool goes into `requirements-dev.txt` by hand.

> Tools like `uv` and `pip-tools` solve this properly with lock files (`uv pip compile`), it's a good next step. We stay with pip, like the course.

## 2.6 `.env` without quotes

Docker's `--env-file` doesn't read `.env` the way Python does: it keeps quotes as part of the value. I checked:

```
.env:                      POSTGRES_DB="fastship"
Python (pydantic) reads:   fastship
docker --env-file reads:   "fastship"     <- with the quotes, so the database name is wrong
```

Your values don't contain spaces, `#` or `$` (I checked the shape of each line without reading the values), so the quotes aren't needed anywhere. Remove them, with a backup first:

```bash
cp .env .env.backup
sed -i '' -E 's/^([A-Z_]+)="(.*)"$/\1=\2/' .env
grep -c '"' .env
```

What it does:
- `sed -i ''` edits the file in place (`''` is macOS's "no backup suffix").
- `-E 's/^([A-Z_]+)="(.*)"$/\1=\2/'` finds lines like `NAME="value"`: `([A-Z_]+)` remembers the name as `\1`, `(.*)` remembers the value as `\2`. Each line is rewritten as `\1=\2`, so `NAME=value`.
- `grep -c '"' .env` counts lines that still have a quote. Expected: `0`.

I tested this command on a copy of your `.env`: same keys, same values, no quotes left. `.env.backup` is ignored by git (the `*.env.*` rule in `.gitignore`). Delete it once Part 5 works.

Then add two new lines to `.env`, for the RabbitMQ container in Part 5. Use the same user and password as in your `CELERY_BROKER_URL` (or new ones, the container creates the user):

```bash
RABBITMQ_USER=fastship
RABBITMQ_PASSWORD=the_password_from_your_CELERY_BROKER_URL
```

And update `.env.example` (the file other people copy). It's committed, so it only has fake values:

```text
# Copy to .env and fill in. No quotes around the values:
# docker run --env-file would keep the quotes as part of the value

POSTGRES_SERVER=host_server
POSTGRES_PORT=1234
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgre_password
POSTGRES_DB=postgre_db

REDIS_HOST=redishost
REDIS_PORT=6379

JWT_SECRET=secret key
JWT_ALGORITHM=security algo

MAIL_USERNAME=your_address@gmail.com
MAIL_PASSWORD=gmail_app_password
MAIL_FROM=your_address@gmail.com
MAIL_FROM_NAME=FastShip
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_STARTTLS=True
MAIL_SSL_TLS=False
USE_CREDENTIALS=True
VALIDATE_CERTS=True


VERIFICATION_CODE_SECRET=paste_openssl_output
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_NUMBER=+1xxxxxxxxxx


CELERY_BROKER_URL=amqp://fastship:YOUR_RABBIT_PASSWORD@localhost:5672/fastship
CELERY_RESULT_BACKEND=redis://localhost:6379/dbNum
FLOWER_USER=flower User
FLOWER_PASSWORD=YOUR_FLOWER_PASSWORD

# The RabbitMQ user that docker compose creates, see compose.yaml
RABBITMQ_USER=fastship
RABBITMQ_PASSWORD=YOUR_RABBIT_PASSWORD

# Optional: the Logfire write token, without it telemetry stays on this machine
LOGFIRE_TOKEN=
```

## 2.7 Check

```bash
pip install -r requirements-dev.txt
pytest
ruff check app tests
```

Expected: `91 passed`. `pip install` does nothing new, it just proves the two files are complete.

---

# Part 3: Your first Docker image

## 3.1 The words

| Word | Meaning | In our project |
|---|---|---|
| **Image** | A read-only package: an operating system's files, Python, your packages and your code. Like a class. | `fastship-api:0.1.0` |
| **Container** | A running copy of an image, with its own processes, network and disk. Like an object made from the class. You can run many containers from one image. | the API, the worker and the migrations all run our one image |
| **Layer** | Each Dockerfile instruction adds one layer on top of the previous one. Unchanged layers come from the cache. | `pip install` is one layer |
| **Tag** | A name plus a version: `name:tag`. Without a tag Docker assumes `latest`. | `fastship-api:0.1.0` |
| **Registry** | A server that stores images. | Docker Hub (Part 7), AWS ECR (Part 10) |
| **Build context** | The folder Docker sends to the builder. `COPY` can only read files from it. | the project folder, minus `.dockerignore` |

## 3.2 First, the naive way (to see the problem)

**Optional:** this build downloads about 100 MB of Python packages. If your internet is slow, read the results table below and skip to 3.3.

Create `Dockerfile` in the project root with what most tutorials start with:

```dockerfile
FROM python:3.14
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
```

Build it:

```bash
docker build -t fastship-api:naive .
docker images fastship-api
```

- `docker build` reads `./Dockerfile`.
- `-t fastship-api:naive` names (tags) the image.
- `.` at the end is the build context: this folder.

This is what it measured on your machine (without `.dockerignore`):

| | |
|---|---|
| Build context sent to Docker | **about 750 MB**: `.venv` 267 MB, `frontend/node_modules` 386 MB, `.mypy_cache` 95 MB... |
| Image size (`docker images`) | **2.22 GB** |
| Download size (what a server pulls) | **513 MB** |
| `.env` | **inside the image**, with your Gmail App Password and Twilio token |

Four problems:
1. **`python:3.14` is a full Debian with compilers**, about 1.1 GB before your code.
2. **`COPY . .` copies everything**: your `.venv` (built for macOS, useless on Linux), `node_modules`, caches, and **`.env` with your secrets**. Anyone who gets the image can read them with `docker run fastship-api:naive cat .env`.
3. **Layer order**: code is copied before `pip install`, so changing one line of Python makes Docker reinstall every package (minutes instead of seconds).
4. **It runs as root.** A bug that lets an attacker run commands gives them full control of the container.

Delete it:

```bash
docker rmi fastship-api:naive
```

## 3.3 `.dockerignore`

Create `.dockerignore` in the project root:

```text
# What Docker must NOT send to the build. Everything else in this folder is
# the "build context" that COPY can read

# Secrets: the settings come from environment variables when the container runs
.env
*.env

# Your local environment and caches, the image installs its own packages
.venv/
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.pytest_cache/
.coverage
htmlcov/

# Not needed to run the API. The frontend has its own Dockerfile
.git/
.vscode/
frontend/
docs/
tests/
Temp/
logs/
celerybeat-schedule*
*.db
scratch*.py
```

It works like `.gitignore` but for the build context: these paths are never sent to Docker, so no `COPY` can put them in the image, even by mistake. Our Dockerfile below only copies 3 things anyway, but this file is a second safety net (defense in depth), and it makes the build start instantly: the context drops from about 750 MB to **7 KB**.

## 3.4 The real Dockerfile

Replace `Dockerfile` with:

```dockerfile
# The image for the API, the Celery worker and the migrations: one image,
# a different command for each

# Official Python image, "slim" variant: Debian with only what Python needs
FROM python:3.14-slim

# PYTHONDONTWRITEBYTECODE: don't write .pyc cache files next to the code at run time
# PYTHONUNBUFFERED: print logs right away, so `docker logs` shows them live
# PIP_NO_CACHE_DIR: pip's download cache is useless inside an image
# ENVIRONMENT: the image is for production, see app/config.py
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production

# The following commands run in /app, it's created if missing
WORKDIR /app

# Dependencies before the code: Docker reuses this layer from its cache until
# requirements.txt changes, so a code change rebuilds in seconds
COPY requirements.txt .
RUN pip install -r requirements.txt

# A user without a password or a home folder. If someone breaks into the app,
# they can't change the system files
RUN useradd --system --no-create-home fastship

# Only what the API needs at run time. Owned by root, so the app can't edit it
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

USER fastship

# Documents the port the app listens on, `docker run -p` still publishes it
EXPOSE 8000

# --forwarded-allow-ips: trust the X-Forwarded-* headers from the proxy in front
# of the app (Render, nginx, a load balancer), so it knows the visitor used https
CMD ["fastapi", "run", "app/main.py", "--port", "8000", "--forwarded-allow-ips", "*"]
```

Line by line:

| Line | What and why |
|---|---|
| `FROM python:3.14-slim` | The **slim** variant: Debian with only what Python needs, about 42 MB to download instead of 386 MB. Same Python 3.14 as your `.venv`. Not `alpine`: Alpine uses a different C library (musl), and many Python packages have no ready-made wheels for it, so pip would compile them (slow, needs compilers). |
| `ENV PYTHONDONTWRITEBYTECODE=1` | Python won't try to write `.pyc` cache files next to our code when it runs. The code folder is read-only for the app user anyway. |
| `PYTHONUNBUFFERED=1` | Python normally keeps output in a buffer and prints it in chunks. In a container you want each log line to show up right away. |
| `PIP_NO_CACHE_DIR=1` | pip normally keeps a copy of every download for next time. Inside an image there's no "next time", it would only add size. |
| `PIP_DISABLE_PIP_VERSION_CHECK=1` | No "a new pip is available" message on every build. |
| `ENVIRONMENT=production` | Every container from this image is in production mode unless told otherwise (Part 2.1). |
| `WORKDIR /app` | Like `cd /app` (and creates it). All following commands, and the running app, use this folder. |
| `COPY requirements.txt .` then `RUN pip install` | **The caching trick.** Docker reuses a layer when its instruction and the files it copies haven't changed. `requirements.txt` rarely changes, so this ~300 MB layer is reused on almost every build, and only the small code layers below are rebuilt. |
| `RUN useradd --system --no-create-home fastship` | Creates a normal user: no password, no home folder, no login. |
| `COPY alembic.ini ./` ... `COPY app ./app` | Only what's needed at run time: the code and the migrations. Not tests, not the frontend. The files belong to root, so the `fastship` user can read them but not change them. |
| `USER fastship` | Everything from here on, including the running app, runs as that user, not root. |
| `EXPOSE 8000` | Documentation for humans and tools: "this app listens on 8000". It doesn't open anything; `-p` does that. |
| `CMD [...]` | The command a container runs when it starts, unless you give another one. |

The `CMD` itself:
- **`fastapi run`** is production mode: no auto-reload, listens on `0.0.0.0` (all network interfaces). `fastapi dev` listens only on `127.0.0.1`, which can't be reached from outside the container.
- **`--forwarded-allow-ips *`**: on Render, AWS or behind nginx, the request arrives from a proxy that adds `X-Forwarded-Proto: https`. By default uvicorn only trusts that header from `127.0.0.1`, so the app thinks the visitor used plain `http`, and FastAPI's redirects (`/tag` → `/tag/`) point to `http://...`, which browsers block on an `https` page. `*` trusts the proxy. That's safe because the container is only reachable through that proxy. I tested it: with this flag, the redirect is `location: https://fastship-api.onrender.com/tag/`.

### CMD vs ENTRYPOINT

| | `CMD ["a", "b"]` | `ENTRYPOINT ["a"]` |
|---|---|---|
| Meaning | the default command | the fixed program; `CMD` becomes its default arguments |
| `docker run image something` | runs `something` **instead** | runs `a something` |

We use only `CMD` on purpose. The same image runs other commands just by naming them:

```bash
docker run ... fastship-api:0.1.0 alembic upgrade head          # migrations
docker run ... fastship-api:0.1.0 celery -A app.worker.celery_app worker   # worker
```

With `ENTRYPOINT ["fastapi"]` these would become `fastapi alembic upgrade head`, which is wrong. ENTRYPOINT is good when an image is *one* tool (an image that only runs `alembic`, for example), or for a startup script that prepares something and then runs the CMD.

### Exec form vs shell form

`CMD ["fastapi", "run"]` (a JSON list, the **exec form**) starts `fastapi` directly as the container's main process. `CMD fastapi run` (the **shell form**) starts `/bin/sh -c "fastapi run"`: then `sh` is the main process, and when Docker or Render stops the container, the stop signal goes to `sh`, which doesn't pass it on. The app is killed after 10 seconds instead of finishing its requests. Use the exec form.

## 3.5 Build it

```bash
docker build -t fastship-api:0.1.0 .
docker images fastship-api
docker history fastship-api:0.1.0
```

- The tag `0.1.0` matches `version="0.1.0"` in `app/main.py`. Each release gets a new version, so you always know which code a container runs.
- `docker history` lists the layers and their sizes: about 300 MB is `pip install` (Twilio alone is 51 MB, SQLAlchemy 29 MB), the code is about 0.5 MB.

Results on your machine:

| | naive | slim |
|---|---|---|
| `docker images` size | 2.22 GB | **572 MB** (about 650 MB after Part 9 adds telemetry) |
| Download size | 513 MB | **about 110 MB** |
| `.env` inside | yes | **no** |
| Runs as | root | **fastship** |

Change one line in `app/main.py` and build again: it finishes in a few seconds, because the `pip install` layer comes from the cache (`CACHED` in the output).

> **Why not a multi-stage build here?** Multi-stage (Part 6) helps when building needs tools the app doesn't need to run, like compilers or Node. Every package here installs from a ready-made wheel, so slim has no compilers to throw away. The frontend is different, there we save hundreds of MB.

## 3.6 Run it

```bash
docker run --rm -p 8000:8000 --env-file .env fastship-api:0.1.0
```

- `docker run IMAGE` makes a container and starts it.
- `--rm` deletes the container when it stops (no pile of old containers).
- `-p 8000:8000` is **host port : container port**. Your Mac's port 8000 forwards to the container's 8000. Without `-p` the container is unreachable from the Mac. `-p 9000:8000` would use http://localhost:9000.
- `--env-file .env` turns every line of `.env` into an environment variable in the container (the image itself has no `.env`).

Open http://localhost:8000/health → `{"status":"ok"}`, and http://localhost:8000/scalar → the docs. Now try **List all tags** → **500 Internal server error**. The terminal shows `ConnectionRefusedError`.

Why: `.env` says `POSTGRES_SERVER=localhost`. **Inside a container, `localhost` is the container itself**, and there's no Postgres in it. Press Ctrl+C.

Docker Desktop has a special name for your Mac, `host.docker.internal`. `-e` sets one variable and wins over `--env-file`:

```bash
docker run --rm -p 8000:8000 --env-file .env \
  -e POSTGRES_SERVER=host.docker.internal \
  -e REDIS_HOST=host.docker.internal \
  fastship-api:0.1.0
```

(`\` at the end of a line continues the command on the next line.) Now **List all tags** works: the container reached your Homebrew Postgres. Ctrl+C.

Notice in the terminal that the log lines have a time, a level and a logger name, and that SQL isn't printed: that's `ENVIRONMENT=production` from the image.

## 3.7 Everyday commands

```bash
docker run -d --name api-test -p 8000:8000 --env-file .env \
  -e POSTGRES_SERVER=host.docker.internal -e REDIS_HOST=host.docker.internal \
  fastship-api:0.1.0        # -d: in the background, --name: a name to refer to it
docker ps                   # running containers (add -a to include stopped ones)
docker logs -f api-test     # its output, -f keeps following (Ctrl+C stops following, not the app)
docker exec -it api-test sh # a shell INSIDE the running container (-it: interactive terminal)
  whoami                    #   -> fastship, not root
  ls -la /app               #   -> alembic.ini, app, migrations, requirements.txt, owned by root. No .env
  exit
docker stop api-test        # stop it (Docker sends SIGTERM, waits up to 10 s, then kills)
docker rm api-test          # delete the stopped container
```

---
# Part 4: A bridge network by hand (API + Postgres + Redis)

Before Compose does it for us, let's do it by hand once, so you see what Compose automates.

## 4.1 How containers find each other

Docker gives every container a private network address. Containers on the **same user-defined bridge network** can reach each other **by container name**: Docker runs a small DNS server for that network, so `fastship-db` resolves to the database container's address. (Docker's *default* bridge network, used when you give no `--network`, has no such DNS, which is why we create our own.)

```
your Mac ──-p 8000:8000──► fastship-api ──"fastship-db:5432"───► fastship-db
                               │
                               └───────"fastship-redis:6379"──► fastship-redis
          (all three on the network "fastship-net"; only the API publishes a port)
```

Only the API gets `-p`. The database is reachable by the API through the network, but not from your Mac or your Wi-Fi: smaller attack surface, and no clash with your Homebrew Postgres on 5432.

## 4.2 Network, database, Redis

```bash
docker network create fastship-net

docker run -d --name fastship-db --network fastship-net \
  --env-file .env \
  -v fastship-db-data:/var/lib/postgresql \
  postgres:18-alpine

docker run -d --name fastship-redis --network fastship-net redis:8-alpine

docker ps
```

- **`--env-file .env` on the database**: the official Postgres image creates a user, password and database on its first start from `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`, the same names our app uses. It ignores the other variables. (Compose in Part 5 will pass only those three, which is cleaner.)
- **`-v fastship-db-data:/var/lib/postgresql`**: a **named volume**. Docker keeps it outside the container, so the data survives `docker rm` and new image versions. Postgres 18 images store their data under `/var/lib/postgresql` (older versions used `/var/lib/postgresql/data`, many old tutorials show that path).
- **`redis:8-alpine`**: the `alpine` variants are smaller downloads. For ready-made images like these, the musl issue from 3.4 doesn't matter.

## 4.3 The tables: migrations with the same image

The new database is empty. Run the migrations with **our API image**, just a different command:

```bash
docker run --rm --network fastship-net --env-file .env \
  -e POSTGRES_SERVER=fastship-db \
  -e REDIS_HOST=fastship-redis \
  fastship-api:0.1.0 alembic upgrade head
```

You'll see each migration run, ending with `add tags`. The container exits by itself when `alembic` finishes, and `--rm` deletes it. This is why the Dockerfile uses `CMD` and not `ENTRYPOINT` (3.4).

Look at the tables:

```bash
docker exec -it fastship-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
```

`sh -c '...'` runs inside the container, so `$POSTGRES_USER` is the container's own variable (single quotes stop your Mac's shell from replacing it first). Expected: 7 tables, including `alembic_version`.

## 4.4 The API

```bash
docker run -d --name fastship-api --network fastship-net -p 8000:8000 \
  --env-file .env \
  -e POSTGRES_SERVER=fastship-db \
  -e REDIS_HOST=fastship-redis \
  -e CELERY_RESULT_BACKEND=redis://fastship-redis:6379/1 \
  fastship-api:0.1.0

docker logs -f fastship-api
```

- `CELERY_RESULT_BACKEND` is overridden too: queuing a task connects to the result backend first, and `localhost` would fail.
- There's no RabbitMQ yet, so queuing an email fails. The app already handles that (`NotificationService._enqueue` catches `OperationalError`): the shipment is saved, and the log shows `ERROR app.services.notification Could not queue ..., is RabbitMQ running?`. I measured it: creating a shipment still takes about 0.09 s. Render works the same way (Part 8).

In http://localhost:8000/scalar: sign up a seller and a partner (zip code 11001 for both), log in as the seller with **Authorize**, create a shipment, then **My shipments** with `limit=1`. Check the `x-total-count` header.

## 4.5 Clean up

```bash
docker rm -f fastship-api fastship-redis fastship-db
docker network rm fastship-net
docker volume rm fastship-db-data
```

`rm -f` stops and deletes in one go. The volume must be deleted separately; that's on purpose, so data isn't lost by accident.

Typing all those flags for every container is exactly what Compose replaces.

---

# Part 5: Docker Compose

## 5.1 What it is

`compose.yaml` describes all the containers, networks and volumes of the app in one file, and `docker compose up` creates them in the right order. Compose:

- creates a network for the project (`fastship_default`), so services reach each other by **service name**: `db`, `redis`, `rabbitmq`, `api`...
- prefixes names with the project name: containers `fastship-api-1`, volumes `fastship_db-data`
- reads `.env` from the same folder **for `${VARIABLE}` replacement** inside `compose.yaml`
- waits for dependencies (`depends_on` with conditions) and restarts crashed containers (`restart`)

Our services:

| Service | Image | Job |
|---|---|---|
| `db` | postgres:18-alpine | the database |
| `redis` | redis:8-alpine | token blacklist, delivery codes, Celery results |
| `rabbitmq` | rabbitmq:4-management-alpine | the Celery broker (your app uses RabbitMQ), with its web UI |
| `migrate` | our image | runs `alembic upgrade head` once, then exits |
| `api` | our image | FastAPI |
| `worker` | our image | the Celery worker: emails, SMS |
| `beat` | our image | Celery Beat: the daily overdue-shipments task |
| `web` | our frontend image | added in Part 6 |

## 5.2 The file

Create `compose.yaml` in the project root (the frontend's `web` service comes in Part 6):

```yaml
# The whole FastShip app on your machine, with one command:
#   docker compose up --build -d
# Frontend: http://localhost:8080   API docs: http://localhost:8000/scalar

name: fastship

# Shared by every service that runs our Python image. Compose ignores keys that
# start with x-, they only exist to be copied in with <<: *backend
x-backend: &backend
  image: fastship-api:dev
  build: .
  env_file: .env
  # .env is written for your Mac, where everything is on localhost. Inside
  # Compose each service is reached by its service name instead
  environment:
    POSTGRES_SERVER: db
    POSTGRES_PORT: 5432
    REDIS_HOST: redis
    REDIS_PORT: 6379
    CELERY_BROKER_URL: amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@rabbitmq:5672/fastship
    CELERY_RESULT_BACKEND: redis://redis:6379/1
  restart: unless-stopped

services:
  db:
    image: postgres:18-alpine
    # The image creates this user and database the first time it starts
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      # Postgres 18 keeps its data under /var/lib/postgresql
      - db-data:/var/lib/postgresql
    ports:
      # For pgAdmin on your Mac. 5433 because your own Postgres uses 5432.
      # 127.0.0.1: only your Mac can connect, not other devices on the Wi-Fi
      - "127.0.0.1:5433:5432"
    healthcheck:
      # Healthy when Postgres accepts connections. $$ is a $ that Compose leaves
      # alone, so the container's own variable is used
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  redis:
    image: redis:8-alpine
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  rabbitmq:
    image: rabbitmq:4-management-alpine
    # RabbitMQ saves its data under its host name, a random one would lose it
    hostname: rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: fastship
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    ports:
      # Management website: http://localhost:15673 (your own RabbitMQ uses 15672)
      - "127.0.0.1:15673:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 10s
      retries: 10
    restart: unless-stopped

  # Runs once and exits: creates or updates the tables, then the API starts
  migrate:
    <<: *backend
    command: ["alembic", "upgrade", "head"]
    restart: "no"
    depends_on:
      db:
        condition: service_healthy

  api:
    <<: *backend
    ports:
      - "8000:8000"
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    healthcheck:
      # The image has Python but not curl
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://localhost:8000/health')
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # Sends the emails and SMS from the queue
  worker:
    <<: *backend
    command:
      - celery
      - -A
      - app.worker.celery_app
      - worker
      - --pool=threads
      - --concurrency=4
      - --loglevel=INFO
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  # Adds the scheduled tasks to the queue, like the daily overdue check
  beat:
    <<: *backend
    # The schedule file goes in /tmp, the app user can't write in /app
    command:
      - celery
      - -A
      - app.worker.celery_app
      - beat
      - --loglevel=INFO
      - --schedule=/tmp/celerybeat-schedule
    depends_on:
      rabbitmq:
        condition: service_healthy

# Named volumes live outside the containers: the data survives
# `docker compose down` and new images. `down -v` deletes them
volumes:
  db-data:
  redis-data:
  rabbitmq-data:
```

Section by section:

**`name: fastship`**: the project name, used in container, network and volume names. Without it, Compose uses the folder name, and yours has spaces.

**`x-backend: &backend`**: Compose ignores top-level keys that start with `x-`. `&backend` is a YAML **anchor**: it names this block. `<<: *backend` inside a service copies the block in, and the service can then add or override keys (like `migrate` overriding `restart`). Four services run our image, so their shared settings are written once.

- **`image: fastship-api:dev` + `build: .`**: build the image from `./Dockerfile` and name it `fastship-api:dev`. All four services share it. You'll see `Image fastship-api:dev Built` four times: Compose builds once per service, and the second to fourth builds come entirely from the cache.
- **`env_file: .env`**: every line of `.env` becomes an environment variable in the container, like `--env-file`.
- **`environment:`**: these win over `env_file`. Your `.env` says `localhost`, which is correct for your Mac; inside Compose the other services are called `db`, `redis` and `rabbitmq`.
- **`${RABBITMQ_USER}`**: replaced by Compose from `.env` while it reads the file, so the URL contains your real user and password.

**`db`**:
- `environment:` passes only the 3 variables the image needs (better than all of `.env`, as in Part 4).
- `ports: "127.0.0.1:5433:5432"`: published for pgAdmin only. 5433 on your Mac, because your own Postgres has 5432. Writing `127.0.0.1:` means only your Mac can connect. Without it, Docker listens on every network interface, and other devices on your Wi-Fi could try to log in.
- `healthcheck`: Docker runs `pg_isready` every 5 s. The container is **healthy** once Postgres accepts connections, not merely when the process started. `$$` is how you write a literal `$` in `compose.yaml`; a single `$` would make Compose try to replace it from your `.env`.

**`redis`**: a volume for `/data` so Redis can save its data between restarts, and a `redis-cli ping` health check.

**`rabbitmq`**:
- The `RABBITMQ_DEFAULT_*` variables create the user and the `fastship` vhost on the first start. (RabbitMQ's built-in `guest` user can only log in from inside its own container, so the API couldn't use it.)
- `hostname: rabbitmq`: RabbitMQ stores its data in a folder named after its host name. Without a fixed one, each new container gets a random name and starts with empty data.
- Port 15673 is the management website (your Homebrew RabbitMQ already uses 15672).

**`migrate`**: `restart: "no"` overrides the anchor's `unless-stopped`; a finished migration must not be restarted forever. `depends_on: db: condition: service_healthy` waits until Postgres really accepts connections.

**`api`**:
- `depends_on: migrate: condition: service_completed_successfully`: the API starts only after the migrations finished with exit code 0. If a migration fails, the API doesn't start against a half-migrated database.
- `healthcheck`: our image has no `curl`, so Python's `urllib` calls `/health`. `start_period: 10s` gives the app time to start before failures count.

**`worker`**: the same command you run on your Mac (`--pool=threads --concurrency=4`). A list (`- celery`, `- -A` ...) is the exec form, like the Dockerfile's `CMD [...]`.

**`beat`**: `--schedule=/tmp/celerybeat-schedule`. Beat saves its schedule to a file, by default in the current folder, `/app`, which the `fastship` user can't write to. `/tmp` is writable.

**`restart: unless-stopped`**: if a container crashes, Docker starts it again. "unless-stopped" means: except when you stopped it yourself.

**`volumes:`** at the bottom declares the named volumes.

## 5.3 Run it

```bash
docker compose config --quiet && echo OK   # checks the file and the ${...} values
docker compose up --build -d
docker compose ps
```

- `--build` rebuilds our image if the code changed (without it, Compose reuses the last image).
- `-d` runs in the background.

The start order you'll see: `db`, `redis` and `rabbitmq` become **Healthy**, `migrate` runs and shows **Exited**, then `api` becomes Healthy, while `worker` and `beat` start. In my test, everything was up in about a minute.

```bash
docker compose logs -f api worker   # follow two services (Ctrl+C stops following)
docker compose logs migrate         # the migration output
```

Try the whole flow in http://localhost:8000/scalar: sign up a seller and a partner, create a shipment, and as the partner set it to `out_for_delivery`, then verify with the code.

> **Real emails go out.** The worker uses your Gmail settings from `.env`. Use **your own email** as `client_contact_email`, and leave `client_contact_phone` empty so no SMS is sent (Twilio trial credit). In my test I used a fake mail server instead: the 3 "Shipped" emails, the "Arriving Soon" email with the 6-digit code and the inline QR image all arrived, and the code from the email verified the delivery.

More to look at:
- **RabbitMQ**: http://localhost:15673, log in with `RABBITMQ_USER` / `RABBITMQ_PASSWORD`. Queues → `celery`, messages come and go as you create shipments.
- **pgAdmin**: Register → Server. Name: `FastShip Docker`. Connection: host `localhost`, port **5433**, username and password from your `.env`. This is the container's database, not your Homebrew one.
- **A shell in a service**: `docker compose exec api sh`
- **psql**: `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`
- **A one-off command**: `docker compose run --rm api alembic current`

## 5.4 Everyday Compose commands

| Command | What it does |
|---|---|
| `docker compose up --build -d` | build what changed, create or update containers, in the background |
| `docker compose up --build -d api` | rebuild and restart only `api` (after a code change) |
| `docker compose restart worker` | restart without rebuilding |
| `docker compose stop` | stop everything, keep the containers |
| `docker compose down` | stop and delete containers and the network. **Volumes stay**, so the data stays |
| `docker compose down -v` | the same, **and delete the volumes: all data is gone** |

I tested `down` then `up -d`: the 3 shipments were still there, and `migrate` ran again and did nothing (Alembic only runs migrations that weren't applied yet).

## 5.5 When something goes wrong

| Symptom | Cause |
|---|---|
| `api` never becomes healthy | `docker compose logs api`. Usually a missing `.env` value: pydantic prints its name |
| `migrate` exits with code 1 | `docker compose logs migrate`, often a wrong password. **If you changed `POSTGRES_PASSWORD` after the first start**: the volume still has the old password, because the image only creates the user on the *first* start. `docker compose down -v` (deletes the data) and `up` again |
| `password authentication failed` with `"..."` | quotes are still in `.env` (2.6) |
| `localhost:8000` shows old behavior | `fastapi dev` is still running on your Mac (Before you start, point 4) |
| `port is already allocated` | another container uses that port: `docker ps` |

---

# Part 6: The React app in a container

## 6.1 Multi-stage builds

To *build* the React app you need Node and `node_modules` (about 380 MB). To *serve* it you only need the result, plain files in `dist/` (about 1 MB), and a web server. A **multi-stage** Dockerfile has several `FROM` lines: the first stage builds, the last stage copies only the results from it, and everything else is thrown away.

```
stage "build": node:26-alpine + node_modules + src  ─► npm run build ─► /app/dist
stage 2:       nginx:1.29-alpine  +  COPY --from=build /app/dist         (the image you keep)
```

**nginx** is a small, very fast web server. It does two jobs here:
1. serves `index.html` and the JavaScript and CSS files
2. forwards `/api/...` to FastAPI, the same job the Vite proxy does in development. The frontend's `client.ts` already calls `/api` when `VITE_API_URL` isn't set, so **no React code changes**.

## 6.2 The files

These are new files in `frontend/`, not changes to your React code.

`frontend/.dockerignore`:

```text
# The image runs `npm ci` and `npm run build` itself, so the local results
# would only slow the build down (node_modules is about 380 MB)
node_modules/
dist/
.vite/

# Local settings, VITE_API_URL is decided at build time
.env
.env.*

.git/
.vscode/
Dockerfile
```

`frontend/Dockerfile`:

```dockerfile
# Two stages: Node builds the app, then only the built files go into a small
# nginx image. Node, node_modules and the source code are not in the result

# Stage 1: build the React app into plain HTML, CSS and JavaScript files
FROM node:26-alpine AS build

WORKDIR /app

# Packages before the code, so this layer stays cached until they change.
# npm ci installs exactly what package-lock.json says
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: serve the files from stage 1
FROM nginx:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
```

- **`AS build`** names the first stage, so `COPY --from=build` can take files from it.
- **`npm ci`** (not `npm install`) installs exactly the versions in `package-lock.json`, and fails if the lock file and `package.json` disagree. Builds are repeatable.
- **`package.json` and `package-lock.json` first, then `COPY . .`**: the same caching trick as the Python image.
- **`npm run build`** runs `tsc -b && vite build`: type-check, then build into `dist/`. A type error stops the image build, which is good.
- **No `CMD`**: the nginx image already has one that starts nginx.
- Node 26 matches your Mac (`node --version`).

`frontend/nginx.conf`:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;

    # Compress text files before sending them
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    # The same job the Vite proxy does in development: /api/seller/me goes to
    # FastAPI as /seller/me. "api" is the service name in compose.yaml
    location /api/ {
        proxy_pass http://api:8000/;
        # Tell FastAPI who really called and over what, nginx is in between
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Vite puts a hash in these file names (index-B1x2y3.js), a new build gets
    # new names, so browsers can keep them for a year without asking again
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # React Router handles /seller/shipments and the other pages in the browser.
    # Any path that isn't a real file gets index.html, then React shows the page.
    # no-cache: browsers check for a new index.html each time, so they get the
    # newest JavaScript file names after a deploy
    location / {
        try_files $uri /index.html;
        add_header Cache-Control "no-cache";
    }
}
```

- **`proxy_pass http://api:8000/;`**, the trailing `/` matters: nginx replaces the matched `/api/` with `/`, so `/api/seller/me` reaches FastAPI as `/seller/me`. Without it FastAPI would get `/api/seller/me` and answer 404.
- **`X-Forwarded-*` headers**: FastAPI sees nginx as the caller; these tell it the real client and protocol (that's what `--forwarded-allow-ips` trusts, 3.4).
- **`try_files $uri /index.html`**: `/seller/shipments/123` isn't a file, it's a React Router page. Without this, reloading that page gives nginx's 404. With it, nginx sends `index.html`, React starts and shows the right page.
- **Caching**: files in `/assets/` have a hash in their name (`index-CYN5s5KJ.js`); a new build gives new names, so browsers may keep them for a year. `index.html` gets `no-cache`, so after a deploy browsers pick up the new file names right away.

> A bug I hit while testing: I first wrote `expires 1y;` *and* `add_header Cache-Control ...`. nginx then sent **two** `Cache-Control` headers. One header with `max-age=31536000` does both jobs.

## 6.3 Add it to Compose

In `compose.yaml`, add this service at the end of `services:`, just above the `# Named volumes ...` comment, at the same indentation as `beat:`:

```yaml
  # The React app, built and served by nginx, which also forwards /api to FastAPI
  web:
    image: fastship-web:dev
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped
```

- `build: ./frontend` uses `frontend/` as the build context and `frontend/Dockerfile`.
- `depends_on: api: service_healthy`: nginx looks up the name `api` when it starts, and fails if `api` doesn't exist yet.

```bash
docker compose up --build -d
docker images fastship-web
```

Open http://localhost:8080 and log in. The image is about **93 MB** (nginx itself is 92 MB, your app 1 MB), compared with about 380 MB of `node_modules` it was built with.

What I tested through the container in Chrome: login, the dashboard, reloading `/seller/shipments/new` directly (nginx's `try_files`), the `/api` proxy, pagination headers through nginx, and no console errors.

> **The camera:** browsers only allow it on `https://` or `http://localhost`. http://localhost:8080 on your Mac works. Your phone at `http://<your Mac's IP>:8080` doesn't (not https); use `npm run dev:phone` from the frontend guide, or the Render site from Part 8, which is https.

---

# Part 7: Docker Hub

## 7.1 The platform problem

Your Mac has an **ARM** processor (Apple Silicon, `uname -m` says `arm64`). Render, and most servers, use **Intel/AMD** processors (`amd64`, also called x86_64). An image contains compiled programs (Python itself, `asyncpg`, `uvloop`...) built for one processor type. An ARM image on an amd64 server fails with `exec format error`. Render's docs say it plainly: the image must be built for `linux/amd64`.

The best fix is a **multi-platform image**: one tag that contains both an amd64 and an arm64 version, and every machine pulls the one it needs. Docker Desktop builds the amd64 version through emulation; slower, but it works.

## 7.2 Log in

Your Mac is already logged in to Docker Hub (it's in the keychain). To check, or to log in:

```bash
docker login
```

It shows your username. Use it in place of `YOUR_DOCKERHUB_USERNAME` below.

## 7.3 Build and push

```bash
docker build --platform linux/amd64,linux/arm64 \
  -t YOUR_DOCKERHUB_USERNAME/fastship-api:0.1.0 .

docker push YOUR_DOCKERHUB_USERNAME/fastship-api:0.1.0

docker buildx imagetools inspect YOUR_DOCKERHUB_USERNAME/fastship-api:0.1.0
```

- `--platform linux/amd64,linux/arm64` builds both versions (it took about 1.5 minutes on your Mac).
- The tag now starts with your username: `docker push` sends an image to the account its name starts with. The repository is created on the first push, **public** by default. That's fine here, because `.dockerignore` keeps `.env` out and the image has no secrets.
- `imagetools inspect` shows what's in the registry: `Platform: linux/amd64` and `linux/arm64`. Two `unknown/unknown` entries are normal; they're build records (attestations) Docker adds.

I tested exactly this push with a temporary local registry instead of Docker Hub. Both platforms arrived, and both versions start: `machine = x86_64` and `machine = aarch64`.

Then open https://hub.docker.com → **Repositories** → `fastship-api`: tag `0.1.0`, two platforms, about 110 MB compressed.

## 7.4 Tags: versions, not `latest`

Deploy **version tags** (`0.1.0`, `0.2.0`...), never `latest`. `latest` is only a default name, and it moves every time you push. With versions:
- you always know which code is running
- rolling back means deploying the previous tag
- a server restart can't pick up a newer image by surprise

Each new release: change `version=` in `app/main.py`, build with the new tag, push.

---
# Part 8: Deploy on Render (free)

Render runs your Docker Hub image as a web service, and gives you a managed Postgres and a Redis-compatible Key Value store. Everything below uses **free** instances only; no card needed for these.

> I can't open a Render account for you, so the Render website steps weren't clicked through by me. Everything that runs **on your side** was tested: the image, the exact Docker Command, the environment file, migrations through environment variables, CORS, `https` redirects, and running without RabbitMQ (simulated locally with the same settings, see Part 11). Render's dashboard changes its labels from time to time; if a button has a slightly different name, look for the closest one.

## 8.1 What "free" means on Render

| Free | Limit |
|---|---|
| Web service | 750 hours a month per workspace (one service running all month). **Spins down after 15 minutes without requests**; the next request wakes it, which takes about a minute. 512 MB RAM. |
| Postgres | **Expires 30 days after creation** (then a 14-day grace period to upgrade). 1 GB. One free database per workspace. No backups. |
| Key Value (Redis) | In memory only: data is lost on restart. One free instance. |
| Static site | Free, served from a CDN, doesn't spin down. |
| **Not free** | background workers, cron jobs, shell access, pre-deploy commands, persistent disks |
| **Blocked** on free web services | outgoing ports 25, 465 and 587, which are the SMTP ports used for sending email |

What this means for FastShip on Render:
- **No Celery worker**, as you said. Signup, login, shipments, tags, tracking and pagination all work. **Emails, SMS and delivery codes are not sent**, so a partner can't finish a delivery with a code on Render. The API stays fast anyway: queuing fails quickly and is logged, as tested in Part 4.
- With no worker, the API never needs your Gmail or Twilio secrets. They stay off the server (least privilege: a server only gets the secrets it uses).
- The free database is deleted after 30 days + 14. That's fine for learning; for a real product you'd pay.

## 8.2 Account and region

Sign up at https://render.com (GitHub login is easiest, the static site in 8.10 needs GitHub anyway).

Use **one region for everything**: Frankfurt (EU Central), the closest to Egypt. Services in the same region talk over Render's **private network** (fast, no internet, no TLS needed); across regions they can't.

## 8.3 Postgres

Dashboard → **New** → **Postgres**:

| Field | Value |
|---|---|
| Name | `fastship-db` |
| Database | `fastship` |
| User | `fastship` |
| Region | Frankfurt |
| PostgreSQL Version | 18 (the same as your Mac and the Compose file) |
| Instance type | **Free** |

**Create Database**, wait until its status is **Available**. On its page (**Info** / **Connections**) you'll find:

- **Hostname**: like `dpg-abc123xyz-a`. This short name only works *inside* Render.
- **Port** 5432, **Database**, **Username**, **Password** (click to reveal)
- **Internal Database URL**: `postgresql://fastship:PASSWORD@dpg-abc123xyz-a/fastship`, for services in the same region
- **External Database URL**: `postgresql://fastship:PASSWORD@dpg-abc123xyz-a.frankfurt-postgres.render.com/fastship`, for your Mac. External connections must use TLS (Render refuses `sslmode=disable`).

Our settings take the parts, not a URL, so you'll copy hostname, user, password and database name separately.

## 8.4 Key Value (Redis)

**New** → **Key Value**:

| Field | Value |
|---|---|
| Name | `fastship-redis` |
| Region | Frankfurt |
| Instance type | **Free** |
| Maxmemory Policy | **noeviction** |

Why `noeviction`: when memory is full, `allkeys-lru` deletes the least recently used keys to make room. One of those could be a **logged-out token on the blacklist**, and then that token works again. With `noeviction`, Redis refuses new writes instead and nothing is silently deleted. Our keys have expiry times, so memory frees itself up.

Copy the **Internal Key Value URL**: `redis://red-abc123xyz:6379`. `red-abc123xyz` is the `REDIS_HOST`. Internal connections need no password; external connections are off by default, which we keep.

## 8.5 Run the migrations from your Mac

The new database is empty. On the free plan there's no shell and no pre-deploy command, so the course runs Alembic **from your Mac** against the **external** address.

Environment variables win over `.env` (pydantic-settings reads them first), so you only override the database values, in **one terminal you close afterwards**:

```bash
export POSTGRES_SERVER=dpg-abc123xyz-a.frankfurt-postgres.render.com
export POSTGRES_PORT=5432
export POSTGRES_USER=fastship
export POSTGRES_DB=fastship
read -s POSTGRES_PASSWORD && export POSTGRES_PASSWORD
alembic upgrade head
alembic current
exit
```

- Use **your** external hostname (from the External Database URL, the part between `@` and `/`).
- `read -s` waits for you to paste the password and shows nothing, so it doesn't end up on screen or in your shell history. Paste it, press Enter.
- **TLS:** asyncpg (our Postgres driver) defaults to `sslmode=prefer`, so it tries TLS first and Render accepts it. Nothing to add. (I checked asyncpg's source: with no `ssl` setting it uses `'prefer'`.)
- `alembic current` should print `7737ed1e95a5 (head)`.
- **`exit` closes that terminal**, so no later command in it can accidentally hit the Render database. That's the whole point of the separate terminal.

I tested this exact override with the Compose database (`POSTGRES_SERVER=localhost POSTGRES_PORT=5433 alembic current` → `7737ed1e95a5 (head)`).

## 8.6 See it in pgAdmin

pgAdmin → **Register** → **Server**:

| Tab | Field | Value |
|---|---|---|
| General | Name | `FastShip Render` |
| Connection | Host name/address | your external hostname (`dpg-...frankfurt-postgres.render.com`) |
| | Port | `5432` |
| | Maintenance database | `fastship` |
| | Username / Password | from Render |
| Parameters | SSL mode | **require** |

Open Databases → fastship → Schemas → public → Tables: the 7 tables, and `tag` has the 7 tags from the migration (right-click → View/Edit Data). Use the full hostname, not an IP address: Render needs the name for TLS (otherwise `No SNI information found`).

## 8.7 The production environment file

Make secrets that are **different from your Mac's**. If your local `.env` ever leaks, production stays safe:

```bash
openssl rand -hex 32    # for JWT_SECRET
openssl rand -hex 32    # for VERIFICATION_CODE_SECRET
```

`openssl rand -hex 32` prints 32 random bytes as 64 hex characters.

Create a file `render.env` in the project root (git ignores it, it matches `*.env`) and fill in your values:

```text
# FastShip on Render. Paste all of it in fastship-api > Environment > Add from .env

# fastship-db > Info: the short internal hostname, user, password, database
POSTGRES_SERVER=dpg-abc123xyz-a
POSTGRES_PORT=5432
POSTGRES_USER=fastship
POSTGRES_PASSWORD=paste_the_render_database_password
POSTGRES_DB=fastship

# fastship-redis > Internal Key Value URL, redis://red-abc123xyz:6379
REDIS_HOST=red-abc123xyz
REDIS_PORT=6379

# New secrets, only for production: openssl rand -hex 32
JWT_SECRET=paste_the_first_openssl_output
JWT_ALGORITHM=HS256
VERIFICATION_CODE_SECRET=paste_the_second_openssl_output

# Required by the settings, but unused on Render: no worker sends email or SMS
MAIL_USERNAME=unused@example.com
MAIL_PASSWORD=unused
MAIL_FROM=noreply@example.com
MAIL_FROM_NAME=FastShip
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
TWILIO_ACCOUNT_SID=ACunused
TWILIO_AUTH_TOKEN=unused
TWILIO_NUMBER=+10000000000
FLOWER_USER=unused
FLOWER_PASSWORD=unused

# No RabbitMQ on Render: nothing listens here, so queuing fails at once
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=redis://red-abc123xyz:6379/0

# The static site's address (8.10)
CORS_ORIGINS=["https://fastship-web.onrender.com"]

# Our image listens on 8000, Render's default is 10000
PORT=8000
```

Why each value:
- **`POSTGRES_SERVER` / `REDIS_HOST` are the short internal names**: the API runs inside Render, so it uses the private network.
- **The mail and Twilio values are placeholders on purpose.** The settings classes require them, so the app wouldn't start without them, but on Render nothing sends email (no worker, and the SMTP ports are blocked). Your real Gmail App Password and Twilio token never leave your Mac. `noreply@example.com` must look like a real address; `fastapi-mail` checks it, and I tested these exact values.
- **`CELERY_BROKER_URL` points to nothing.** Inside the container nothing listens on port 5672, so queuing fails in milliseconds and is logged. (A host that doesn't exist could make every request hang while it waits for a timeout.)
- **`CELERY_RESULT_BACKEND` is the Key Value store, database 0**: queuing a task connects there first, so it must exist. Database 0 also holds the token blacklist; the key names don't overlap.
- **`CORS_ORIGINS`**: your frontend's address from 8.10. Use this name for now, you'll fix it if Render gives a different one.
- **`PORT=8000`**: Render routes traffic to `$PORT` (10000 by default). Our image listens on 8000, so we say so.

## 8.8 The web service, from your Docker Hub image

**New** → **Web Service** → **Existing Image**:

1. **Image URL**: `docker.io/YOUR_DOCKERHUB_USERNAME/fastship-api:0.1.0`. Public image, so no credential needed. → **Connect**.
2. **Name**: `fastship-api`. This name becomes your address: `https://fastship-api.onrender.com`, or with a suffix if the name is taken.
3. **Region**: Frankfurt. **Instance type**: **Free**.
4. **Environment Variables** → **Add from .env** → paste the whole content of `render.env` → add.
5. **Advanced**:
   - **Health Check Path**: `/health`
   - **Docker Command**:
     ```
     /bin/sh -c "alembic upgrade head && exec fastapi run app/main.py --port 8000 --forwarded-allow-ips '*'"
     ```
6. **Deploy Web Service**.

The Docker Command, piece by piece:
- It **replaces the image's `CMD`** (3.4). Render runs it as given, without a shell, so to run two commands we start a shell ourselves: `/bin/sh -c "..."`.
- **`alembic upgrade head &&`**: on **every deploy**, the migrations run first, over the internal network. `&&` means "only if the first one succeeded", so a failed migration stops the deploy instead of starting the API on a broken database. Free instances have no pre-deploy command, and this is the usual replacement. You ran it by hand in 8.5 to learn it; from now on new migrations apply themselves. (With several instances, two could migrate at the same time; free has only one.)
- **`exec`**: replaces the shell with `fastapi`, so `fastapi` becomes the main process and receives Render's stop signal itself (the shell-form problem from 3.4). I checked the process list in the container: only `fastapi run ...` is left.
- **`'*'` in single quotes** stops the shell from expanding `*` into file names.

I ran this exact command with the same environment file locally: migrations ran, then `Uvicorn running on http://0.0.0.0:8000`.

## 8.9 Watch it, then test with Scalar

On the service page:
- **Events**: the deploy steps. "Pulling image", then the health check, then **Live**.
- **Logs**: your container's stdout. You'll see Alembic's lines, `Application startup complete`, then one line per request from uvicorn (`INFO: ... "GET /health HTTP/1.1" 200`) and our `fastship.requests` line with the duration and request ID. Use the search box: try `ERROR` or a request ID.
- **Metrics**: CPU, memory, requests.

Open `https://fastship-api.onrender.com/scalar` (your address):

1. **Sign up** a seller (`POST /seller/signup`) and a partner (`POST /partner/signup`, `serviceable_zip_codes: [11001]`).
2. **Authorize**: in the Seller scheme, enter the seller's email and password. Scalar gets the token from `/seller/token`.
3. **Submit a shipment** → 201. In **Logs**: `ERROR app.services.notification Could not queue app.worker.tasks.send_email_with_template, is RabbitMQ running?`. That's the expected result without a worker, and the shipment is saved anyway.
4. **My shipments** with `limit=1`, `sort_by=weight` → response header `x-total-count`.
5. **Get a shipment**, and **Tracking page** with its id (HTML).
6. pgAdmin → `shipment` table → your rows are there.

After 15 minutes without requests the service sleeps; the next request takes about a minute (you'll see the "waking up" page). That's the free plan.

## 8.10 The frontend as a static site

The React app is just files, so it doesn't need a container on Render: a **Static Site** is free, served from a CDN, and never sleeps. Render builds it from your GitHub repo; `frontend/` is already pushed (commit `f580584`). The three new files from Part 6 don't matter here, Render runs its own build.

**New** → **Static Site** → connect GitHub → choose `FastAPI-Best-Practices`:

| Field | Value |
|---|---|
| Name | `fastship-web` (→ `https://fastship-web.onrender.com`) |
| Branch | `main` |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |
| Environment variable | `VITE_API_URL` = `https://fastship-api.onrender.com` (your API address, no `/` at the end) |

Then, in the site's **Redirects/Rewrites**, add one rule:

| Source | Destination | Action |
|---|---|---|
| `/*` | `/index.html` | **Rewrite** |

Why:
- **Root Directory `frontend`**: the repo root is the backend, the React app is in `frontend/`.
- **`VITE_API_URL` is used at build time.** Vite replaces `import.meta.env.VITE_API_URL` with the text while building, so the JavaScript files contain `https://fastship-api.onrender.com`. Changing the variable later means rebuilding (**Manual Deploy**). Never put secrets in `VITE_` variables: they end up in files anyone can download.
- **The rewrite** does what nginx's `try_files` did: React Router paths get `index.html`. **Rewrite**, not Redirect, because the address in the browser must stay `/seller/shipments/123`. Render applies it only when no real file exists at that path, so `/assets/*.js` still works.
- **Node version**: Render's default today is Node 24, which works with Vite 8. If you want the same version as your Mac, add `NODE_VERSION=26`.

**CORS.** The site (`fastship-web.onrender.com`) and the API (`fastship-api.onrender.com`) are **different origins**, so the browser asks the API first (the `OPTIONS` "preflight") whether this site may call it. If your site's address differs from `CORS_ORIGINS` in 8.7, change it on the API service: **Environment** → edit `CORS_ORIGINS` → save (it redeploys). I tested the answer with these values: `Origin: https://fastship-web.onrender.com` → `200` with `access-control-allow-origin`; any other origin → `400`, no permission.

Open `https://fastship-web.onrender.com`, sign up, log in, create a shipment, try the pages and pagination headers in DevTools → Network. It's **https**, so the QR scanner can use your **phone's camera** too. (On Render, no code is emailed, so there's nothing real to scan; scanning works with the Compose setup.)

Every `git push` to `main` rebuilds the site (auto-deploy).

## 8.11 Shipping a new version of the API

Image-backed services don't redeploy by themselves:

```bash
# 1. change version="0.2.0" in app/main.py, then:
docker build --platform linux/amd64,linux/arm64 -t YOUR_DOCKERHUB_USERNAME/fastship-api:0.2.0 .
docker push YOUR_DOCKERHUB_USERNAME/fastship-api:0.2.0
```

2. Render → `fastship-api` → **Settings** → **Image URL**: change the tag to `0.2.0` → save → **Manual Deploy** → **Deploy latest reference**.

Rolling back = setting the old tag again. (Render also has a **Deploy Hook** URL in Settings: calling it starts a deploy, which is how a CI pipeline would do it later.)

---
# Part 9: Telemetry with OpenTelemetry and Logfire

## 9.1 The ideas

When the app runs on a server you can't put a `print` in it or attach a debugger. **Telemetry** is the data an app sends about itself so you can see what it does. There are three kinds:

| Signal | What | Example from FastShip |
|---|---|---|
| **Logs** | text lines about events | `Could not queue send_email_with_template` |
| **Metrics** | numbers over time | requests per minute, memory, p95 response time |
| **Traces** | the path of one request through the system, with timings | `PATCH /shipment/` took 45 ms: 6 SQL queries, 1 Redis check, then queued a task, and the worker sent the email 200 ms later |

A **trace** is made of **spans**. A span is one timed step with a name, a start, a duration and **attributes** (key/value details). Spans nest: the request span is the parent, each SQL query inside it is a child. Every span in a trace shares the same **trace ID**.

```
trace 01a1bd945c8d                                    service
└─ PATCH /shipment/                                   fastship-api
   ├─ SELECT   (the shipment, the partner, ...)       fastship-api
   ├─ EXISTS   (is the token on the blacklist?)       fastship-api
   ├─ INSERT   (the new shipment_event)               fastship-api
   └─ apply_async/app.worker.tasks.send_verification_code    fastship-api
      └─ run/app.worker.tasks.send_verification_code          fastship-worker
         ├─ SET  (save the new code's hash)                   fastship-worker
         └─ DEL  (reset the failed attempts)                  fastship-worker
```

This tree is real, simplified: these span names are what I recorded in the Compose test (Part 11), the real trace had 9 SELECTs and 1 INSERT. The API's span and the worker's span are in **one trace**, even though they run in different containers. That's **context propagation**: when the API queues the task, it writes the trace ID into the RabbitMQ message, and the worker reads it and continues the same trace.

**OpenTelemetry** (OTel) is the open standard for all of this: one API and SDK for creating spans, ready-made **instrumentations** (plug-ins) for FastAPI, SQLAlchemy, Redis and Celery that create the spans for you, and one wire format, **OTLP**, that every telemetry backend accepts.

**Logfire** is one such backend (made by the Pydantic team, the people behind FastAPI's validation): a website that stores the telemetry and lets you search it, plus a Python package `logfire`, which is a thin, friendly layer over the OpenTelemetry SDK. Because underneath it's OpenTelemetry, you aren't locked in (9.10).

**Free plan** (checked on their pricing page): 10 million logs, spans and metrics a month, 30 days of history, no credit card. If you go over, data just stops being accepted until next month. You won't get a bill.

## 9.2 Install

```bash
pip install 'logfire[fastapi,sqlalchemy,celery,redis]'
```

The part in `[...]` adds the four OpenTelemetry instrumentations. The quotes stop zsh from treating `[` `]` as a file pattern.

Add it to `pyproject.toml`, at the end of `dependencies`:

```toml
    "segno==1.6.6",
    "logfire[fastapi,sqlalchemy,celery,redis]",
]
```

(Note the `,` added after `"segno==1.6.6"`.) Then update `requirements.txt` with the command from 2.5:

```bash
pip freeze $(grep "==" requirements-dev.txt | sed 's/==.*//; s/^/--exclude /') > requirements.txt
git diff --stat requirements.txt
```

In my test this added `logfire`, `logfire-sdk`, six `opentelemetry-instrumentation-*` packages and a few helpers, and moved `opentelemetry-api`/`-sdk` from 1.45.1 to 1.45.2 (they were already there, `fastapi-cloud-cli` uses them).

## 9.3 The token setting

In `app/config.py`, in `AppSettings`, under `CORS_ORIGINS`:

```python
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Write token of the Logfire project, empty means telemetry stays on this machine
    LOGFIRE_TOKEN: str | None = None
```

Why a setting and not just the environment variable: `logfire` reads `LOGFIRE_TOKEN` from real environment variables, but pydantic-settings reads `.env` **without** putting its values into the environment. As a setting it works from `.env` on your Mac, from `env_file` in Compose and from Render's environment, like every other setting.

## 9.4 The telemetry module

Create `app/core/telemetry.py`:

```python
import logging
from typing import Any

import logfire
from fastapi import FastAPI

from app.config import app_settings
from app.database.session import engine


def _configure(service_name: str, distributed_tracing: bool):
    logfire.configure(
        # Shown on every span, so the API and the worker can be told apart
        service_name=service_name,
        environment=app_settings.ENVIRONMENT,
        token=app_settings.LOGFIRE_TOKEN,
        # Without a token (tests, a machine without one) nothing is sent anywhere
        send_to_logfire="if-token-present",
        # Our own logging already prints to the terminal
        console=False,
        # Whether to continue a trace that arrives from outside, see the callers
        distributed_tracing=distributed_tracing,
    )
    # Our log lines also go to Logfire, attached to the request that wrote them
    logging.getLogger("app").addHandler(logfire.LogfireLoggingHandler())


def _request_attributes(request: Any, attributes: dict[str, Any]) -> dict[str, Any]:
    # By default every endpoint argument is recorded. Ours hold emails, phone
    # numbers and the login form, so keep only the validation errors
    return {"errors": attributes["errors"]} if attributes["errors"] else {}


def setup_telemetry(app: FastAPI):
    # Anyone on the internet can send a trace id header, don't join their traces
    _configure("fastship-api", distributed_tracing=False)
    # One span (a timed step) per request: route, status code and duration.
    # /health is called every few seconds by Docker and Render, skip it
    logfire.instrument_fastapi(
        app,
        excluded_urls="/health",
        request_attributes_mapper=_request_attributes,
    )
    # One span per SQL query and per Redis command, inside the request's span.
    # skip_dep_check: the instrumentation lists SQLAlchemy < 2.1, we have 2.1.
    # tests/unit/test_telemetry.py checks that the query spans still work
    logfire.instrument_sqlalchemy(engine=engine, skip_dep_check=True)
    logfire.instrument_redis()
    # Puts the trace id in each task message, so the worker continues the trace
    logfire.instrument_celery()


def setup_worker_telemetry():
    # Task messages come from our own API: continue the API's trace
    _configure("fastship-worker", distributed_tracing=True)
    logfire.instrument_celery()
    logfire.instrument_redis()
```

Why each part:
- **`service_name`**: every span is labeled `fastship-api` or `fastship-worker`, so you can filter by it.
- **`environment`**: `development` on your Mac, `production` in Docker and on Render. One Logfire project, two environments, easy to separate.
- **`send_to_logfire="if-token-present"`**: without a token nothing is sent. The tests, and anyone who clones the repo, don't need an account.
- **`console=False`**: Logfire can also print every span to the terminal. We already print logs, and SQL spans in the terminal would be noise.
- **`LogfireLoggingHandler` on the `app` logger**: our log lines (`logger.error(...)` in `app/...`) also go to Logfire, **attached to the span that was active**, so a "Could not queue" error shows up *inside* the request that caused it.
- **`_request_attributes`: privacy.** By default the FastAPI instrumentation records every endpoint argument. Ours include client emails, phone numbers and the login form. Logfire hides values whose names look secret (`password`, `token`...), but an email isn't hidden. We keep only validation errors, which help debug 422s. A test checks that the client email and the password never reach a span. **Telemetry is data leaving your server; treat it like an API response that goes to a third party.**
- **`excluded_urls="/health"`**: Docker calls `/health` every 10 s and Render every few seconds. That's thousands of useless spans a day, and the free plan counts them.
- **`skip_dep_check=True`**: the SQLAlchemy instrumentation declares support for SQLAlchemy `< 2.1`, and you have 2.1.6, so by default it refuses to start. I tested it with the check skipped: query spans work. The test `test_sql_queries_are_recorded` will tell you if a future version breaks it.
- **`distributed_tracing`**: a trace ID can arrive from outside, in an HTTP `traceparent` header or in a Celery message. For the **API**, the request comes from the internet: anyone could send a made-up trace ID and get their requests mixed into your traces, so `False`. For the **worker**, the messages come from our own API, which is exactly how API and worker end up in one trace, so `True`. (Without this setting Logfire prints a warning about it, which is how I noticed.) I tested both: a fake `traceparent` sent to the API was ignored, and the API → worker trace still worked.

## 9.5 Turn it on in the API

In `app/main.py`, import it:

```python
from app.core.middleware import log_requests
from app.core.telemetry import setup_telemetry
```

and call it right after `setup_logging()`:

```python
setup_logging()
setup_telemetry(app)
```

After logging is set up, because `_configure` adds its handler to the `app` logger.

## 9.6 The logging middleware: link the request ID to the trace

You already have `log_requests` in `app/core/middleware.py`: it gives each request an ID, puts it in `X-Request-ID`, and logs one line per request. Now the request span should carry that ID too. Add the import:

```python
from fastapi import Request
from opentelemetry import trace
```

and one line after `request.state.request_id = request_id`:

```python
    # request.state is shared with routes and exception handlers for this request
    request.state.request_id = request_id
    # Also on the request's telemetry span, so Logfire can find it by this ID
    trace.get_current_span().set_attribute("request_id", request_id)
```

Why:
- The FastAPI instrumentation wraps the **whole** middleware stack, so its request span is already the "current span" when our middleware runs. `trace.get_current_span()` is plain OpenTelemetry, it works with any backend.
- Your 500 handler already returns `request_id` to the client. Now support can ask for that ID and find the exact request, with its SQL queries and the error, in Logfire.

## 9.7 Turn it on in the worker

In `app/worker/celery_app.py`, add the imports:

```python
from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]
from celery.signals import worker_init  # type: ignore[import-untyped]

from app.config import celery_settings
from app.core.telemetry import setup_worker_telemetry
```

and at the end of the file:

```python
@worker_init.connect(weak=False)
def start_telemetry(**kwargs):
    # Runs once when the worker starts. We use --pool=threads, so the tasks run
    # in this same process. (The default prefork pool would need
    # worker_process_init, which runs in each forked process)
    setup_worker_telemetry()
```

Why a **signal** and not a line at the top of the file: `celery_app.py` is also imported by the API (to queue tasks) and by Beat. The API does its own setup in `main.py`; this must only run in the worker. `worker_init` is sent only when a worker starts. `weak=False` keeps the function registered (Celery would otherwise keep only a "weak" reference to it).

Why `worker_init` and not `worker_process_init` (which Logfire's docs show): with the default **prefork** pool, Celery starts *child processes* that run the tasks. The exporter's background thread doesn't survive being copied into a child process, so prefork must set up in each child (`worker_process_init`). You run `--pool=threads`: one process, tasks in threads. There `worker_process_init` never fires, and `worker_init` is right. I tested it: the worker's spans arrived.

## 9.8 Tests

Create `tests/unit/test_telemetry.py`:

```python
import json

import logfire
from httpx import AsyncClient
from logfire.testing import CaptureLogfire
from sqlalchemy import text

from app.database.session import engine
from tests.helpers import PASSWORD


def spans(capfire: CaptureLogfire) -> list[dict]:
    return capfire.exporter.exported_spans_as_dict()


async def test_request_has_a_span(client: AsyncClient, capfire: CaptureLogfire):
    response = await client.get("/tag/")

    request_span = next(s for s in spans(capfire) if s["name"] == "GET /tag/")
    # The same ID the client got back, so a bug report can be found in Logfire
    assert request_span["attributes"]["request_id"] == response.headers["X-Request-ID"]


async def test_sql_queries_are_recorded(capfire: CaptureLogfire):
    # The app's own engine, instrumented by setup_telemetry (the other tests use
    # a separate engine for the test database). SELECT 1 reads no data
    with logfire.span("request"):
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    request = next(s for s in spans(capfire) if s["name"] == "request")
    query = next(s for s in spans(capfire) if s["name"] == "SELECT")
    # The query is a child of the span that was open when it ran
    assert query["parent"]["span_id"] == request["context"]["span_id"]
    assert query["attributes"]["db.statement"] == "SELECT 1"


async def test_health_checks_are_not_recorded(
    client: AsyncClient, capfire: CaptureLogfire
):
    await client.get("/health")

    assert spans(capfire) == []


async def test_no_personal_data_in_spans(
    client: AsyncClient,
    capfire: CaptureLogfire,
    seller_headers,
    partner,
    shipment_data,
):
    # seller_headers logged in with the password, this sends the client's email
    await client.post("/shipment/", json=shipment_data, headers=seller_headers)

    recorded = json.dumps(spans(capfire))
    assert shipment_data["client_contact_email"] not in recorded
    assert PASSWORD not in recorded
```

- **`capfire`** is a pytest fixture that comes with `logfire` (no import needed for the fixture itself): during the test, spans go to an in-memory list instead of the network.
- `test_sql_queries_are_recorded` uses the **app's** engine. The other tests use a separate engine for the test database, and OpenTelemetry instruments SQLAlchemy only once per process (I tried instrumenting the test engine as well; the second call does nothing). `SELECT 1` reads no data.

```bash
pytest
ruff check app tests
```

Expected: **95 passed**.

## 9.9 Logfire: the website

The website's labels may differ slightly from these.

1. Go to https://logfire.pydantic.dev and sign up (GitHub is easiest). When asked for a **data region**, pick **EU** (the closest to you; your token remembers it).
2. Create a **project**: `fastship`.
3. Project **Settings** → **Write tokens** → **New write token** → copy it. It starts with `pylf_v1_`. It's a secret: it lets anyone send data into your project.
4. Add it to your Mac's `.env`:

   ```bash
   LOGFIRE_TOKEN=pylf_v1_eu_...your token...
   ```

5. Run the app as usual: `fastapi dev`, and the worker in its own terminal (`celery -A app.worker.celery_app worker --pool=threads --concurrency=4 --loglevel=INFO`), and the frontend (`npm run dev`). Click around: log in, create a shipment, change its status.

In Logfire:
- **Live**: spans arrive as they happen. Click `POST /shipment/` to open the trace: every SQL query with its duration, the Redis `EXISTS` (the token blacklist check), `apply_async/...` and, nested under it, the worker's `run/...` with its Redis commands.
- **Filter** by `service_name = 'fastship-worker'`, or `deployment_environment = 'production'`.
- **Find a request by its ID**: copy `x-request-id` from DevTools → Network, and search `attributes->>'request_id' = 'the id'`.
- **Explore** (SQL): telemetry is a table you can query. For example, the slowest requests:

  ```sql
  SELECT span_name, duration, start_timestamp
  FROM records
  WHERE service_name = 'fastship-api' AND span_name LIKE '% /%'
  ORDER BY duration DESC
  LIMIT 20
  ```

  (The editor lists the available columns; `duration` is in seconds.)
- **Errors**: stop RabbitMQ (`brew services stop rabbitmq`), create a shipment, and find the `Could not queue ...` log *inside* that request's trace. Start it again: `brew services start rabbitmq`.

## 9.10 In Docker and on Render

**Compose**: nothing to do. `env_file: .env` already passes `LOGFIRE_TOKEN` to `api` and `worker`. `docker compose up --build -d` (the image needs the new packages), and the spans arrive with `environment = production` and the container names.

**Render**: a new version (8.11): set `version="0.2.0"` in `app/main.py`, build and push `0.2.0`. Add **one** environment variable to `fastship-api`: `LOGFIRE_TOKEN` = your token. Change the image tag, deploy. Your Render traffic now shows up in Logfire next to your Mac's, separated by `deployment_environment`.

> **Vendor-neutral:** the same code can send to any OpenTelemetry backend (Grafana Tempo, Jaeger, Honeycomb, Datadog...) with the standard variable `OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318`, no Logfire token needed. That's how I tested the Compose traces: a tiny OTLP receiver on my side printed every span the containers sent.

## 9.11 What to remember

- Logs tell you **what** happened, metrics **how much**, traces **where the time went**.
- Instrument the edges (HTTP in, database, cache, queue) and you get most of the value without writing a single `span` yourself.
- Never send secrets or personal data. Decide what goes out (`request_attributes_mapper`), and test it.
- Skip noise like health checks. On free plans every span counts.

---
# Part 10: AWS, only the free parts

## 10.1 The honest answer first: can FastShip run on AWS for free?

**Not completely, and not the way the course did it.** I checked AWS's own pages (sources at the end of this guide):

| What the course used | Status for a new AWS account today | In this guide |
|---|---|---|
| **App Runner** (runs the container) | **Closed to new customers since April 30, 2026.** Only accounts that already used it can still create services. You can't create one. | Skipped, it's not possible |
| **ECS Express Mode** (AWS's suggested replacement) | Free to use itself, but it creates an **Application Load Balancer** and **Fargate** tasks that are billed by the hour: roughly **$1 a day** (about $35 a month) from public prices. | Skipped, not free |
| **ECR** (image registry) | 500 MB a month free for 12 months; our image is about 230 MB for both platforms. Otherwise $0.10 per GB a month from credits. | **Done** (10.6) |
| **IAM** (users, roles, permissions) | Always free | **Done** (10.4) |
| **API Gateway**, REST API | 1 million calls a month free for 12 months, otherwise $3.50 per million. A few hundred test calls cost less than one cent. | **Done** (10.7, 10.8), in front of your Render API |
| **API Gateway cache** | Billed per hour, **never free**: about $0.02 an hour for the smallest size | **Optional** (10.9), about one hour |
| **CloudWatch Logs** | 5 GB a month free | **Optional** (10.10) |

**The AWS Free plan.** New accounts (since July 2025) choose a **Free plan** or a **Paid plan** at sign-up. The Free plan gives **$100 of credits, plus up to $100 more** for trying services, for 6 months, and AWS says most new customers don't even need a payment method. When the credits or the 6 months run out, the account is **paused, not billed**. That's the safe choice for learning: **pick the Free plan.** (Some services are blocked on the Free plan; if the console refuses something below, skip that step.)

So the plan is: **Render runs the app (free), AWS adds a gateway in front of it (free)**, and you learn IAM, ECR and API Gateway, the parts that are the same whatever runs the container.

> I can't create an AWS account for you, so none of the AWS console steps were clicked through by me. What I could test: the `apigateway.json` file is generated from your real API, validated against the OpenAPI 3.0 schema, and checked against AWS's documented import rules (Part 11). AWS's console changes often; if a label is different, look for the closest one.

## 10.2 Why put an API gateway in front of an API at all?

FastAPI already checks tokens and validates input. A gateway is a **front door** that does things every API needs, before the request reaches your code:

| Job | Example |
|---|---|
| **Throttling** (rate limits) | at most 10 requests per second; more get `429` without touching your server. Protects a small server like Render's free one from floods |
| **API keys and usage plans** | give a partner company a key with 10,000 calls a month, then bill or block them |
| **Caching** | answer repeated `GET`s from memory, your server isn't even called |
| **One address for many backends** | `/shipments/*` → this service, `/payments/*` → another. Move a backend from Render to ECS later, clients keep the same URL |
| **Security at the edge** | AWS WAF (blocks attack patterns), IP allow lists, authorizers (Cognito, Lambda), mutual TLS |
| **Versions and stages** | `/dev` and `/prod` stages of the same API, with canary releases |
| **Monitoring** | per-endpoint metrics and access logs in CloudWatch |

The costs: one more network hop (a few to tens of milliseconds), a hard **29-second timeout**, another thing to configure, and money at scale. A single small app often doesn't need one; a company with many APIs and many clients almost always has one.

## 10.3 Create the account (safely)

1. https://aws.amazon.com → **Create an AWS account**. Choose the **Free plan**.
2. The email and password you use make the **root user**: it can do anything, including closing the account. After the next steps you'll use it almost never.
3. Sign in as root → top-right account menu → **Security credentials** → **Assign MFA** (a passkey or an authenticator app). Do this before anything else; a leaked root password without MFA is the classic way AWS accounts get stolen.
4. Region (top-right): **Europe (Frankfurt) eu-central-1**, the same region as your Render services, so the gateway → Render hop is short.
5. **Billing and Cost Management** → **Budgets** → **Create budget** → template **Zero spend budget** → your email. AWS emails you the moment anything costs money, even if credits pay for it. A good habit on any cloud.

## 10.4 IAM: stop using root

**IAM** (Identity and Access Management) decides **who** can do **what** on **which** resources:
- a **user** is a person or a program with long-term sign-in
- a **role** is a set of permissions that an AWS service or a user can *take on* for a while (temporary credentials)
- a **policy** is a JSON document of allowed actions, e.g. `ecr:PutImage` on one repository

You'll know Azure's version of this (Entra ID with RBAC); the ideas are the same.

Create an everyday admin user:
1. Search **IAM** → **Users** → **Create user** → name `marwan-admin` → check **Provide user access to the AWS Management Console** → custom password.
2. **Permissions** → **Attach policies directly** → `AdministratorAccess`. (For learning on your own account. In a company you'd get narrower permissions.)
3. Create. Copy the **console sign-in URL** (it has your account ID in it).
4. Sign out of root, sign in with that URL as `marwan-admin`, and give this user MFA too (**IAM** → **Users** → `marwan-admin` → **Security credentials** → **Assign MFA**).

From now on, use `marwan-admin`.

## 10.5 The AWS CLI, without access keys

```bash
brew install awscli
aws --version        # 2.32 or newer is needed for `aws login`
aws login
aws configure set region eu-central-1
aws sts get-caller-identity
```

- `aws login` opens the browser: sign in as `marwan-admin`, approve, done. The CLI gets **temporary** credentials that renew themselves every 15 minutes. This is AWS's recommended way since November 2025. The old way, an **access key** pasted into `~/.aws/credentials`, is a long-term password in a file. That's how keys leak, through a git commit or a backup. Avoid it when you can.
- `aws sts get-caller-identity` prints your account ID and `arn:aws:iam::123456789012:user/marwan-admin`: proof that you're signed in.

## 10.6 ECR: your private image registry on AWS

ECR is AWS's Docker Hub. AWS services (ECS, Lambda, App Runner) pull images from it over AWS's own network, without Docker Hub's download limits.

```bash
aws ecr create-repository --repository-name fastship-api --image-tag-mutability IMMUTABLE

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGISTRY=$ACCOUNT.dkr.ecr.eu-central-1.amazonaws.com
echo $REGISTRY

aws ecr get-login-password | docker login --username AWS --password-stdin $REGISTRY

docker tag YOUR_DOCKERHUB_USERNAME/fastship-api:0.1.0 $REGISTRY/fastship-api:0.1.0
docker push $REGISTRY/fastship-api:0.1.0
```

- **`--image-tag-mutability IMMUTABLE`**: pushing `0.1.0` a second time is refused. A version name then always means the same image (7.4), and nobody can quietly replace a deployed version.
- `--query Account --output text` picks one field from the JSON answer.
- **`get-login-password | docker login --password-stdin`**: the AWS CLI makes a Docker password valid for 12 hours, and `|` (a pipe) hands it to `docker login` without it ever appearing on screen or in your history.
- **`docker tag`** gives the existing image a second name (no copy, no rebuild). The registry is part of the name, so `docker push` knows where to send it. It pushes both platforms.

Console → **ECR** → `fastship-api`: the tag, both platforms, the size, and **Scan** (ECR can scan images for known vulnerabilities, a useful habit).

This is the image App Runner or ECS Express Mode would run. Here it's where AWS's learning path stops, because running it isn't free (10.1).

## 10.7 API Gateway: import the OpenAPI file

### Make the file

FastAPI's `/openapi.json` can't be imported as it is:
- API Gateway imports **OpenAPI 3.0**; FastAPI writes **3.1**.
- API Gateway paths **can't end with `/`**; FastAPI has `/shipment/` and `/tag/`.
- Each endpoint must say **where to send the request** (the "integration"), and FastAPI's file doesn't know that.

A small script does it. Create `scripts/openapi_to_apigateway.py`:

```python
"""Writes apigateway.json, an OpenAPI file that AWS API Gateway (REST API) imports.

FastAPI's /openapi.json can't be imported as it is: API Gateway reads OpenAPI 3.0
(FastAPI writes 3.1), its paths can't end with "/", and it needs to know where
to send each request. Run it with the public URL of the deployed API:

    python scripts/openapi_to_apigateway.py https://fastship-api.onrender.com
"""

import json
import sys
import urllib.request

backend = sys.argv[1].rstrip("/")

with urllib.request.urlopen(f"{backend}/openapi.json", timeout=90) as response:
    fastapi_spec = json.load(response)

paths: dict[str, dict] = {}
for path, operations in fastapi_spec["paths"].items():
    # API Gateway doesn't allow "/shipment/", so the gateway path is "/shipment"
    # and the backend URL below keeps FastAPI's own path with the "/"
    gateway_path = path.rstrip("/") or "/"

    for method, operation in operations.items():
        # Only the real API, the practice routes like /time have no tag
        if not operation.get("tags"):
            continue

        paths.setdefault(gateway_path, {})[method] = {
            "operationId": operation["operationId"],
            "summary": operation.get("summary", ""),
            "tags": operation["tags"],
            # API Gateway only reads name, in, required and type. Declaring the
            # query parameters lets the cache use them later (e.g. ?id=)
            "parameters": [
                {
                    "name": parameter["name"],
                    "in": parameter["in"],
                    "required": parameter.get("required", False),
                    "schema": {"type": "string"},
                }
                for parameter in operation.get("parameters", [])
                if parameter["in"] == "query"
            ],
            # The bodies and responses are FastAPI's job, the gateway passes them on
            "responses": {"200": {"description": "The response from FastAPI"}},
            "x-amazon-apigateway-integration": {
                # http_proxy: send the request (headers, query string, body) to
                # FastAPI unchanged, and return FastAPI's response unchanged
                "type": "http_proxy",
                "httpMethod": method.upper(),
                "uri": backend + path,
                "passthroughBehavior": "when_no_match",
                # The most API Gateway waits, 29 seconds
                "timeoutInMillis": 29000,
            },
        }

gateway_spec = {
    "openapi": "3.0.1",
    "info": {
        "title": fastapi_spec["info"]["title"],
        "version": fastapi_spec["info"]["version"],
    },
    "paths": paths,
}

with open("apigateway.json", "w") as file:
    json.dump(gateway_spec, file, indent=2)

count = sum(len(operations) for operations in paths.values())
print(f"apigateway.json: {count} endpoints, sent to {backend}")
```

- **`http_proxy`** integration: API Gateway forwards the request (method, headers including `Authorization`, query string, body) to the URL, and returns the answer unchanged. FastAPI keeps doing validation and auth. The other type, `http`, lets you transform requests and responses with mapping templates; we don't need that.
- **The schemas are left out on purpose.** API Gateway uses them for request validation and SDK generation, and it can't read many 3.1 features (`anyOf` with `null`, `examples`...). FastAPI validates anyway.
- **Query parameters are declared** (name, required, type) because API Gateway's cache can only use **declared** parameters in its cache key (10.9).
- **Only tagged endpoints**: the practice routes like `/time` and `/custom` stay private.

Add `apigateway.json` to `.gitignore` (it's generated, and it contains your Render address):

```text
# Generated by scripts/openapi_to_apigateway.py
apigateway.json
```

Wake the Render API first (open its `/health`; a sleeping free service takes about a minute), then:

```bash
python scripts/openapi_to_apigateway.py https://fastship-api.onrender.com
```

Expected: `apigateway.json: 23 endpoints, sent to https://fastship-api.onrender.com`.

### Import it

Console → **API Gateway** → **Create API** → **REST API** (not "HTTP API", see the box below) → **Import API** → choose `apigateway.json` → **API endpoint type: Regional** → **Create API**.

**Resources** shows the tree it made: `/partner`, `/seller/me`, `/shipment`, `/shipment/track`, `/tag`... each with its methods.

### Look at an integration, and edit one

Click **GET** under `/shipment/track`. The diagram shows the four stages of every request:

```
Method request  ─►  Integration request  ─►  (Render)  ─►  Integration response  ─►  Method response
(what the client    (where and how API                     (what came back)          (what the client
 must send)          Gateway calls the backend)                                        gets)
```

Open **Integration request**: type **HTTP**, **HTTP proxy integration: on**, method GET, endpoint URL `https://fastship-api.onrender.com/shipment/track`. That's the `x-amazon-apigateway-integration` block from the file.

This is where the course "edits the integration". **Edit** lets you change the endpoint URL, the method or the timeout. Try changing the timeout to `10000` (10 s) and save. In real life you'd edit an integration when a backend moves; then you'd regenerate the file with the new URL and re-import it (**Import API** → **Overwrite**) instead of clicking through 23 endpoints.

**Test** (the tab on the method): query string `id=<a shipment id from Render>` → **Test** → status 200, the HTML page, and the full log of what API Gateway did. The console test doesn't need a deployed stage.

> **REST API or HTTP API?** API Gateway has two products. **HTTP API** is newer, cheaper and simpler, but has **no cache, no usage plans and no API keys**. **REST API** has all of them. The course and this guide use REST API, because of caching and throttling per client.

### Deploy a stage

Changes go live only when **deployed** to a **stage**. **Deploy API** → Stage: **New stage** → name `prod` → **Deploy**. You get an **Invoke URL** like `https://a1b2c3d4e5.execute-api.eu-central-1.amazonaws.com/prod`.

```bash
GW=https://a1b2c3d4e5.execute-api.eu-central-1.amazonaws.com/prod   # yours

curl -s $GW/tag | head -c 200; echo
curl -s -X POST $GW/seller/token -d 'username=you@example.com&password=yourpassword'
TOKEN=paste_the_access_token
curl -s $GW/seller/me -H "Authorization: Bearer $TOKEN"
curl -s -D - -o /dev/null "$GW/seller/shipments?limit=1" -H "Authorization: Bearer $TOKEN" | grep -i total
```

- **No trailing `/`**: on the gateway it's `/tag`; the gateway calls FastAPI's `/tag/`.
- The `Authorization` header and the query string pass through unchanged; `x-total-count` comes back.
- If Render is asleep, the first call may fail with `504` after 29 seconds (the gateway's limit). Call again after a minute.

## 10.8 Throttling

**Stages** → `prod` → **Stage details** → **Edit** → **Throttling**: on, **Rate** `2`, **Burst** `4` → **Save**.

- **Rate**: requests per second on average. **Burst**: how many can arrive at the same instant. (It's a "token bucket": the bucket holds 4 tokens, refills at 2 per second, each request takes one.)

```bash
seq 20 | xargs -P 10 -I{} curl -s -o /dev/null -w "%{http_code}\n" $GW/tag | sort | uniq -c
```

`seq 20` prints 1 to 20, `xargs -P 10` runs 10 `curl`s at the same time, `sort | uniq -c` counts each status code. Expected: a few `200` and many `429 Too Many Requests`. The rejected requests never reached Render.

Set the rate back to something sensible (e.g. 50 / 100) afterwards.

> **Per-client limits**: **Usage plans** + **API keys** give each client its own rate and monthly quota (clients send `x-api-key`). Same menu area, worth a look; not needed for FastShip.

## 10.9 Optional: the cache (about $0.02 an hour)

**Skip this if you want zero use of credits.** It's paid by the hour from the moment it's created until you delete it, and it's billed from your credits, never your card while you're on the Free plan.

**Caching an API is dangerous if done carelessly**, and this is the real lesson. API Gateway's cache key is the path plus the parameters **you mark as keys**. The `Authorization` header is not part of it unless you add it. Enable caching on `GET /seller/me` and the **first** seller's profile is served to **every** seller for 5 minutes, a data leak. And on `GET /shipment` without `id` in the key, every shipment id gets the first shipment's answer.

Safe rule: **cache only public `GET`s, and put every parameter that changes the answer in the cache key.** In FastShip that's `GET /shipment?id=` and `GET /shipment/track?id=`.

1. **Stages** → `prod` → **Edit** → **Cache settings**: **Provision API cache** on, capacity **0.5 GB**, TTL `60` seconds. Save. Creating the cache takes a few minutes; status changes to **Available**.
2. In the stage editor, the cache may be turned on for **all** GET methods. **Turn it off for every method except `GET /shipment` and `GET /shipment/track`**: select each method under the stage → **Override settings** → **Cache**. Check `/seller/me`, `/seller/shipments`, `/partner/me`, `/partner/shipments` and `/tag/shipments` especially.
3. **Resources** → `/shipment` → **GET** → **Method request** → **Edit** → URL query string parameters → `id` → check **Caching** → save. Do the same for `/shipment/track`. Now each `id` has its own cache entry.
4. **Deploy API** to `prod` again (resource changes need a deploy).

See it work:

```bash
ID=a_shipment_id
curl -s "$GW/shipment?id=$ID" | grep -o '"status":"[a-z_]*"'
# as the partner, change the status through Render directly (Scalar), then within 60 s:
curl -s "$GW/shipment?id=$ID" | grep -o '"status":"[a-z_]*"'   # the OLD status: from the cache
# after 60 seconds:
curl -s "$GW/shipment?id=$ID" | grep -o '"status":"[a-z_]*"'   # the new one
```

That's the price of caching: **stale data** for up to the TTL. Pick TTLs the business can accept.

**Then delete the cache**: **Stages** → `prod` → **Edit** → **Provision API cache** off → save. Check that the status shows no cache.

> For FastShip itself I wouldn't use the gateway cache: almost everything is per user. Caching inside the app, with Redis keyed by user, is the usual choice for that.

## 10.10 Optional: gateway logs in CloudWatch (an IAM role in practice)

API Gateway needs **permission** to write logs to CloudWatch, and that permission is given through a **role**, the standard AWS pattern ("this service may do that").

1. **IAM** → **Roles** → **Create role** → **AWS service** → use case **API Gateway** → it suggests the policy `AmazonAPIGatewayPushToCloudWatchLogs` → name `APIGatewayCloudWatchLogs` → create → copy its **ARN**.
2. **API Gateway** → **Settings** (left menu, for the whole account in this region) → **Logging** → **Edit** → paste the ARN → save.
3. **Stages** → `prod` → **Logs and tracing** → **Edit** → CloudWatch logs: **Errors and info logs** → save. Leave **Data tracing** off: it logs full request and response bodies, which means tokens and personal data.
4. Call the API a few times, then **CloudWatch** → **Log groups** → `API-Gateway-Execution-Logs_<id>/prod`.

## 10.11 Clean up

When you're done learning:

1. **API Gateway** → **APIs** → select `FastShip API` → **Delete** (this deletes its stages and any cache).
2. **ECR** → `fastship-api` → **Delete** (type `delete`).
3. **CloudWatch** → **Log groups** → delete `API-Gateway-Execution-Logs_*` (if you did 10.10).
4. **Billing** → **Free Tier** / **Credits**: check what was used. Expected: a few cents at most.

---
# Part 11: What was tested, and what couldn't be

Everything was built in a copy of your project, on your Mac, with your Docker Desktop.

**Tested and passing**
- **Tests**: 95 passed (79 existing + 12 pagination + 4 telemetry). Ruff and Mypy clean.
- **Pagination**: page sizes, offsets, total header, sorting, invalid values (422), the CORS header, the docs. Rows read with 500 shipments, before and after the `lazy="raise"` change (1.8).
- **Images**: the naive build (2.22 GB, `.env` inside) and the slim one (572 MB, about 650 MB with telemetry; about 110 MB to download), running as `fastship`, no `.env` inside. Build context 750 MB → 7 KB. A code change rebuilds from the cache.
- **`docker run`**: `/health` and `/scalar` work; the database fails with `localhost` as expected; `host.docker.internal` reaches your Homebrew Postgres and Redis. `--env-file` keeping the quotes: confirmed.
- **Bridge network**: Postgres 18 + Redis + migrations with the same image + the API, by container name; signup, login, the `X-Total-Count` header; shipment creation without RabbitMQ: 201 in 0.09 s, error logged.
- **Compose** (all services): start order and health checks; then **13 end-to-end checks through the nginx container**: index.html, the React-route fallback, asset caching, the `/api` proxy, signup of both roles, 3 shipments, pagination + sorting through nginx, the worker's 3 "Shipped" emails, out for delivery, the email with the code **and the inline QR image**, delivery verified with the emailed code. (Emails went to a local test mail server, not Gmail.) Beat started. Data survived `down` + `up`. `migrate` re-ran safely.
- **The frontend container in Google Chrome**: login, dashboard, reloading a deep link, no console errors.
- **Multi-platform**: built `linux/amd64` + `linux/arm64`, both variants start (`x86_64` and `aarch64`), pushed both to a temporary local registry.
- **Render simulation**: the exact Docker Command and the `render.env.example` values (local container hostnames instead of Render's): migrations then the server, `exec` leaves only `fastapi` running, `https` redirects behind a proxy, CORS for the static site's origin only, shipments without RabbitMQ. The template starts the image in production mode.
- **Migrations through environment variables** (8.5), against the Compose database.
- **Telemetry**: request spans with `request_id`; SQL spans with SQLAlchemy 2.1 (`skip_dep_check`); no `/health` spans; no email or password in any span; **one trace from the API into the worker** (sent to a local OTLP receiver from the containers); a fake outside `traceparent` ignored; the Logfire warning gone.
- **The API Gateway file**: generated from the running API, valid OpenAPI 3.0.1, no path ending in `/`, all path segments allowed by AWS's rules, 23 endpoints.
- **The commands**: the `requirements-dev.txt` and `pip freeze --exclude` commands; the `.env` quote removal on a copy of your `.env` (same values, no quotes; your real `.env` was not touched).

**Not tested, because they need your accounts**
- Render's website (8.2 to 8.10): creating the services, "Add from .env", the static site build and rewrite rule.
- Docker Hub push to your account (tested with a local registry instead).
- Logfire's website and a real token (tested with Logfire's test exporter and a local OTLP receiver).
- AWS: account, IAM, `aws login`, the ECR push, the API Gateway import, throttling, cache, logs.
- Real Gmail delivery from the worker container, and a real phone camera on the Render site.

---

# Part 12: Best practices you used

**Images**
- Slim base, pinned major versions (`python:3.14-slim`, `postgres:18-alpine`), not `latest`.
- `.dockerignore` keeps secrets and junk out; `COPY` only what runs.
- Dependencies before code, for layer caching.
- A non-root user; code owned by root.
- Exec form `CMD`; `exec` in shell wrappers.
- One image, many commands (API, worker, beat, migrations).
- Multi-stage when the build needs tools the runtime doesn't (the frontend).
- Version tags, immutable in the registry. Multi-platform images.

**Configuration and secrets**
- Settings from environment variables (twelve-factor); `.env` only on your machine.
- Different secrets per environment; a server gets only the secrets it uses (no Gmail or Twilio on Render).
- Never in an image, never in git, never in `VITE_` variables, never in telemetry.

**Running**
- Health checks; `depends_on` with conditions; migrations before the app, and a failed migration stops the start.
- Only publish the ports you need, bound to `127.0.0.1` for tools.
- Logs on stdout; no files in containers.
- Trust proxy headers only behind a proxy (`--forwarded-allow-ips`).
- Named volumes for data; `down -v` only on purpose.

**APIs**
- Paginate every list; cap the page size; whitelist sort fields; a unique tie-breaker for stable pages.
- Check what the ORM loads, not just the SQL you wrote (`lazy="selectin"` vs `"raise"`).
- Document headers in OpenAPI; expose them with CORS.
- Cache only public data, with every input in the cache key.

**Observability**
- Traces over guesswork: instrument HTTP, database, cache and queue.
- Request IDs in responses, logs and spans.
- Decide what leaves the server, and test it.
- Don't trust trace context from the internet.

---

# Part 13: Interview questions

**Docker**
1. *Image vs container?* An image is a read-only template; a container is a running instance of it, with its own writable layer, processes and network.
2. *Why copy `requirements.txt` before the code?* Layer caching: Docker reuses a layer whose instruction and input files didn't change, so a code change doesn't reinstall packages.
3. *CMD vs ENTRYPOINT?* CMD is the default command and is replaced by arguments to `docker run`; ENTRYPOINT is the fixed program, and CMD becomes its default arguments.
4. *Exec form vs shell form?* Exec form runs the program as PID 1, so it receives SIGTERM and can shut down cleanly; shell form runs `sh -c`, which doesn't forward signals.
5. *Why run as non-root?* To limit what an attacker can do after exploiting the app: no changing system files or the code, no installing tools.
6. *What does `EXPOSE` do?* Only documents the port; `-p` publishes it.
7. *How do containers on a user-defined bridge network find each other?* Docker's embedded DNS resolves container (or Compose service) names.
8. *Volume vs bind mount?* A volume is managed by Docker and survives the container; a bind mount maps a host folder, good for development, tied to the host's file layout.
9. *What is a multi-stage build for?* Building with heavy tools in one stage and shipping only the results in a small final stage.
10. *Why `slim` and not `alpine` for Python?* Alpine uses musl libc, many wheels are built for glibc, so pip compiles from source: slower builds, needs compilers, sometimes subtle bugs.
11. *`depends_on` alone vs with `condition: service_healthy`?* Alone it only orders container starts; with the condition it waits for the health check to pass.
12. *Why can't an ARM image run on Render?* The binaries inside are compiled for one CPU architecture; build for `linux/amd64` or a multi-platform image.

**Deployment**
13. *How do you run migrations in a deployment?* As a separate step before the new version takes traffic: a pre-deploy job, a one-off container, or the start command with `&&` on single-instance setups. Never in parallel from many instances without a lock.
14. *What is a health check, and what should it check?* An endpoint the platform polls to decide whether to route traffic or restart. Liveness checks only the process; readiness may check dependencies, carefully, so a slow database doesn't cause restart loops.
15. *Why `X-Forwarded-Proto`?* TLS ends at the proxy; the app sees plain HTTP unless it trusts the proxy's header.
16. *Why can a static site and an API need CORS?* They are different origins (scheme + host + port); the browser blocks cross-origin JavaScript calls unless the API allows the origin.

**Pagination**
17. *Offset vs cursor pagination?* Offset is simple and can jump to any page, but gets slow at large offsets and can skip or repeat rows when data changes; cursor (keyset) is fast and stable but only goes next/previous.
18. *Why add `id` to the `ORDER BY`?* Rows with equal sort values have no guaranteed order; a unique tie-breaker makes pages stable.
19. *Body envelope vs `X-Total-Count`?* Both are common; the header keeps the body a plain list (backwards compatible), the envelope is easier to read and to add fields to.
20. *Why can an endpoint with `LIMIT 10` still be slow?* The ORM may eager-load relationships (`selectin`) far beyond the 10 rows, or the count query may be slow.

**Observability**
21. *Logs, metrics, traces?* Events, numbers over time, request paths with timings.
22. *What is a span? Context propagation?* A timed operation with attributes; propagation carries the trace ID across processes (HTTP `traceparent` header, message headers) so spans join one trace.
23. *OpenTelemetry vs Logfire?* OTel is the vendor-neutral standard and SDK; Logfire is one backend and a thin SDK on top of it.
24. *What must never go into telemetry?* Secrets, tokens, passwords and personal data, unless you have explicitly decided to and are allowed to.

**API Gateway**
25. *Why use an API gateway?* Throttling, API keys and quotas, caching, auth at the edge, one entry point for many backends, monitoring, stages.
26. *Throttling rate vs burst?* A token bucket: burst is the bucket size (requests at once), rate is the refill speed (requests per second).
27. *What's the risk with response caching?* Serving one user's data to another if the cache key misses something that changes the response (the `Authorization` header, an `id`); stale data up to the TTL.
28. *REST API vs HTTP API in API Gateway?* REST: caching, usage plans, API keys, request validation, more features; HTTP: cheaper, faster and simpler, with fewer features.

---

# Part 14: When you're done

1. Tell me which parts you finished. As before, I'll test **your** version: `pytest`, Ruff, Mypy, image builds, Compose, the end-to-end flow, and the frontend container in Chrome.
2. Then, when you say so, I'll commit and push. These files are new and will go into git: `Dockerfile`, `.dockerignore`, `compose.yaml`, `requirements-dev.txt`, `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/nginx.conf`, `scripts/openapi_to_apigateway.py`, `app/core/telemetry.py`, `app/services/pagination.py`, and the two new test files. These **never** go into git: `.env`, `.env.backup`, `render.env`, `apigateway.json`.
3. Delete `.env.backup` once Compose works.
4. Remember the free limits: the Render database is deleted 30 + 14 days after you create it, and the AWS Free plan ends after 6 months. Delete anything on AWS you no longer use (10.11).

Good next steps, when you want them:
- The partner-side fix from 1.8 (count active shipments with SQL).
- The React dashboard reading `X-Total-Count` with page buttons (when we learn React).
- A CI pipeline (GitHub Actions): run the tests, build the multi-platform image, push it, call Render's deploy hook.
- `uv` with a lock file instead of `pip freeze`.

---

## Sources

- AWS App Runner availability change: https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html
- AWS Free Tier and the Free plan: https://aws.amazon.com/free/ and https://aws.amazon.com/free/free-tier-faqs/
- API Gateway pricing (free tier, cache prices): https://aws.amazon.com/api-gateway/pricing/
- ECR pricing: https://aws.amazon.com/ecr/pricing/
- API Gateway OpenAPI import rules: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-known-issues.html
- `x-amazon-apigateway-integration`: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration.html
- ECS Express Mode: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html
- `aws login`: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html
- Render free instances: https://render.com/docs/free
- Render, deploy a prebuilt image: https://render.com/docs/deploying-an-image
- Render Docker Command: https://render.com/docs/docker
- Render web services and `PORT`: https://render.com/docs/web-services
- Render Postgres connections: https://render.com/docs/postgresql-creating-connecting
- Render Key Value: https://render.com/docs/key-value
- Render environment variables (Add from .env): https://render.com/docs/configure-environment-variables
- Render redirects and rewrites: https://render.com/docs/redirects-rewrites
- Render Node version: https://render.com/docs/node-version
- Logfire pricing: https://pydantic.dev/pricing
- Logfire FastAPI, Celery and logging integrations: https://pydantic.dev/docs/logfire/integrations/web-frameworks/fastapi/, https://pydantic.dev/docs/logfire/integrations/event-streams/celery/, https://pydantic.dev/docs/logfire/integrations/logging/logging/
