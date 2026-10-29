from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.shipment import ShipmentCreate
from app.database.models import Seller, Shipment, ShipmentStatus


class ShipmentService: 
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def get(self, id: UUID) -> Shipment | None:
        return await self.session.get(Shipment, id)
    
    async def add(self, shipment_create: ShipmentCreate, seller: Seller) -> Shipment:
        new_shipment = Shipment(
            **shipment_create.model_dump(),
            status=ShipmentStatus.placed,
            estimated_delivery=datetime.now() + timedelta(days=3),
            seller_id=seller.id
        )
        self.session.add(new_shipment)
        await self.session.commit()
        await self.session.refresh(new_shipment)

        return new_shipment 
    
    async def update(self, id: UUID, shipment_update: dict) -> Shipment | None:
        shipment = await self.get(id)
        if shipment is None:
            return None
        shipment.sqlmodel_update(shipment_update)
        
        self.session.add(shipment)
        await self.session.commit()
        await self.session.refresh(shipment)
        
        return shipment
        
    
    async def delete(self, id: UUID) -> None:
        await self.session.delete(await self.get(id))
        await self.session.commit()
    
    