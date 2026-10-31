from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, EmailStr, Field

from app.database.models import ShipmentEvent, ShipmentStatus


class BaseShipment(BaseModel):
    content: str
    weight: float = Field(gt=0, le=25)
    destination: int


class ShipmentRead(BaseShipment):
    id: UUID
    status: ShipmentStatus | None
    timeline: list[ShipmentEvent]
    estimated_delivery: datetime


class ShipmentCreate(BaseShipment):
    client_contact_email: EmailStr
    client_contact_phone: str | None = Field(default=None)


class ShipmentUpdate(BaseModel):
    location: int | None = Field(default=None)
    description: str | None = Field(default=None)
    status: ShipmentStatus | None = Field(default=None)
    estimated_delivery: AwareDatetime | None = Field(default=None)
