from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

from app.database.models import ShipmentEvent, ShipmentStatus, TagName


class BaseShipment(BaseModel):
    content: str
    weight: float = Field(gt=0, le=25)
    destination: int


class TagRead(BaseModel):
    # Lets pydantic read the values from a Tag database object
    model_config = ConfigDict(from_attributes=True)

    name: TagName
    instruction: str


class ShipmentRead(BaseShipment):
    id: UUID
    status: ShipmentStatus | None
    timeline: list[ShipmentEvent]
    tags: list[TagRead]
    estimated_delivery: datetime


class ShipmentCreate(BaseShipment):
    client_contact_email: EmailStr
    # E.164 format, the only format Twilio accepts, for example +201012345678
    client_contact_phone: str | None = Field(
        default=None,
        pattern=r"^\+[1-9]\d{7,14}$",
    )


class ShipmentUpdate(BaseModel):
    location: int | None = Field(default=None)
    description: str | None = Field(default=None)
    status: ShipmentStatus | None = Field(default=None)
    estimated_delivery: AwareDatetime | None = Field(default=None)


class ShipmentVerify(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
