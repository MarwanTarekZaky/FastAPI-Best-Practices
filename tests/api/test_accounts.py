from httpx import AsyncClient

from tests.helpers import ZIP_CODE, login


async def test_seller_profile(client: AsyncClient, seller, seller_headers):
    response = await client.get("/seller/me", headers=seller_headers)

    assert response.status_code == 200
    assert response.json()["email"] == seller.email


async def test_partner_profile(client: AsyncClient, partner, partner_headers):
    response = await client.get("/partner/me", headers=partner_headers)

    assert response.status_code == 200
    assert response.json()["serviceable_zip_codes"] == [ZIP_CODE]


async def test_profiles_need_login(client: AsyncClient):
    assert (await client.get("/seller/me")).status_code == 401
    assert (await client.get("/partner/me")).status_code == 401


async def test_seller_shipments_newest_first(
    client: AsyncClient, seller_headers, partner, shipment_data
):
    first = await client.post("/shipment/", json=shipment_data, headers=seller_headers)
    second = await client.post("/shipment/", json=shipment_data, headers=seller_headers)

    response = await client.get("/seller/shipments", headers=seller_headers)

    assert response.status_code == 200
    ids = [shipment["id"] for shipment in response.json()]
    assert ids == [second.json()["id"], first.json()["id"]]


async def test_seller_sees_only_own_shipments(
    client: AsyncClient, shipment, make_seller
):
    other = await make_seller("other@example.com")
    other_headers = await login(client, "seller", other.email)

    response = await client.get("/seller/shipments", headers=other_headers)

    assert response.json() == []


async def test_partner_shipments(client: AsyncClient, shipment, partner_headers):
    response = await client.get("/partner/shipments", headers=partner_headers)

    assert response.status_code == 200
    assert [s["id"] for s in response.json()] == [shipment["id"]]
