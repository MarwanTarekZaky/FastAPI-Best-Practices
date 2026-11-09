from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.schemas.shipment import (
    ShipmentCreate,
    ShipmentListParams,
    ShipmentUpdate,
)
from app.core.exceptions import (
    AlreadyExists,
    EntityNotFound,
    InvalidInput,
    InvalidState,
    NotAllowed,
    TooManyAttempts,
)
from app.database.models import (
    DeliveryPartner,
    Seller,
    Shipment,
    ShipmentStatus,
    TagName,
)
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
from .pagination import paginate_shipments
from .tag import TagService

MAX_VERIFICATION_ATTEMPTS = 5
FINISHED_STATUSES = (ShipmentStatus.delivered, ShipmentStatus.cancelled)

class ShipmentService(BaseService): 
    def __init__(
        self, session: AsyncSession,
        partner_service: DeliveryPartnerService,
        event_service: ShipmentEventService,
        tag_service: TagService,
    ) -> None:
        super().__init__(Shipment, session)
        self.partner_service = partner_service
        self.event_service = event_service
        self.tag_service = tag_service
    
    async def get(self, id: UUID) -> Shipment | None:
        return await self._get(id)
    
    async def get_by_seller(
        self, seller: Seller, params: ShipmentListParams
    ) -> tuple[Sequence[Shipment], int]:
        return await paginate_shipments(
            self.session,
            select(Shipment).where(col(Shipment.seller_id) == seller.id),
            params,
        )

    async def get_by_partner(
        self, partner: DeliveryPartner, params: ShipmentListParams
    ) -> tuple[Sequence[Shipment], int]:
        return await paginate_shipments(
            self.session,
            select(Shipment).where(col(Shipment.delivery_partner_id) == partner.id),
            params,
        )

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
        self._ensure_active(shipment)

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
        shipment = await self._get_seller_shipment(id, seller)

        self._ensure_active(shipment)
        
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
            raise EntityNotFound("Shipment not found")

        if shipment.delivery_partner_id != partner.id:
            raise NotAllowed()

        return shipment
    
    async def _get_seller_shipment(self, id: UUID, seller: Seller) -> Shipment:
        shipment = await self.get(id)
        if shipment is None:
            raise EntityNotFound("Shipment not found")

        if shipment.seller_id != seller.id:
            raise NotAllowed()

        return shipment
    
    def _ensure_active(self, shipment: Shipment):
        if shipment.status in FINISHED_STATUSES:
            raise InvalidState(f"Shipment is already {shipment.status.value}")
        
    async def verify_delivery(
        self,
        id: UUID,
        code: str,
        partner: DeliveryPartner,
    ) -> Shipment:
        shipment = await self._get_partner_shipment(id, partner)

        if shipment.status != ShipmentStatus.out_for_delivery:
            raise InvalidState("Shipment is not out for delivery")

        # Count first, so each try is counted before the code is checked
        attempts = await count_verification_attempt(id)
        if attempts > MAX_VERIFICATION_ATTEMPTS:
            raise TooManyAttempts("Too many wrong codes, request a new code")

        stored_hash = await get_verification_code_hash(id)
        if stored_hash is None:
            raise InvalidInput("Code expired, request a new code")

        if not is_valid_verification_code(id, code, stored_hash):
            raise InvalidInput(
                f"Wrong code, {MAX_VERIFICATION_ATTEMPTS - attempts} attempts left"
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
            raise InvalidState("Shipment is not out for delivery")

        if not await can_resend_verification_code(id):
            raise TooManyAttempts("Please wait before requesting another code")

        await self.event_service.resend_verification_code(shipment)

    async def add_tag(self, id: UUID, tag_name: TagName, seller: Seller) -> Shipment:
        # Only the seller who owns the shipment knows what is inside it
        shipment = await self._get_seller_shipment(id, seller)
        self._ensure_active(shipment)

        tag = await self.tag_service.get_by_name(tag_name)
        if tag in shipment.tags:
            raise AlreadyExists(f"Shipment already has the {tag_name.value} tag")

        # Adding to the list makes SQLAlchemy insert a row in shipment_tag
        shipment.tags.append(tag)
        return await self._update(shipment)

    async def remove_tag(self, id: UUID, tag_name: TagName, seller: Seller) -> Shipment:
        shipment = await self._get_seller_shipment(id, seller)
        self._ensure_active(shipment)

        tag = await self.tag_service.get_by_name(tag_name)
        if tag not in shipment.tags:
            raise EntityNotFound(f"Shipment doesn't have the {tag_name.value} tag")

        # Removing from the list deletes the row in shipment_tag, not the tag
        shipment.tags.remove(tag)
        return await self._update(shipment)