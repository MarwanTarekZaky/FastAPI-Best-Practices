from httpx import AsyncClient

from tests.helpers import PASSWORD, login

SELLER = {
    "name": "Cairo Crafts",
    "email": "new@example.com",
    "password": PASSWORD,
    "zip_code": 11001,
}


async def test_seller_signup(client: AsyncClient):
    response = await client.post("/seller/signup", json=SELLER)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == SELLER["email"]
    # Never send the password or its hash back
    assert "password" not in data
    assert "password_hash" not in data


async def test_signup_with_used_email(client: AsyncClient, seller):
    response = await client.post(
        "/seller/signup", json={**SELLER, "email": seller.email}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}


async def test_signup_without_zip_code(client: AsyncClient):
    seller = {key: value for key, value in SELLER.items() if key != "zip_code"}

    response = await client.post("/seller/signup", json=seller)

    assert response.status_code == 422


async def test_login(client: AsyncClient, seller):
    response = await client.post(
        "/seller/token",
        data={"username": seller.email, "password": PASSWORD},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


async def test_login_with_wrong_password(client: AsyncClient, seller):
    response = await client.post(
        "/seller/token",
        data={"username": seller.email, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_login_with_unknown_email(client: AsyncClient):
    response = await client.post(
        "/seller/token",
        data={"username": "nobody@example.com", "password": PASSWORD},
    )

    # Same answer as a wrong password, so nobody can check which emails exist
    assert response.status_code == 401
    assert response.json() == {"detail": "Email or password is incorrect"}


async def test_logout_blocks_the_token(client: AsyncClient, seller_headers):
    response = await client.get("/seller/logout", headers=seller_headers)
    assert response.status_code == 200

    # The same token doesn't work anymore
    response = await client.get("/seller/logout", headers=seller_headers)
    assert response.status_code == 401


async def test_partner_token_is_not_a_seller(client: AsyncClient, partner):
    partner_headers = await login(client, "partner", partner.email)

    response = await client.get(
        "/tag/shipments",
        params={"tag_name": "fragile"},
        headers=partner_headers,
    )

    assert response.status_code == 401


async def test_invalid_token(client: AsyncClient):
    response = await client.get(
        "/seller/logout",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}
