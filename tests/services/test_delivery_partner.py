import pytest

from app.core.exceptions import NoPartnerAvailable
from app.database.models import DeliveryPartner, Seller, Shipment
from app.services.delivery_partner import DeliveryPartnerService
from tests.helpers import ZIP_CODE


def new_shipment(seller: Seller, destination: int = ZIP_CODE) -> Shipment:
    return Shipment(  # type: ignore[call-arg]
        content="Box",
        weight=1,
        destination=destination,
        client_contact_email="client@example.com",
        seller_id=seller.id,
    )


async def test_finds_partner_by_zip_code(session, partner: DeliveryPartner):
    service = DeliveryPartnerService(session)

    assert await service.get_partner_by_zipcode(ZIP_CODE) == [partner]
    assert await service.get_partner_by_zipcode(99999) == []


async def test_assigns_partner_who_serves_the_zip_code(
    session, seller: Seller, partner: DeliveryPartner
):
    shipment = new_shipment(seller)

    assigned = await DeliveryPartnerService(session).assign_shipment(shipment)

    assert assigned.id == partner.id


async def test_no_partner_for_unknown_zip_code(session, seller: Seller, partner):
    with pytest.raises(NoPartnerAvailable):
        await DeliveryPartnerService(session).assign_shipment(
            new_shipment(seller, destination=99999)
        )


async def test_full_partner_gets_no_more_shipments(
    session, seller: Seller, partner: DeliveryPartner
):
    service = DeliveryPartnerService(session)
    # The partner fixture can handle 2 shipments at once
    for _ in range(partner.max_handling_capacity):
        await service.assign_shipment(new_shipment(seller))

    with pytest.raises(NoPartnerAvailable):
        await service.assign_shipment(new_shipment(seller))
