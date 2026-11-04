from uuid import uuid4

from httpx import AsyncClient

from tests.helpers import login


async def test_create_shipment(
    client: AsyncClient, seller_headers, partner, shipment_data, queued_tasks
):
    response = await client.post(
        "/shipment/", json=shipment_data, headers=seller_headers
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Glass vase"
    assert data["status"] == "placed"
    assert len(data["timeline"]) == 1
    # The client was emailed, through Celery
    assert queued_tasks[0][0] == "send_email_with_template"
    assert queued_tasks[0][1]["recipients"] == ["client@example.com"]


async def test_create_shipment_without_login(client: AsyncClient, shipment_data):
    response = await client.post("/shipment/", json=shipment_data)

    assert response.status_code == 401


async def test_create_shipment_without_partner(
    client: AsyncClient, seller_headers, shipment_data
):
    # No partner fixture, so nobody delivers to this zip code
    response = await client.post(
        "/shipment/", json=shipment_data, headers=seller_headers
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "No delivery partner available"}


async def test_create_shipment_too_heavy(
    client: AsyncClient, seller_headers, partner, shipment_data
):
    response = await client.post(
        "/shipment/",
        json={**shipment_data, "weight": 30},
        headers=seller_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "weight"]


async def test_get_shipment(client: AsyncClient, shipment):
    response = await client.get("/shipment/", params={"id": shipment["id"]})

    assert response.status_code == 200
    assert response.json()["id"] == shipment["id"]


async def test_get_missing_shipment(client: AsyncClient):
    response = await client.get("/shipment/", params={"id": str(uuid4())})

    assert response.status_code == 404
    assert response.json() == {"detail": "Shipment not found"}


async def test_partner_updates_shipment(client: AsyncClient, shipment, partner_headers):
    response = await client.patch(
        "/shipment/",
        params={"id": shipment["id"]},
        json={"status": "in_transit", "location": 11002},
        headers=partner_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_transit"
    assert data["timeline"][-1]["location"] == 11002


async def test_update_with_no_data(client: AsyncClient, shipment, partner_headers):
    response = await client.patch(
        "/shipment/",
        params={"id": shipment["id"]},
        json={},
        headers=partner_headers,
    )

    assert response.status_code == 400


async def test_cancel_shipment(client: AsyncClient, shipment, seller_headers):
    response = await client.post(
        "/shipment/cancel",
        params={"id": shipment["id"]},
        headers=seller_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_cancel_twice(client: AsyncClient, shipment, seller_headers):
    params = {"id": shipment["id"]}
    await client.post("/shipment/cancel", params=params, headers=seller_headers)

    response = await client.post(
        "/shipment/cancel", params=params, headers=seller_headers
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Shipment is already cancelled"}


async def test_other_seller_cant_cancel(client: AsyncClient, shipment, make_seller):
    # Regression test: cancel used to work on any seller's shipment
    other = await make_seller("other@example.com")
    other_headers = await login(client, "seller", other.email)

    response = await client.post(
        "/shipment/cancel",
        params={"id": shipment["id"]},
        headers=other_headers,
    )

    assert response.status_code == 403
    # And the shipment is still active
    response = await client.get("/shipment/", params={"id": shipment["id"]})
    assert response.json()["status"] == "placed"
