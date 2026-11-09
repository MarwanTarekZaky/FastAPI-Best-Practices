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
