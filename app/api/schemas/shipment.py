from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

from app.database.models import ShipmentEvent, ShipmentStatus, TagName


class BaseShipment(BaseModel):
    content: str = Field(
        description="What is inside the package",
        examples=["Glass vase"],
    )
    weight: float = Field(
        gt=0,
        le=25,
        description="Weight in kg",
        examples=[2.5],
    )
    destination: int = Field(
        description="Zip code to deliver to",
        examples=[11001],
    )


class TagRead(BaseModel):
    # Lets pydantic read the values from a Tag database object
    model_config = ConfigDict(from_attributes=True)

    name: TagName
    instruction: str = Field(
        examples=["Handle with care and don't stack anything on top"],
    )


class ShipmentRead(BaseShipment):
    """A shipment with its full history, newest event last"""

    id: UUID
    status: ShipmentStatus | None
    timeline: list[ShipmentEvent]
    tags: list[TagRead]
    estimated_delivery: datetime


class ShipmentCreate(BaseShipment):
    """A new shipment, a delivery partner is assigned automatically"""

    client_contact_email: EmailStr = Field(
        description="Gets the tracking link and the delivery code",
        examples=["client@example.com"],
    )
    # E.164 format, the only format Twilio accepts, for example +201012345678
    client_contact_phone: str | None = Field(
        default=None,
        pattern=r"^\+[1-9]\d{7,14}$",
        description="Optional, in international format. Gets the code by SMS",
        examples=["+201012345678"],
    )


class ShipmentUpdate(BaseModel):
    """Send only the fields that changed, at least one"""

    location: int | None = Field(
        default=None,
        description="Zip code where the shipment is now",
        examples=[11002],
    )
    description: str | None = Field(
        default=None,
        examples=["Arrived at the hub"],
    )
    status: ShipmentStatus | None = Field(
        default=None,
        description="Can't be `delivered`, use /shipment/verify for that",
    )
    estimated_delivery: AwareDatetime | None = Field(
        default=None,
        description="Must include a timezone",
        examples=["2026-11-07T15:00:00+02:00"],
    )


class ShipmentVerify(BaseModel):
    code: str = Field(
        pattern=r"^\d{6}$",
        description="The 6 digit code the client received",
        examples=["123456"],
    )
