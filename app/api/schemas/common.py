from pydantic import BaseModel, Field


class Message(BaseModel):
    """A short message that confirms the action worked"""

    detail: str = Field(examples=["Successfully logged out"])


class ErrorResponse(BaseModel):
    """The body of every error the API returns on purpose"""

    detail: str = Field(examples=["Shipment not found"])


class Token(BaseModel):
    access_token: str = Field(description="Send it as `Authorization: Bearer <token>`")
    # The OAuth2 standard name, clients and tools look for this one
    token_type: str = "bearer"
    # Old name, still sent so existing clients don't break
    type: str = Field(default="jwt", deprecated="Use token_type instead")
