from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.config import db_settings

# Create a database engine to connect with database
engine = create_async_engine(
    url=db_settings.POSTGRES_URL,
    # Log sql queries
    echo=True,
)

# Session factory, created once and reused for every request
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


async def create_db_tables():
    async with engine.begin() as connection:
        from app.database.models import Shipment  # noqa: F401
        await connection.run_sync(SQLModel.metadata.create_all)


async def get_session():
    async with async_session() as session:
        yield session
