from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.shipment import ShipmentCreate, ShipmentUpdate
from app.database.models import DeliveryPartner, Seller, Shipment, ShipmentStatus
from app.database.redis import (
    can_resend_verification_code,
    count_verification_attempt,
    delete_verification_code,
    get_verification_code_hash,
)
from app.services.shipment_events import ShipmentEventService
from app.utils import is_valid_verification_code

from .base import BaseService
from .delivery_partner import DeliveryPartnerService

MAX_VERIFICATION_ATTEMPTS = 5
FINISHED_STATUSES = (ShipmentStatus.delivered, ShipmentStatus.cancelled)

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
        
        shipment: Shipment = await self._add(new_shipment)
        
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
        
        shipment = await self._get_partner_shipment(id, partner)

        if shipment.status in FINISHED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Shipment is already {shipment.status.value}",
            )

        # Delivery needs the client's code, see verify_delivery
        if shipment_update.status == ShipmentStatus.delivered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use /shipment/verify with the client's code to mark as delivered",
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
            
        if shipment.status in FINISHED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Shipment is already {shipment.status.value}",
            )
   
        event = await self.event_service.add(
            shipment=shipment,
            status=ShipmentStatus.cancelled
        )
        shipment.timeline.append(event)
        return shipment
            
    async def delete(self, shipment: Shipment) -> None:
        await self._delete(shipment)
      
    async def _get_partner_shipment(
        self,
        id: UUID,
        partner: DeliveryPartner,
    ) -> Shipment:
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

        return shipment
    
    async def verify_delivery(
        self,
        id: UUID,
        code: str,
        partner: DeliveryPartner,
    ) -> Shipment:
        shipment = await self._get_partner_shipment(id, partner)

        if shipment.status != ShipmentStatus.out_for_delivery:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Shipment is not out for delivery",
            )

        # Count first, so each try is counted before the code is checked
        attempts = await count_verification_attempt(id)
        if attempts > MAX_VERIFICATION_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many wrong codes, request a new code",
            )

        stored_hash = await get_verification_code_hash(id)
        if stored_hash is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code expired, request a new code",
            )

        if not is_valid_verification_code(id, code, stored_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Wrong code, {MAX_VERIFICATION_ATTEMPTS - attempts} attempts left",
            )

        await self.event_service.add(
            shipment=shipment,
            status=ShipmentStatus.delivered,
        )
        # A code works only once
        await delete_verification_code(id)

        return await self._update(shipment)

    async def resend_verification_code(
        self,
        id: UUID,
        partner: DeliveryPartner,
    ) -> None:
        shipment = await self._get_partner_shipment(id, partner)

        if shipment.status != ShipmentStatus.out_for_delivery:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Shipment is not out for delivery",
            )

        if not await can_resend_verification_code(id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another code",
            )

        await self.event_service.resend_verification_code(shipment)


    