from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_size=10,  # 连接池常驻连接数
    pool_recycle=3600,  # 连接最大存活时间，单位秒，3600=1小时
    pool_pre_ping=True,  # 获取连接前探测连接是否有效
    echo=False,  # 是否打印SQL语句，开发环境改为True看日志
)
# 会话工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
