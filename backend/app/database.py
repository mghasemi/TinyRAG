import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app/data/rag.db")

# Check if the data directory exists
data_dir = os.path.dirname(DATABASE_URL.replace("sqlite:///", ""))
if not os.path.exists(data_dir):
    os.makedirs(data_dir, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite requirement
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
