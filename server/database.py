import contextvars
import re
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from server.config import settings

class Base(DeclarativeBase):
    pass

# default engine for the main user
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30},
)

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

SessionLocal = sessionmaker(bind=engine)

# per-user database support
_current_user = contextvars.ContextVar('current_user', default=None)
_user_engines = {}

VALID_USER_ID = re.compile(r'^[a-zA-Z0-9_-]{1,32}$')


def _get_user_engine(user_id: str):
    """get or create a SQLAlchemy engine for a specific user's database."""
    if user_id not in _user_engines:
        db_path = f"sqlite:///./spotme_{user_id}.db"
        eng = create_engine(
            db_path,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(eng, "connect")
        def set_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        # create all tables for new user databases
        Base.metadata.create_all(bind=eng)
        _user_engines[user_id] = eng
    return _user_engines[user_id]


def get_db():
    user_id = _current_user.get()
    if user_id:
        eng = _get_user_engine(user_id)
        db = sessionmaker(bind=eng)()
    else:
        db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
