from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.shipment import ShipmentCreate, ShipmentUpdate
from app.database.models import DeliveryPartner, Seller, Shipment, ShipmentStatus
from app.services.shipment_events import ShipmentEventService

from .base import BaseService
from .delivery_partner import DeliveryPartnerService


class ShipmentService(BaseService): 
    def __init__(
        self, session: AsyncSession,
        partner_service: DeliveryPartnerService,
        event_service: ShipmentEventService,
    ) -> None:
        super().__init__(Shipment, session)
        self.partner_service = partner_service
        self.event_service = event_service
    
    async def get(self, id: UUID) -> Shipment | None:
        return await self._get(id)
    
    async def add(self, shipment_create: ShipmentCreate, seller: Seller) -> Shipment:
        new_shipment = Shipment(
            **shipment_create.model_dump(),
            estimated_delivery=datetime.now(UTC) + timedelta(days=3),
            seller_id=seller.id
        )
        partner = await self.partner_service.assign_shipment(
            new_shipment,
        )
        new_shipment.delivery_partner_id = partner.id
        
        shipment = await self._add(new_shipment)
        
        event = await self.event_service.add(
            shipment=shipment,
            # Sellers created before zip_code was added don't have one
            location=seller.zip_code or shipment.destination,
            status=ShipmentStatus.placed,
            description=f"assigned to {partner.name}"
        )

        shipment.timeline.append(event)
        
        return shipment
    
    async def update(
        self,
        id: UUID,
        shipment_update: ShipmentUpdate,
        partner: DeliveryPartner
    ) -> Shipment | None:
        shipment = await self.get(id)
        if shipment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Given id doesn't exist!",
            )
    
        if shipment.delivery_partner_id != partner.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authorized",
            )
        
        update = shipment_update.model_dump(exclude_none=True)
        estimated_delivery = update.pop("estimated_delivery", None)

        if estimated_delivery is not None:
            shipment.estimated_delivery = estimated_delivery

        # Remaining fields describe a new event in the timeline
        if update:
            await self.event_service.add(
                shipment=shipment,
                **update,
            )
        
        return await self._update(shipment)
    
    async def cancel(self, id: UUID, seller: Seller) -> Shipment:
        shipment = await self.get(id)
        if shipment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Given id doesn't exist!",
            )
            
        if shipment.seller_id != seller.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authorized",
            )
            
        event = await self.event_service.add(
            shipment=shipment,
            status=ShipmentStatus.cancelled
        )
        shipment.timeline.append(event)
        return shipment
            
    async def delete(self, shipment: Shipment) -> None:
        await self._delete(shipment)
      
    
    