from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.schemas.shipment import ShipmentListParams, ShipmentSort, SortOrder
from app.database.models import Shipment

# Which column each sort option uses
SORT_COLUMNS = {
    ShipmentSort.created_at: col(Shipment.created_at),
    ShipmentSort.estimated_delivery: col(Shipment.estimated_delivery),
    ShipmentSort.weight: col(Shipment.weight),
}


async def paginate_shipments(
    session: AsyncSession,
    query: Select[Shipment],
    params: ShipmentListParams,
) -> tuple[Sequence[Shipment], int]:
    # How many match in total, so the client knows how many pages there are
    total = await session.scalar(select(func.count()).select_from(query.subquery()))

    column = SORT_COLUMNS[params.sort_by]
    ordering = column.asc() if params.order == SortOrder.asc else column.desc()

    shipments = await session.scalars(
        # id breaks ties: rows with the same weight must keep the same order
        # on every page, or one could show up twice and another never
        query.order_by(ordering, col(Shipment.id))
        .limit(params.limit)
        .offset(params.offset)
    )
    return shipments.all(), total or 0
