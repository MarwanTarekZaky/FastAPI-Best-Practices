import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from app.database.models import Shipment  # noqa: F401
from app.database.session import get_session
from app.main import app


### Test client with a fresh in-memory database for each test
@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    # Use the test database instead of sqlite.db
    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def create_shipment(client: TestClient) -> int:
    response = client.post(
        "/shipment",
        json={"content": "steel rods", "weight": 14.7, "destination": 11003},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_create_and_get_shipment(client):
    id = create_shipment(client)

    response = client.get("/shipment", params={"id": id})

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "steel rods"
    assert data["weight"] == 14.7
    assert data["destination"] == 11003
    assert data["status"] == "placed"
    assert "estimated_delivery" in data


def test_create_gives_new_ids(client):
    assert create_shipment(client) != create_shipment(client)


def test_create_rejects_heavy_shipment(client):
    response = client.post(
        "/shipment",
        json={"content": "anvil", "weight": 30, "destination": 11003},
    )
    assert response.status_code == 422


def test_get_missing_shipment(client):
    response = client.get("/shipment", params={"id": 999})
    assert response.status_code == 404


def test_update_shipment(client):
    id = create_shipment(client)

    response = client.patch(
        "/shipment", params={"id": id}, json={"status": "in_transit"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_transit"
    assert client.get("/shipment", params={"id": id}).json()["status"] == "in_transit"


def test_update_with_empty_body(client):
    id = create_shipment(client)
    response = client.patch("/shipment", params={"id": id}, json={})
    assert response.status_code == 400


def test_update_with_invalid_status(client):
    id = create_shipment(client)
    response = client.patch("/shipment", params={"id": id}, json={"status": "lost"})
    assert response.status_code == 422


def test_update_missing_shipment(client):
    response = client.patch(
        "/shipment", params={"id": 999}, json={"status": "delivered"}
    )
    assert response.status_code == 404


def test_delete_shipment(client):
    id = create_shipment(client)

    response = client.delete("/shipment", params={"id": id})

    assert response.status_code == 200
    assert client.get("/shipment", params={"id": id}).status_code == 404


def test_delete_missing_shipment(client):
    response = client.delete("/shipment", params={"id": 999})
    assert response.status_code == 404


def test_scalar_docs(client):
    assert client.get("/scalar").status_code == 200


def test_update_estimated_delivery(client):
    id = create_shipment(client)

    response = client.patch(
        "/shipment",
        params={"id": id},
        json={"estimated_delivery": "2026-11-01T10:00:00"},
    )

    assert response.status_code == 200
    assert response.json()["estimated_delivery"] == "2026-11-01T10:00:00"
