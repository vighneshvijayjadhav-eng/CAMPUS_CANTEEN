from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def connect(url: str):
    return create_engine(url, pool_pre_ping=True)


def session_for(engine):
    return Session(engine, expire_on_commit=False)
