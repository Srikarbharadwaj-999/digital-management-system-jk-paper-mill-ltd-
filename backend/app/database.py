from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DB_URL = "sqlite:///./helmet_dms.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def add_column_if_missing(table_name: str, column_name: str, column_sql: str):
    """Small SQLite migration helper.

    This keeps older local databases working when the project receives new fields.
    It is intentionally simple because this project uses SQLite, not Alembic.
    """
    with engine.begin() as connection:
        existing_columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        existing_names = {column[1] for column in existing_columns}
        if column_name not in existing_names:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def run_lightweight_migrations():
    add_column_if_missing("users", "active", "active BOOLEAN DEFAULT 1")

    add_column_if_missing("registered_persons", "department", "department VARCHAR DEFAULT ''")
    add_column_if_missing("registered_persons", "designation", "designation VARCHAR DEFAULT ''")
    add_column_if_missing("registered_persons", "updated_at", "updated_at DATETIME")

    add_column_if_missing("violations", "department", "department VARCHAR DEFAULT ''")
    add_column_if_missing("violations", "designation", "designation VARCHAR DEFAULT ''")
    add_column_if_missing("violations", "camera_id", "camera_id INTEGER")
    add_column_if_missing("violations", "face_score", "face_score FLOAT DEFAULT 0")
    add_column_if_missing("violations", "is_unknown", "is_unknown BOOLEAN DEFAULT 1")
    add_column_if_missing("violations", "unknown_tracking_id", "unknown_tracking_id VARCHAR")
    add_column_if_missing("violations", "repeat_count", "repeat_count INTEGER DEFAULT 1")
