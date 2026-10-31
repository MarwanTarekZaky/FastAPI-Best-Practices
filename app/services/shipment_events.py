
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Shipment, ShipmentEvent, ShipmentStatus
from app.services.base import BaseService


class ShipmentEventService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__(ShipmentEvent, session)

    async def add(
        self,
        shipment: Shipment,
        location: int | None = None,
        status: ShipmentStatus | None = None,
        description: str | None = None,
    ) -> ShipmentEvent:

        last_event = await self.get_latest_event(shipment)

        # Fill missing values from the last event, if the shipment has one
        if location is None:
            location = last_event.location if last_event else shipment.destination
        if status is None:
            status = last_event.status if last_event else ShipmentStatus.placed

        new_event = ShipmentEvent(  # type: ignore[call-arg]
            location=location,
            status=status,
            description=description
            if description
            else self._generate_description(status, location),
            shipment_id=shipment.id,
        )

        return await self._add(new_event)

    async def get_latest_event(
        self,
        shipment: Shipment,
    ) -> ShipmentEvent | None:
        timeline = shipment.timeline
        return timeline[-1] if timeline else None

    def _generate_description(self, status: ShipmentStatus, location: int):
        match status:
            case ShipmentStatus.placed:
                return "Placed"
            case ShipmentStatus.delivered:
                return "Delivered"
            case ShipmentStatus.out_for_delivery:
                return "Out for delivery"
            case ShipmentStatus.cancelled:
                return "Cancelled by the seller"
            case _:
                return f"Scanned at {location}"
