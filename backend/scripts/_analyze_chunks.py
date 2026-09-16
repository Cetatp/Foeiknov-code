"""快速诊断：为什么 6504 Document → 2048 Node？"""
import sys
sys.path.insert(0, ".")

from collections import Counter
import re

# 直接 inline build_chunks，避免 import 路径问题
from sqlalchemy import text
from app.database.mysql_client import engine
from llama_index.core import Document

def build_chunks():
    documents = []
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM spots")).fetchall()
        for row in rows:
            d = dict(row._mapping)
            base_meta = {"source_type": "spot", "source_id": d["spot_id"], "source_name": d["spot_name"]}
            if d.get("description"):
                documents.append(Document(text=str(d["description"]), metadata={**base_meta, "chunk_type": "description"}))
            tips_parts = []
            if d.get("opening_hours_json"): tips_parts.append(f"开放时间:{d['opening_hours_json']}")
            if d.get("ticket_price_min") is not None: tips_parts.append(f"票价:{d['ticket_price_min']}元")
            if d.get("travel_tips"): tips_parts.append(f"游览建议:{d['travel_tips']}")
            if tips_parts:
                documents.append(Document(text="\n".join(tips_parts), metadata={**base_meta, "chunk_type": "travel_tips"}))
            if d.get("cultural_context"):
                documents.append(Document(text=str(d["cultural_context"]), metadata={**base_meta, "chunk_type": "cultural_context"}))
            info_parts = [f"名称:{d['spot_name']}"]
            if d.get("spot_level"): info_parts.append(f"级别:{d['spot_level']}")
            if d.get("address"): info_parts.append(f"地址:{d['address']}")
            if d.get("rating") is not None: info_parts.append(f"评分:{d['rating']}")
            if d.get("area_tag"): info_parts.append(f"区域:{d['area_tag']}")
            documents.append(Document(text="\n".join(info_parts), metadata={**base_meta, "chunk_type": "basic_info"}))

        rows = conn.execute(text("SELECT * FROM foods")).fetchall()
        for row in rows:
            d = dict(row._mapping)
            base_meta = {"source_type": "food", "source_id": d["food_id"], "source_name": d["food_name"]}
            if d.get("description"):
                documents.append(Document(text=str(d["description"]), metadata={**base_meta, "chunk_type": "description"}))
            price_parts = []
            if d.get("avg_price"): price_parts.append(f"人均:{d['avg_price']}")
            if d.get("best_areas"): price_parts.append(f"推荐区域:{d['best_areas']}")
            if price_parts:
                documents.append(Document(text="\n".join(price_parts), metadata={**base_meta, "chunk_type": "price_area"}))
            if d.get("famous_shops"):
                documents.append(Document(text=f"名店:{d['famous_shops']}", metadata={**base_meta, "chunk_type": "shops"}))

        rows = conn.execute(text("SELECT * FROM avoid_rules")).fetchall()
        for row in rows:
            d = dict(row._mapping)
            documents.append(Document(
                text=f"[{d['category']}] {d['title']}: {d['content']}",
                metadata={"source_type": "rule", "source_id": d["rule_id"], "source_name": d["title"],
                          "chunk_type": "rule_detail", "severity": d["severity"]},
            ))
    return documents

docs = build_chunks()
print(f"=== Document 总数: {len(docs)} ===")
src_cnt = Counter(d.metadata["source_type"] for d in docs)
chunk_cnt = Counter(d.metadata["chunk_type"] for d in docs)
print(f"  source_type: {dict(src_cnt)}")
print(f"  chunk_type:  {dict(chunk_cnt)}")

def count_chars(s): return len(re.findall(r"[\u4e00-\u9fff]", s)) + len(s.split())
lens = [count_chars(d.text) for d in docs]
print(f"\n=== 文本长度分布 (中文字符数) ===")
print(f"  min={min(lens)}, max={max(lens)}, avg={sum(lens)/len(lens):.1f}")
print(f"  <100字:      {sum(1 for l in lens if l<100)}")
print(f"  100-500字:   {sum(1 for l in lens if 100<=l<500)}")
print(f"  500-1024字:  {sum(1 for l in lens if 500<=l<1024)}")
print(f"  >1024字:     {sum(1 for l in lens if l>=1024)}")

# 看 SentenceSplitter 的行为
from llama_index.core.node_parser import SentenceSplitter
splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
nodes = splitter.get_nodes_from_documents(docs, show_progress=False)
print(f"\n=== SentenceSplitter(chunk_size=1024) 后 ===")
print(f"  Node 总数: {len(nodes)}")
print(f"  压缩率: {len(docs)} → {len(nodes)} ({len(nodes)/len(docs)*100:.0f}%)")

# 用 chunk_size=512 试试
splitter2 = SentenceSplitter(chunk_size=512, chunk_overlap=20)
nodes2 = splitter2.get_nodes_from_documents(docs, show_progress=False)
print(f"\n=== SentenceSplitter(chunk_size=512) 后 ===")
print(f"  Node 总数: {len(nodes2)}")
print(f"  压缩率: {len(docs)} → {len(nodes2)} ({len(nodes2)/len(docs)*100:.0f}%)")

# 抽样短文档
print(f"\n=== 抽样短 Document (<80字, 共 {sum(1 for l in lens if l<80)} 个) ===")
short_docs = [(i,d) for i,d in enumerate(docs) if count_chars(d.text)<80][:8]
for i,d in short_docs:
    meta = d.metadata
    text_preview = d.text[:80].replace("\n", " / ")
    print(f"  [{meta['source_type']}/{meta['chunk_type']}] {count_chars(d.text)}字: {text_preview}")
