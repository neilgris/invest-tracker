import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 测试环境用独立数据库，避免污染生产数据
_db_name = "invest_tracker_test.db" if os.getenv("INVEST_TRACKER_TEST") else "invest_tracker.db"
DATABASE_URL = f"sqlite:///./{_db_name}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
