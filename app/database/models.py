from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel
from pydantic import EmailStr

class ShipmentStatus(str, Enum):
    placed = "placed"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    
    
class Shipment(SQLModel, table=True):
    __tablename__ = "shipment"
    
    id: int = Field(default=None, primary_key=True)
    
    content: str
    weight: float = Field(le=25)
    destination: int
    status: ShipmentStatus
    # sa_type=DateTime stores plain datetime (newer SQLModel requires a timezone by default)
    estimated_delivery: datetime = Field(sa_type=DateTime)
    

class Seller(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    
    email: EmailStr
    password_hash: str