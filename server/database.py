from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from server.config import settings

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
