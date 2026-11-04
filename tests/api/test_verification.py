import pytest
from httpx import AsyncClient

from app.database.redis import save_verification_code
from app.utils import hash_verification_code

CODE = "123456"


@pytest.fixture
async def out_for_delivery(client: AsyncClient, shipment, partner_headers) -> dict:
    # A shipment on its way to the client, with a code we know
    await client.patch(
        "/shipment/",
        params={"id": shipment["id"]},
        json={"status": "out_for_delivery"},
        headers=partner_headers,
    )
    # The Celery task does this in the real app, with a random code
    save_verification_code(shipment["id"], hash_verification_code(shipment["id"], CODE))
    return shipment


async def verify(client: AsyncClient, shipment: dict, headers: dict, code: str):
    return await client.post(
        "/shipment/verify",
        params={"id": shipment["id"]},
        json={"code": code},
        headers=headers,
    )


async def test_out_for_delivery_sends_a_code(
    client: AsyncClient, shipment, partner_headers, queued_tasks
):
    await client.patch(
        "/shipment/",
        params={"id": shipment["id"]},
        json={"status": "out_for_delivery"},
        headers=partner_headers,
    )

    task_name, arguments = queued_tasks[-1]
    assert task_name == "send_verification_code"
    assert arguments["shipment_id"] == shipment["id"]


async def test_right_code_delivers(
    client: AsyncClient, out_for_delivery, partner_headers
):
    response = await verify(client, out_for_delivery, partner_headers, CODE)

    assert response.status_code == 200
    assert response.json()["status"] == "delivered"


async def test_code_works_only_once(
    client: AsyncClient, out_for_delivery, partner_headers
):
    await verify(client, out_for_delivery, partner_headers, CODE)

    response = await verify(client, out_for_delivery, partner_headers, CODE)

    assert response.status_code == 409


async def test_wrong_code(client: AsyncClient, out_for_delivery, partner_headers):
    response = await verify(client, out_for_delivery, partner_headers, "000000")

    assert response.status_code == 400
    assert response.json() == {"detail": "Wrong code, 4 attempts left"}


async def test_too_many_wrong_codes(
    client: AsyncClient, out_for_delivery, partner_headers
):
    for _ in range(5):
        await verify(client, out_for_delivery, partner_headers, "000000")

    # Even the right code is refused now
    response = await verify(client, out_for_delivery, partner_headers, CODE)

    assert response.status_code == 429


async def test_cant_mark_delivered_without_code(
    client: AsyncClient, out_for_delivery, partner_headers
):
    response = await client.patch(
        "/shipment/",
        params={"id": out_for_delivery["id"]},
        json={"status": "delivered"},
        headers=partner_headers,
    )

    assert response.status_code == 400


async def test_resend_code_once_a_minute(
    client: AsyncClient, out_for_delivery, partner_headers
):
    params = {"id": out_for_delivery["id"]}

    first = await client.post(
        "/shipment/resend-code", params=params, headers=partner_headers
    )
    second = await client.post(
        "/shipment/resend-code", params=params, headers=partner_headers
    )

    assert first.status_code == 200
    assert second.status_code == 429
