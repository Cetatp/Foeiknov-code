"""
MySQL 客户端
SQLAlchemy 引擎、会话工厂、Base 声明基类。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# 创建引擎（连接池）
engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,        # 连接前 ping，避免使用失效连接
    pool_recycle=3600,         # 1 小时回收连接
    pool_size=10,              # 连接池大小
    max_overflow=20,           # 最大溢出连接数
    echo=False,                # 生产关闭 SQL 日志
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 基类
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取数据库会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
