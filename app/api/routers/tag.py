from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.database.models import TagName

from ..dependencies import SellerDep, TagServiceDep
from ..docs import TOTAL_COUNT, errors
from ..schemas.shipment import ShipmentListParams, ShipmentRead, TagRead

router = APIRouter(prefix="/tag", tags=["Tag"])


@router.get(
    "/",
    response_model=list[TagRead],
    summary="List all tags",
)
async def get_tags(service: TagServiceDep):
    """Every tag a seller can add, with its handling instruction."""
    return await service.get_all()


@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="My shipments with a tag",
    responses={**TOTAL_COUNT, **errors(401)},
)
async def get_shipments_by_tag(
    tag_name: TagName,
    seller: SellerDep,
    service: TagServiceDep,
    params: Annotated[ShipmentListParams, Query()],
    response: Response,
):
    """One page of the logged in seller's shipments that have this tag."""
    shipments, total = await service.get_shipments(tag_name, seller, params)
    response.headers["X-Total-Count"] = str(total)
    return shipments
