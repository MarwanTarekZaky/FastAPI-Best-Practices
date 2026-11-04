from fastapi import APIRouter

from app.database.models import TagName

from ..dependencies import SellerDep, TagServiceDep
from ..docs import errors
from ..schemas.shipment import ShipmentRead, TagRead

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
    responses=errors(401),
)
async def get_shipments_by_tag(
    tag_name: TagName,
    seller: SellerDep,
    service: TagServiceDep,
):
    """The logged in seller's shipments that have this tag, newest first."""
    return await service.get_shipments(tag_name, seller)
