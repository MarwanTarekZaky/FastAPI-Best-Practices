import logging
from collections.abc import AsyncIterator

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlmodel import SQLModel

from app.api.schemas.delivery_partner import DeliveryPartnerCreate
from app.api.schemas.seller import SellerCreate
from app.config import db_settings
from app.database import redis
from app.database.models import DeliveryPartner, Seller, Tag, TagName
from app.database.session import get_session
from app.main import app
from app.services.delivery_partner import DeliveryPartnerService
from app.services.notification import NotificationService
from app.services.seller import SellerService
from app.services.user import password_context
from tests.helpers import PASSWORD, ZIP_CODE, login

# Keep test requests out of logs/requests.log
logging.getLogger("fastship.requests").disabled = True

# Same server as the app, but a separate database, so tests never touch real data
TEST_DATABASE_URL = make_url(db_settings.POSTGRES_URL).set(
    database="fastship_test"
)


### Database


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    # Runs once for the whole test run: fresh tables and the predefined tags
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)
        await connection.run_sync(SQLModel.metadata.create_all)

    # The migration adds the tags in the real database, here we add them ourselves
    async with AsyncSession(engine) as session:
        for name in TagName:
            session.add(Tag(name=name, instruction=f"{name.value} instruction"))  # type: ignore[call-arg]
        await session.commit()

    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    # Each test runs inside one transaction that is rolled back at the end,
    # so every test starts with an empty database (except the tags)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        yield connection
        await transaction.rollback()


def _make_session(connection: AsyncConnection) -> AsyncSession:
    # commit() in the app only saves a savepoint, the test's rollback still undoes it
    return AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture
async def session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    # For tests that use the database or the services directly
    async with _make_session(connection) as session:
        yield session


### Fakes for outside services


@pytest.fixture(autouse=True, scope="session")
def fast_password_hashing():
    # bcrypt is slow on purpose, the lowest cost keeps the tests fast
    password_context.update(bcrypt__rounds=4)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch):
    # autouse: every test gets a new, empty, in-memory Redis
    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        redis, "_token_blacklist", fakeredis.FakeAsyncRedis(server=server)
    )
    monkeypatch.setattr(
        redis,
        "_verification",
        fakeredis.FakeAsyncRedis(server=server, decode_responses=True),
    )
    monkeypatch.setattr(
        redis,
        "_verification_sync",
        fakeredis.FakeRedis(server=server, decode_responses=True),
    )


@pytest.fixture(autouse=True)
def queued_tasks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    # No emails or SMS from tests: Celery tasks are recorded here instead of sent
    queued: list[tuple[str, dict]] = []

    def fake_enqueue(self, task, **kwargs):
        queued.append((task.name.split(".")[-1], kwargs))

    monkeypatch.setattr(NotificationService, "_enqueue", fake_enqueue)
    return queued


### HTTP client


@pytest.fixture
async def client(connection: AsyncConnection) -> AsyncIterator[AsyncClient]:
    # Each request gets its own session, like in the real app,
    # but on the test's connection so the rollback undoes everything
    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with _make_session(connection) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    # Calls the app directly in memory, no server needed
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


### Users and shipments


@pytest.fixture
def make_seller(session: AsyncSession):
    # A fixture that returns a function: tests can create as many sellers as needed
    async def make(email: str = "seller@example.com") -> Seller:
        return await SellerService(session).add(
            SellerCreate(
                name="Seller", email=email, password=PASSWORD, zip_code=ZIP_CODE
            )
        )

    return make


@pytest.fixture
async def seller(make_seller) -> Seller:
    return await make_seller()


@pytest.fixture
async def seller_headers(client: AsyncClient, seller: Seller) -> dict[str, str]:
    return await login(client, "seller", seller.email)


@pytest.fixture
async def partner(session: AsyncSession) -> DeliveryPartner:
    return await DeliveryPartnerService(session).add(
        DeliveryPartnerCreate(
            name="Partner",
            email="partner@example.com",
            password=PASSWORD,
            serviceable_zip_codes=[ZIP_CODE],
            max_handling_capacity=2,
        )
    )


@pytest.fixture
async def partner_headers(
    client: AsyncClient, partner: DeliveryPartner
) -> dict[str, str]:
    return await login(client, "partner", partner.email)


@pytest.fixture
def shipment_data() -> dict:
    return {
        "content": "Glass vase",
        "weight": 2.5,
        "destination": ZIP_CODE,
        "client_contact_email": "client@example.com",
    }


@pytest.fixture
async def shipment(
    client: AsyncClient,
    seller_headers: dict[str, str],
    partner: DeliveryPartner,
    shipment_data: dict,
) -> dict:
    # A shipment created by `seller` and assigned to `partner`
    response = await client.post(
        "/shipment/", json=shipment_data, headers=seller_headers
    )
    return response.json()
