from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.shipment import ShipmentCreate
from app.database.models import Seller, Shipment, ShipmentStatus

from .base import BaseService
from .delivery_partner import DeliveryPartnerService


class ShipmentService(BaseService): 
    def __init__(
        self, session: AsyncSession,
        partner_service: DeliveryPartnerService,
    ) -> None:
        super().__init__(Shipment, session)
        self.partner_service = partner_service
    
    async def get(self, id: UUID) -> Shipment | None:
        return await self._get(id)
    
    async def add(self, shipment_create: ShipmentCreate, seller: Seller) -> Shipment:
        new_shipment = Shipment(
            **shipment_create.model_dump(),
            status=ShipmentStatus.placed,
            estimated_delivery=datetime.now(UTC) + timedelta(days=3),
            seller_id=seller.id
        )
        partner = await self.partner_service.assign_shipment(
            new_shipment,
        )
        new_shipment.delivery_partner_id = partner.id
        
        return await self._add(new_shipment)
 
    
    async def update(self, shipment: Shipment) -> Shipment | None:
        return await self._update(shipment)
    
    async def delete(self, shipment: Shipment) -> None:
        await self._delete(shipment)
      
    
    