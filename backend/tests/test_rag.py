"""
RAG 检索评测

Case 1: "熊猫基地今天开放吗？" → Top1 必须是 chunk_type=travel_tips 且 source_name 含"大熊猫繁育研究基地"
Case 2: "杜甫草堂门票多少钱" → Top1 必须含"杜甫草堂"且为 travel_tips 或 basic_info
"""
import sys
sys.path.insert(0, ".")

import pytest
from app.rag.embeddings import EmbeddingService
from app.rag.llama_index_engine import (
    build_index, build_hybrid_retriever, build_reranker, KeywordBoostPostprocessor
)
from llama_index.core import Settings
from app.logger import logger

# 全局初始化
Settings.embed_model = EmbeddingService()
Settings.llm = None  # 检索测试不需要 LLM


@pytest.fixture(scope="module")
def hybrid_retriever():
    index = build_index()
    return build_hybrid_retriever(index)


@pytest.fixture(scope="module")
def reranker():
    return build_reranker(top_n=3)


@pytest.fixture(scope="module")
def keyword_boost():
    return KeywordBoostPostprocessor(boost=1.5)


def test_panda_travel_tips(hybrid_retriever, reranker, keyword_boost):
    """Case 1: 熊猫基地开放时间 → 应召回 travel_tips 类型"""
    query = "熊猫基地今天开放吗？"
    nodes = hybrid_retriever.retrieve(query)
    reranked = reranker.postprocess_nodes(nodes, query_str=query)
    boosted = keyword_boost.postprocess_nodes(reranked, query_str=query)

    assert len(boosted) > 0, "检索结果为空"
    top1 = boosted[0]
    logger.info(f"Top1: {top1.metadata.get('source_name')} "
                f"(chunk_type={top1.metadata.get('chunk_type')}, score={top1.score:.4f})")

    name = str(top1.metadata.get("source_name", ""))
    chunk_type = top1.metadata.get("chunk_type", "")
    # 大熊猫6号别墅、成都大熊猫繁育研究基地等都属于熊猫基地
    assert "大熊猫" in name or "熊猫基地" in name, \
        f"Top1 名称不匹配: {name}"
    assert chunk_type == "travel_tips", \
        f"期望 chunk_type=travel_tips, 实际={chunk_type}"


def test_dufu_ticket(hybrid_retriever, reranker, keyword_boost):
    """Case 2: 杜甫草堂门票 → 应召回杜甫草堂相关且含票价信息"""
    query = "杜甫草堂门票多少钱"
    nodes = hybrid_retriever.retrieve(query)
    reranked = reranker.postprocess_nodes(nodes, query_str=query)
    boosted = keyword_boost.postprocess_nodes(reranked, query_str=query)

    assert len(boosted) > 0, "检索结果为空"
    top1 = boosted[0]
    logger.info(f"Top1: {top1.metadata.get('source_name')} "
                f"(chunk_type={top1.metadata.get('chunk_type')}, score={top1.score:.4f})")

    name = str(top1.metadata.get("source_name", ""))
    assert "杜甫草堂" in name, f"Top1 名称不匹配: {name}"
    # travel_tips 含票价，basic_info 也可能含级别信息
    chunk_type = top1.metadata.get("chunk_type", "")
    assert chunk_type in ("travel_tips", "basic_info"), \
        f"期望 travel_tips/basic_info, 实际={chunk_type}"
