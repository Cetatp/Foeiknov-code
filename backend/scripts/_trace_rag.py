"""诊断 6504 Document → 2048 Node 的真实原因"""
import sys
sys.path.insert(0, ".")
from collections import Counter
import importlib.util

# 加载 build_chunks
spec = importlib.util.spec_from_file_location("_ac", "scripts/_analyze_chunks.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
docs = mod.build_chunks()
print(f"1. build_chunks() → {len(docs)} 个 Document")

from llama_index.core import VectorStoreIndex, Settings, StorageContext

# 看看 Settings 里的默认值
print(f"2. Settings.text_splitter: {Settings.text_splitter}")

# 模拟 VectorStoreIndex.from_documents 实际调用链
from llama_index.core.node_parser import SentenceSplitter

splitter = Settings.text_splitter or SentenceSplitter()
print(f"   实际使用的 splitter: {splitter}")

nodes = splitter.get_nodes_from_documents(docs)
print(f"3. splitter 输出 → {len(nodes)} 个 Node")

# 设置 show_progress=True 看 transformations 链路
print("\n4. 模拟 VectorStoreIndex.from_documents 的 transformations...")

# 源码里 from_documents 会调用 index._build_index_from_nodes
# 但在此之前会做 transformations = list(Settings.transformations) or [SentenceSplitter()]
# 让我看看这个默认 transformations 到底是什么
from llama_index.core.ingestion import IngestionPipeline

# 不连 vector store，只看 pipeline 输出
from app.rag.embeddings import EmbeddingService
Settings.embed_model = EmbeddingService()

# 用 IngestionPipeline 看看
pipeline = IngestionPipeline(
    transformations=Settings.transformations or [SentenceSplitter()],
)
pipeline.nodes = []  # 清空
try:
    ingested = pipeline.run(documents=docs, show_progress=False)
    print(f"5. IngestionPipeline.run() → {len(ingested)} 个 Node")
except Exception as e:
    print(f"5. IngestionPipeline 报错（可能需要 embed model）: {e}")

# 关键问题：实际运行时 2048 是怎么来的？
# 让我直接 trace 从 VectorStoreIndex.from_documents 的 transformation 路径
print("\n=== 直接检查 LlamaIndex 默认行为 ===")

# Settings.transformations 如果是 None，from_documents 内部用的是什么？
# 看 LlamaIndex 源码
import inspect
src = inspect.getsource(VectorStoreIndex.from_documents)
# 只看前 3000 字符
print(src[:3000])
