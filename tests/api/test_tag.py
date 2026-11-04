from httpx import AsyncClient

from app.database.models import TagName


async def add_tag(client: AsyncClient, shipment: dict, headers: dict, tag_name: str):
    return await client.post(
        "/shipment/tag",
        params={"id": shipment["id"], "tag_name": tag_name},
        headers=headers,
    )


async def test_list_tags(client: AsyncClient):
    response = await client.get("/tag/")

    assert response.status_code == 200
    assert {tag["name"] for tag in response.json()} == {tag.value for tag in TagName}


async def test_add_tag(client: AsyncClient, shipment, seller_headers):
    response = await add_tag(client, shipment, seller_headers, "fragile")

    assert response.status_code == 200
    assert [tag["name"] for tag in response.json()["tags"]] == ["fragile"]


async def test_add_same_tag_twice(client: AsyncClient, shipment, seller_headers):
    await add_tag(client, shipment, seller_headers, "fragile")

    response = await add_tag(client, shipment, seller_headers, "fragile")

    assert response.status_code == 409


async def test_unknown_tag(client: AsyncClient, shipment, seller_headers):
    response = await add_tag(client, shipment, seller_headers, "explosive")

    assert response.status_code == 422


async def test_remove_tag(client: AsyncClient, shipment, seller_headers):
    await add_tag(client, shipment, seller_headers, "fragile")

    response = await client.delete(
        "/shipment/tag",
        params={"id": shipment["id"], "tag_name": "fragile"},
        headers=seller_headers,
    )

    assert response.status_code == 200
    assert response.json()["tags"] == []


async def test_shipments_by_tag(client: AsyncClient, shipment, seller_headers):
    await add_tag(client, shipment, seller_headers, "gift")

    gift = await client.get(
        "/tag/shipments", params={"tag_name": "gift"}, headers=seller_headers
    )
    fragile = await client.get(
        "/tag/shipments", params={"tag_name": "fragile"}, headers=seller_headers
    )

    assert [s["id"] for s in gift.json()] == [shipment["id"]]
    assert fragile.json() == []
