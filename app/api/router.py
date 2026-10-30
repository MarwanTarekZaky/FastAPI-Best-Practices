from fastapi import APIRouter

from .routers import delivery_partner, seller, shipment

master_router = APIRouter()

master_router.include_router(shipment.router)
master_router.include_router(seller.router)
master_router.include_router(delivery_partner.router)