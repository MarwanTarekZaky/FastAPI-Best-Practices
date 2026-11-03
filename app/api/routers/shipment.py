from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.core.exceptions import EntityNotFound, InvalidInput
from app.database.models import TagName
from app.utils import TEMPLATE_DIR

from ..dependencies import DeliveryPartnerDep, SellerDep, ShipmentServiceDep
from ..schemas.shipment import (
    ShipmentCreate,
    ShipmentRead,
    ShipmentUpdate,
    ShipmentVerify,
)

router = APIRouter(prefix="/shipment", tags=["Shipment"])

templates = Jinja2Templates(TEMPLATE_DIR)

### Read a shipment by id
@router.get("/", response_model=ShipmentRead)
async def get_shipment(
    id: UUID,
    service: ShipmentServiceDep,
):
    # Check for shipment with given id
    shipment = await service.get(id)

    if shipment is None:
        raise EntityNotFound("Given id doesn't exist")

    return shipment

@router.get("/track")
async def get_tracking(request: Request, id: UUID, service: ShipmentServiceDep):
    shipment = await service.get(id)

    if shipment is None:
        raise EntityNotFound("Given id doesn't exist")

    context = shipment.model_dump()
    context["status"] = shipment.status
    context["partner"] = shipment.delivery_partner.name
    # Newest event first, a copy so the shipment's own timeline stays in order
    context["timeline"] = shipment.timeline[::-1]

    return templates.TemplateResponse(
        request=request,
        name="track.html",
        context=context,
    )
    
    
### Create a new shipment with content and weight
@router.post("/", response_model=ShipmentRead)
async def submit_shipment(
    seller: SellerDep,
    shipment: ShipmentCreate,
    service: ShipmentServiceDep,
):
    return await service.add(shipment, seller)


### Update fields of a shipment
@router.patch("/", response_model=ShipmentRead)
async def update_shipment(
    id: UUID,
    shipment_update: ShipmentUpdate,
    service: ShipmentServiceDep,
    partner: DeliveryPartnerDep,
):
    # Update data with given fields
    update = shipment_update.model_dump(exclude_none=True)

    if not update:
        raise InvalidInput("No data provided to update")

    return await service.update(id, shipment_update, partner)


### Delivery partner confirms delivery with the client's code
@router.post("/verify", response_model=ShipmentRead)
async def verify_delivery(
    id: UUID,
    verification: ShipmentVerify,
    service: ShipmentServiceDep,
    partner: DeliveryPartnerDep,
):
    return await service.verify_delivery(id, verification.code, partner)


### Send the client a new code
@router.post("/resend-code")
async def resend_verification_code(
    id: UUID,
    service: ShipmentServiceDep,
    partner: DeliveryPartnerDep
) -> dict[str, str]:
    await service.resend_verification_code(id, partner)
    return {"detail": "A new code was sent to the client"}


### Cancel a shipment by id
@router.get("/cancel", response_model=ShipmentRead)
async def cancel_shipment(
    id: UUID,
    seller: SellerDep,
    service: ShipmentServiceDep
):
    return await service.cancel(id, seller)


### Seller adds a predefined tag to their shipment
@router.post("/tag", response_model=ShipmentRead)
async def add_tag(
    id: UUID,
    tag_name: TagName,
    seller: SellerDep,
    service: ShipmentServiceDep,
):
    return await service.add_tag(id, tag_name, seller)


### Seller removes a tag from their shipment
@router.delete("/tag", response_model=ShipmentRead)
async def remove_tag(
    id: UUID,
    tag_name: TagName,
    seller: SellerDep,
    service: ShipmentServiceDep,
):
    return await service.remove_tag(id, tag_name, seller)
