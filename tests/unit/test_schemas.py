import pytest
from pydantic import ValidationError

from app.api.schemas.shipment import ShipmentCreate, ShipmentUpdate, ShipmentVerify

VALID = {
    "content": "Glass vase",
    "weight": 2.5,
    "destination": 11001,
    "client_contact_email": "client@example.com",
}


def test_valid_shipment():
    # model_validate checks a dict, the same way FastAPI checks the JSON body
    shipment = ShipmentCreate.model_validate(VALID)

    assert shipment.weight == 2.5
    assert shipment.client_contact_phone is None


@pytest.mark.parametrize("weight", [0.1, 1, 25])
def test_allowed_weights(weight):
    shipment = ShipmentCreate.model_validate({**VALID, "weight": weight})

    assert shipment.weight == weight


@pytest.mark.parametrize("weight", [0, -1, 25.1, 100])
def test_rejected_weights(weight):
    with pytest.raises(ValidationError):
        ShipmentCreate.model_validate({**VALID, "weight": weight})


@pytest.mark.parametrize("phone", ["+201012345678", "+14155550123"])
def test_allowed_phones(phone):
    shipment = ShipmentCreate.model_validate({**VALID, "client_contact_phone": phone})

    assert shipment.client_contact_phone == phone


@pytest.mark.parametrize("phone", ["01012345678", "+0123456789", "+20 101 234", "+2"])
def test_rejected_phones(phone):
    with pytest.raises(ValidationError):
        ShipmentCreate.model_validate({**VALID, "client_contact_phone": phone})


def test_rejected_email():
    with pytest.raises(ValidationError):
        ShipmentCreate.model_validate({**VALID, "client_contact_email": "not-an-email"})


def test_estimated_delivery_needs_a_timezone():
    with pytest.raises(ValidationError):
        ShipmentUpdate.model_validate({"estimated_delivery": "2026-11-07T15:00:00"})

    update = ShipmentUpdate.model_validate(
        {"estimated_delivery": "2026-11-07T15:00:00+02:00"}
    )
    assert update.estimated_delivery is not None


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "12 456"])
def test_rejected_verification_codes(code):
    with pytest.raises(ValidationError):
        ShipmentVerify.model_validate({"code": code})
