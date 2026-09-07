"""
02_import_seeds.py
将 data/seeds/ 下的 6 类 CSV 种子数据导入 MySQL。
流程：DROP 旧表 → ORM create_all 重建（保留索引/约束）→ append 导入
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
from sqlalchemy import text

from app.database.mysql_client import engine
from app.schemas.db_models import Base
from app.logger import logger

SEEDS_DIR = "./data/seeds"

# 需要导入的表及其 CSV 文件
SEED_MAP = {
    "spots": "spots_seed.csv",
    "foods": "foods_seed.csv",
    "food_shops": "food_shops_seed.csv",
    "avoid_rules": "avoid_rules_seed.csv",
    "hard_rules": "hard_rules_seed.csv",
    "transit_matrix": "transit_matrix.csv",
}


def main():
    # 1. 删除旧表（仅删除种子表，保留 chat_sessions/user_profiles/dlq）
    with engine.connect() as conn:
        for table in SEED_MAP:
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`;"))
        conn.commit()
    logger.info("已删除旧的种子数据表")

    # 2. 用 ORM 重建表（保留索引和约束）
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[t] for t in SEED_MAP])
    logger.info("ORM 重建表完成（含索引/约束）")

    # 3. 导入 CSV 数据（append 模式，不破坏表结构）
    for table_name, filename in SEED_MAP.items():
        df = pd.read_csv(f"{SEEDS_DIR}/{filename}")
        # 清洗空值和脏数据：'[]'、空字符串 → None
        df = df.replace(["[]", "", " "], None)
        df = df.where(pd.notnull(df), None)
        df.to_sql(name=table_name, con=engine, if_exists="append", index=False)
        logger.info(f"✅ {table_name}: 导入 {len(df)} 条")

    # 4. 重置自增主键
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE transit_matrix AUTO_INCREMENT = 1;"))
        conn.commit()

    logger.info("🎉 所有种子数据导入完成")


if __name__ == "__main__":
    main()
