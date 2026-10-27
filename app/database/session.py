from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

# sqlite.db in the project root (app/database -> app -> root)
DB_PATH = Path(__file__).parent.parent.parent / "sqlite.db"

# Create a database engine to connect with database
engine = create_engine(
    # database type/dialect and file name
    url=f"sqlite:///{DB_PATH}",
    # Log sql queries
    echo=True,
    connect_args={"check_same_thread": False},
)


def create_db_tables():
    from .models import Shipment  # noqa: F401
    SQLModel.metadata.create_all(bind=engine)


# Session to interact with database
def get_session():
    with Session(bind=engine) as session:
        yield session


# Session Dependency Annotation
SessionDep = Annotated[Session, Depends(get_session)]