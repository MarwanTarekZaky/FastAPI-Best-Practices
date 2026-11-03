from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.exceptions import EntityNotFound
from app.database.models import Seller, Shipment, Tag, TagName

from .base import BaseService


class TagService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__(Tag, session)

    async def get_all(self) -> Sequence[Tag]:
        return (await self.session.scalars(select(Tag).order_by(Tag.name))).all()

    async def get_by_name(self, name: TagName) -> Tag:
        tag = await self.session.scalar(select(Tag).where(col(Tag.name) == name))
        if tag is None:
            # Tags are created by the migration, so this means it wasn't run
            raise EntityNotFound(f"Tag {name.value} not found")
        return tag

    async def get_shipments(self, name: TagName, seller: Seller) -> Sequence[Shipment]:
        # JOIN through the link table: shipment -> shipment_tag -> tag.
        # Only the seller's own shipments, newest first
        return (
            await self.session.scalars(
                select(Shipment)
                .join(Shipment.tags)  # type: ignore[arg-type]
                .where(col(Tag.name) == name, col(Shipment.seller_id) == seller.id)
                .order_by(col(Shipment.created_at).desc())
            )
        ).all()
