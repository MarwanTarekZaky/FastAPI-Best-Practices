from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.exceptions import EntityNotFound, InvalidInput
from app.database.models import TagName
from app.utils import TEMPLATE_DIR

from ..dependencies import DeliveryPartnerDep, SellerDep, ShipmentServiceDep
from ..docs import SHIPMENT_EXAMPLES, errors
from ..schemas.common import Message
from ..schemas.shipment import (
    ShipmentCreate,
    ShipmentRead,
    ShipmentUpdate,
    ShipmentVerify,
)

router = APIRouter(prefix="/shipment", tags=["Shipment"])

templates = Jinja2Templates(TEMPLATE_DIR)

# Every endpoint takes the id the same way, so it's described once here
ShipmentId = Annotated[
    UUID,
    Query(description="The shipment's id, returned when it was created"),
]


@router.get(
    "/",
    response_model=ShipmentRead,
    summary="Get a shipment",
    responses=errors(404),
)
async def get_shipment(id: ShipmentId, service: ShipmentServiceDep):
    """Anyone with the id can read the shipment, like a tracking number."""
    shipment = await service.get(id)

    if shipment is None:
        raise EntityNotFound("Shipment not found")

    return shipment


@router.get(
    "/track",
    response_class=HTMLResponse,
    summary="Tracking page",
    responses=errors(404),
)
async def get_tracking(
    request: Request,
    id: ShipmentId,
    service: ShipmentServiceDep,
):
    """The HTML page the client opens from the link in their email."""
    shipment = await service.get(id)

    if shipment is None:
        raise EntityNotFound("Shipment not found")

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


@router.post(
    "/",
    response_model=ShipmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shipment",
    response_description="The new shipment",
    responses=errors(401, 409),
)
async def submit_shipment(
    seller: SellerDep,
    shipment: Annotated[ShipmentCreate, Body(openapi_examples=SHIPMENT_EXAMPLES)],
    service: ShipmentServiceDep,
):
    """
    The seller creates a shipment. A delivery partner who serves the destination
    zip code is assigned, and the client gets an email with the tracking link.

    Fails with **409** if no partner serves that zip code or all are full.
    """
    return await service.add(shipment, seller)


@router.patch(
    "/",
    response_model=ShipmentRead,
    summary="Update a shipment's progress",
    responses=errors(400, 401, 403, 404, 409),
)
async def update_shipment(
    id: ShipmentId,
    shipment_update: ShipmentUpdate,
    service: ShipmentServiceDep,
    partner: DeliveryPartnerDep,
):
    """The assigned partner adds a new event: location, status or note."""
    # Update data with given fields
    update = shipment_update.model_dump(exclude_none=True)

    if not update:
        raise InvalidInput("No data provided to update")

    return await service.update(id, shipment_update, partner)


@router.post(
    "/verify",
    response_model=ShipmentRead,
    summary="Confirm delivery",
    responses=errors(400, 401, 403, 404, 409, 429),
)
async def verify_delivery(
    id: ShipmentId,
    verification: ShipmentVerify,
    service: ShipmentServiceDep,
    partner: DeliveryPartnerDep,
):
    """
    The partner enters the code the client received, which marks the shipment
    as delivered. After 5 wrong codes, a new code must be requested.
    """
    return await service.verify_delivery(id, verification.code, partner)


@router.post(
    "/resend-code",
    response_model=Message,
    summary="Send the client a new code",
    responses=errors(401, 403, 404, 409, 429),
)
async def resend_verification_code(
    id: ShipmentId,
    service: ShipmentServiceDep,
    partner: DeliveryPartnerDep,
):
    """The old code stops working. Can be called once a minute."""
    await service.resend_verification_code(id, partner)
    return {"detail": "A new code was sent to the client"}


@router.post(
    "/cancel",
    response_model=ShipmentRead,
    summary="Cancel a shipment",
    responses=errors(401, 403, 404, 409),
)
async def cancel_shipment(
    id: ShipmentId,
    seller: SellerDep,
    service: ShipmentServiceDep,
):
    """The seller cancels their shipment, if it isn't delivered yet."""
    return await service.cancel(id, seller)


@router.get(
    "/cancel",
    response_model=ShipmentRead,
    summary="Cancel a shipment (old)",
    responses=errors(401, 403, 404, 409),
    deprecated=True,
)
async def cancel_shipment_old(
    id: ShipmentId,
    seller: SellerDep,
    service: ShipmentServiceDep,
):
    """
    **Use `POST /shipment/cancel` instead.** A GET request must not change data,
    browsers and tools may call it on their own. Kept so old clients still work.
    """
    return await service.cancel(id, seller)


@router.post(
    "/tag",
    response_model=ShipmentRead,
    summary="Add a tag",
    responses=errors(401, 403, 404, 409),
)
async def add_tag(
    id: ShipmentId,
    tag_name: TagName,
    seller: SellerDep,
    service: ShipmentServiceDep,
):
    """The seller adds a predefined tag, see `GET /tag/` for the list."""
    return await service.add_tag(id, tag_name, seller)


@router.delete(
    "/tag",
    response_model=ShipmentRead,
    summary="Remove a tag",
    responses=errors(401, 403, 404, 409),
)
async def remove_tag(
    id: ShipmentId,
    tag_name: TagName,
    seller: SellerDep,
    service: ShipmentServiceDep,
):
    """The tag stays in the list, it's only removed from this shipment."""
    return await service.remove_tag(id, tag_name, seller)
