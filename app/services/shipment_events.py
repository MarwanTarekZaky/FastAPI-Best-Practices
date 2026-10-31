
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Shipment, ShipmentEvent, ShipmentStatus
from app.services.base import BaseService
from app.services.notification import NotificationService


class ShipmentEventService(BaseService):
    def __init__(self, session: AsyncSession, tasks):
        super().__init__(ShipmentEvent, session)
        self.notification_service = NotificationService(tasks)
        
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

        event = await self._add(new_event)

        # Only email the client when the status changes
        if last_event is None or last_event.status != status:
            await self._notify(shipment, status)

        return event

    async def get_latest_event(
        self,
        shipment: Shipment,
    ) -> ShipmentEvent | None:
        timeline = shipment.timeline
        return timeline[-1] if timeline else None

    def _generate_description(self, status: ShipmentStatus, location: int):
        match status:
            case ShipmentStatus.placed:
                return "assigned delivery partner"
            case ShipmentStatus.out_for_delivery:
                return "shipment out for delivery"
            case ShipmentStatus.delivered:
                return "successfully delivered"
            case ShipmentStatus.cancelled:
                return "cancelled by seller"
            case _:  # and ShipmentStatus.in_transit
                return f"scanned at {location}"
    
    async def _notify(self, shipment: Shipment, status: ShipmentStatus):
        
        if status == ShipmentStatus.in_transit:
            return

        subject: str
        context = {}
        template_name: str

        match status:
            case ShipmentStatus.placed:
                subject="Your Order is Shipped 🚛"
                context["seller"] = shipment.seller.name
                context["partner"] = shipment.delivery_partner.name
                template_name="mail_placed.html"

            case ShipmentStatus.out_for_delivery:
                subject="Your Order is Arriving Soon 🛵"
                template_name = "mail_out_for_delivery.html"
                
            case ShipmentStatus.delivered:
                subject = "Your Order is Delivered ✅"
                context["seller"] = shipment.seller.name
                template_name = "mail_delivered.html"

            case ShipmentStatus.cancelled:
                subject = "Your Order is Cancelled ❌"
                template_name = "mail_cancelled.html"

        await self.notification_service.send_email_with_template(
            recipients=[shipment.client_contact_email],
            subject=subject,
            context=context,
            template_name=template_name,
        )

