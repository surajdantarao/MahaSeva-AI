import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

try:
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        pass
except ImportError:
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing from the project-root .env file."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
    connect_args={"connect_timeout": 5},
)

try:
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
except Exception:
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def check_database_connection() -> str:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT DATABASE()")
        ).scalar_one()
