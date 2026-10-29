from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlalchemy.dialects import postgresql
from sqlmodel import Column, Field, Relationship, SQLModel


class ShipmentStatus(str, Enum):
    placed = "placed"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    
    
class Shipment(SQLModel, table=True):
    __tablename__ = "shipment"  # type: ignore[assignment]
    
    id: UUID = Field(
        sa_column=Column(
            postgresql.UUID,
            default=uuid4,
            primary_key=True
            )
    )
    
    content: str
    weight: float = Field(le=25)
    destination: int
    status: ShipmentStatus
    # sa_type=DateTime stores plain datetime (newer SQLModel requires a timezone by default)
    estimated_delivery: datetime = Field(sa_type=DateTime)
    
    seller_id: UUID = Field(foreign_key="seller.id")
    seller: Seller = Relationship(
        back_populates="shipments",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

class Seller(SQLModel, table=True):
    __tablename__ = "seller"  # type: ignore[assignment]
    
    id: UUID = Field(
        sa_column=Column(
            postgresql.UUID,
            default=uuid4,
            primary_key=True,
        )
    )
    
    name: str
    
    email: EmailStr
    password_hash: str
    
    shipments: list[Shipment] = Relationship(
        back_populates="seller",
        sa_relationship_kwargs={"lazy": "selectin"},
    )