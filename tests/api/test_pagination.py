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
