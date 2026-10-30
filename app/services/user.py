from typing import Any

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import generate_access_token

from .base import BaseService

password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


class UserService(BaseService):
    def __init__(self, model: Any, session: AsyncSession):
        self.model = model
        self.session = session

    async def _add_user(self, data: dict) -> Any:
        if await self._get_by_email(data["email"]) is not None:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
            
        user = self.model(
            **data,
            password_hash=password_context.hash(data["password"]),
        )
        return await self._add(user)

    async def _get_by_email(self, email) -> Any:
        return await self.session.scalar(
            select(self.model).where(self.model.email == email)
        )

    async def _generate_token(self, email, password) -> str:
        # Validate the credentials
        user = await self._get_by_email(email)

        if user is None or not password_context.verify(
            password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect",
            )

        return generate_access_token(
            data={
                "user": {
                    "name": user.name,
                    "id": str(user.id),
                },
            }
        )
