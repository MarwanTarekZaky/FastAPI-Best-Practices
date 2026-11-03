from fastapi import APIRouter

from app.database.models import TagName

from ..dependencies import SellerDep, TagServiceDep
from ..schemas.shipment import ShipmentRead, TagRead

router = APIRouter(prefix="/tag", tags=["Tag"])


### All predefined tags
@router.get("/", response_model=list[TagRead])
async def get_tags(service: TagServiceDep):
    return await service.get_all()


### The logged in seller's shipments that have this tag
@router.get("/shipments", response_model=list[ShipmentRead])
async def get_shipments_by_tag(
    tag_name: TagName,
    seller: SellerDep,
    service: TagServiceDep,
):
    return await service.get_shipments(tag_name, seller)
