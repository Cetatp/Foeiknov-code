"""
01_init_db_create_tables.py
创建 9 张 MySQL 表。使用 SQLAlchemy ORM + Base.metadata.create_all()。
"""
import sys
sys.path.insert(0, ".")

from app.database.mysql_client import engine
from app.schemas.db_models import Base
from app.logger import logger


def main():
    logger.info("开始创建数据表...")
    Base.metadata.create_all(bind=engine)
    tables = Base.metadata.tables.keys()
    logger.info(f"✅ {len(tables)} 张表创建完成：{', '.join(tables)}")


if __name__ == "__main__":
    main()
