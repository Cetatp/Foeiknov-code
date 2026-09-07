"""
backend/scripts/03_build_rag_index.py
从 MySQL 读取 spots/foods/avoid_rules → 文本分块 → BGE 向量化 → 写入 Milvus（通过 LlamaIndex）。

分块策略：
- 景点：description / travel_tips / cultural_context / basic_info（4 类）
- 美食：description / price_area / shops（3 类）
- 避坑规则：rule_detail（1 类）
"""
import sys
sys.path.insert(0, ".")

from sqlalchemy import text
from app.database.mysql_client import engine
from app.rag.embeddings import EmbeddingService
from app.rag.llama_index_engine import _build_vector_store
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from app.config import settings
from app.logger import logger

# LlamaIndex 全局 Settings：BGE 向量化
Settings.embed_model = EmbeddingService()
Settings.llm = None  # 仅建索引，不需要 LLM


def build_chunks() -> list:
    """从 MySQL 读取三类数据，生成 Document 列表。"""
    documents = []

    with engine.connect() as conn:
        # ── 1. 景点：4 类分块 ──
        rows = conn.execute(text("SELECT * FROM spots")).fetchall()
        for row in rows:
            d = dict(row._mapping)
            spot_id = d["spot_id"]
            spot_name = d["spot_name"]
            base_meta = {
                "source_type": "spot",
                "source_id": spot_id,
                "source_name": spot_name,
            }

            # chunk 1: description
            if d.get("description"):
                documents.append(Document(
                    text=str(d["description"]),
                    metadata={**base_meta, "chunk_type": "description"},
                ))

            # chunk 2: travel_tips（硬事实拼接）
            tips_parts = []
            if d.get("opening_hours_json"):
                tips_parts.append(f"开放时间:{d['opening_hours_json']}")
            if d.get("ticket_price_min") is not None:
                tips_parts.append(f"票价:{d['ticket_price_min']}元")
            if d.get("travel_tips"):
                tips_parts.append(f"游览建议:{d['travel_tips']}")
            if tips_parts:
                documents.append(Document(
                    text="\n".join(tips_parts),
                    metadata={**base_meta, "chunk_type": "travel_tips"},
                ))

            # chunk 3: cultural_context
            if d.get("cultural_context"):
                documents.append(Document(
                    text=str(d["cultural_context"]),
                    metadata={**base_meta, "chunk_type": "cultural_context"},
                ))

            # chunk 4: basic_info
            info_parts = [f"名称:{spot_name}"]
            if d.get("spot_level"):
                info_parts.append(f"级别:{d['spot_level']}")
            if d.get("address"):
                info_parts.append(f"地址:{d['address']}")
            if d.get("rating") is not None:
                info_parts.append(f"评分:{d['rating']}")
            if d.get("area_tag"):
                info_parts.append(f"区域:{d['area_tag']}")
            documents.append(Document(
                text="\n".join(info_parts),
                metadata={**base_meta, "chunk_type": "basic_info"},
            ))

        # ── 2. 美食：3 类分块 ──
        rows = conn.execute(text("SELECT * FROM foods")).fetchall()
        for row in rows:
            d = dict(row._mapping)
            food_id = d["food_id"]
            food_name = d["food_name"]
            base_meta = {
                "source_type": "food",
                "source_id": food_id,
                "source_name": food_name,
            }

            if d.get("description"):
                documents.append(Document(
                    text=str(d["description"]),
                    metadata={**base_meta, "chunk_type": "description"},
                ))

            price_parts = []
            if d.get("avg_price"):
                price_parts.append(f"人均:{d['avg_price']}")
            if d.get("best_areas"):
                price_parts.append(f"推荐区域:{d['best_areas']}")
            if price_parts:
                documents.append(Document(
                    text="\n".join(price_parts),
                    metadata={**base_meta, "chunk_type": "price_area"},
                ))

            if d.get("famous_shops"):
                documents.append(Document(
                    text=f"名店:{d['famous_shops']}",
                    metadata={**base_meta, "chunk_type": "shops"},
                ))

        # ── 3. 避坑规则：1 类分块 ──
        rows = conn.execute(text("SELECT * FROM avoid_rules")).fetchall()
        for row in rows:
            d = dict(row._mapping)
            documents.append(Document(
                text=f"[{d['category']}] {d['title']}: {d['content']}",
                metadata={
                    "source_type": "rule",
                    "source_id": d["rule_id"],
                    "source_name": d["title"],
                    "chunk_type": "rule_detail",
                    "severity": d["severity"],
                },
            ))

    return documents


def main():
    logger.info("从 MySQL 读取并生成 Document...")
    documents = build_chunks()
    logger.info(f"✅ 生成 {len(documents)} 个 Document")

    vector_store = _build_vector_store(overwrite=True)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    logger.info("BGE 向量化并写入 Milvus（首次下载模型约 300MB）...")
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )
    logger.info(f"✅ [LlamaIndex] 写入 {len(documents)} 条向量，集合={settings.MILVUS_COLLECTION_SPOTS}")


if __name__ == "__main__":
    main()
