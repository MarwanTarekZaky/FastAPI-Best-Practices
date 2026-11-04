from httpx import AsyncClient

# Every test user has this password
PASSWORD = "secret123"
# The partner fixture delivers to this zip code
ZIP_CODE = 11001


async def login(client: AsyncClient, user_type: str, email: str) -> dict[str, str]:
    # user_type is "seller" or "partner", returns the headers for later requests
    response = await client.post(
        f"/{user_type}/token",
        data={"username": email, "password": PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
