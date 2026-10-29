from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.services.shipment import ShipmentService
from app.services.seller import SellerService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_shipment_service(session: SessionDep):
    return ShipmentService(session)

def get_seller_service(session: SessionDep):
    return SellerService(session)


ShipmentServiceDep = Annotated[
    ShipmentService,
    Depends(get_shipment_service)
]


SellerServiceDep = Annotated[
    SellerService,
    Depends(get_seller_service)
]
