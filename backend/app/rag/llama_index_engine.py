"""
RAG 核心引擎：LlamaIndex VectorStoreIndex + HybridRetriever + BGE Reranker

核心链路：
用户Query → VectorIndexRetriever（BGE向量Top10）→ BM25Retriever（关键词Top10）
→ QueryFusionRetriever 融合 → BGE Reranker 重排 Top3 → 动态QA Prompt → LLM生成
"""
from typing import Optional, List
from llama_index.core import VectorStoreIndex, StorageContext, Settings, PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.schema import TextNode, NodeWithScore
from llama_index.vector_stores.milvus import MilvusVectorStore
from app.rag.embeddings import EmbeddingService
from app.rag.prompt_templates import build_qa_prompt
from app.config import settings
from app.logger import logger


def _build_vector_store(overwrite: bool = False) -> MilvusVectorStore:
    """构建 Milvus VectorStore（兼容 Standalone / Lite）。"""
    kwargs = {
        "uri": settings.milvus_uri,
        "collection_name": settings.MILVUS_COLLECTION_SPOTS,
        "dim": settings.MILVUS_DIM,
        "overwrite": overwrite,
    }
    # Standalone 模式指定数据库
    if not settings.is_milvus_lite and settings.MILVUS_DB_NAME:
        kwargs["db_name"] = settings.MILVUS_DB_NAME
    logger.info(f"MilvusVectorStore: uri={settings.milvus_uri}, "
                f"collection={settings.MILVUS_COLLECTION_SPOTS}, dim={settings.MILVUS_DIM}")
    return MilvusVectorStore(**kwargs)


def _ensure_settings():
    """确保 LlamaIndex Settings 已正确初始化（BGE Embedding + 真实 LLM）。"""
    # 注意：不能读 Settings.embed_model（getter 会触发 resolve_embed_model 调 OpenAI）
    # 直接读私有属性 _embed_model 判断是否已初始化
    if Settings._embed_model is None:
        Settings.embed_model = EmbeddingService()

    # ── Monkey-patch 三部曲：让 LlamaIndex OpenAI LLM 支持 DeepSeek 模型 ──
    #
    # DeepSeek API 完全兼容 OpenAI Chat API，但 LlamaIndex 硬编码了 OpenAI 模型列表
    # 且默认用 legacy /completions 端点，需要三处 patch：

    # Patch 1: 注入 DeepSeek 模型的 context_window
    from llama_index.llms.openai import utils as _llm_utils
    for _ds_model in ("deepseek-chat", "deepseek-v4-pro", "deepseek-reasoner",
                       "deepseek-v4-flash-vision-exp"):
        _llm_utils.ALL_AVAILABLE_MODELS.setdefault(_ds_model, 131072)

    # Patch 2: 注入 tiktoken 编码映射（DeepSeek 用 cl100k_base）
    import tiktoken.model as _tiktoken_model
    for _ds_model in ("deepseek-chat", "deepseek-v4-pro", "deepseek-reasoner",
                       "deepseek-v4-flash-vision-exp"):
        _tiktoken_model.MODEL_TO_ENCODING.setdefault(_ds_model, "cl100k_base")

    # Patch 3: 覆盖 _complete / _acomplete，改用 chat.completions（DeepSeek 不支持 legacy /completions）
    from llama_index.llms.openai import OpenAI as _LlmOpenAI
    from llama_index.core.llms import CompletionResponse

    def _patched_complete(self, prompt, **kwargs):
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self._get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.3),
            stream=False,
        )
        text = resp.choices[0].message.content or ""
        return CompletionResponse(text=text)

    async def _patched_acomplete(self, prompt, **kwargs):
        client = self._get_client()
        resp = await client.chat.completions.create(
            model=self._get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.3),
            stream=False,
        )
        text = resp.choices[0].message.content or ""
        return CompletionResponse(text=text)

    _LlmOpenAI._complete = _patched_complete
    _LlmOpenAI._acomplete = _patched_acomplete

    # ★ 设置真实 LLM（API 完全兼容 OpenAI Chat API）
    from app.config import settings
    Settings.llm = _LlmOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        api_base=settings.DEEPSEEK_BASE_URL,
        temperature=0.3,
        max_tokens=getattr(settings, "DEEPSEEK_MAX_TOKENS", 4096),
    )


def build_index(vector_store: Optional[MilvusVectorStore] = None) -> VectorStoreIndex:
    """从已有 Milvus 集合加载 VectorStoreIndex（不重新向量化）。"""
    _ensure_settings()
    if vector_store is None:
        vector_store = _build_vector_store(overwrite=False)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )
    logger.info("VectorStoreIndex 加载完成")
    return index


def _load_all_nodes_from_milvus(vector_store: MilvusVectorStore) -> List[TextNode]:
    """从 Milvus 全量加载节点（含文本），供 BM25 建索引使用。"""
    import json
    client = vector_store.client
    collection_name = vector_store.collection_name
    nodes = []
    offset = 0
    batch_size = 1000
    while True:
        rows = client.query(
            collection_name=collection_name,
            filter='id != ""',
            output_fields=["id", "_node_content"],
            limit=batch_size,
            offset=offset,
        )
        if not rows:
            break
        for row in rows:
            # LlamaIndex 将节点序列化为 _node_content JSON
            content_raw = row.get("_node_content", "{}")
            try:
                content = json.loads(content_raw)
            except (json.JSONDecodeError, TypeError):
                content = {}
            text = content.get("text", "")
            metadata = content.get("metadata", {})
            # BM25 索引时把 source_name 拼入文本，增强名称匹配权重
            source_name = metadata.get("source_name", "")
            if source_name and source_name not in text:
                text = f"{source_name} {text}"
            node = TextNode(
                id_=str(row["id"]),
                text=text,
                metadata=metadata,
            )
            nodes.append(node)
        offset += len(rows)
        if len(rows) < batch_size:
            break
    logger.info(f"从 Milvus 加载 {len(nodes)} 个节点用于 BM25")
    return nodes


def build_hybrid_retriever(index: VectorStoreIndex) -> QueryFusionRetriever:
    """构建混合检索器：向量 Top10 + BM25 Top10，reciprocal_rerank 融合。"""
    vector_retriever = VectorIndexRetriever(index=index, similarity_top_k=10)

    # BM25 需要原始文本，从 Milvus 全量加载节点
    nodes = _load_all_nodes_from_milvus(index.vector_store)
    # 中文 BM25：用单字 token_pattern，按字符匹配（避免 jieba 分词后查询无法对齐）
    bm25_retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=10,
        verbose=False,
        token_pattern=r"[\u4e00-\u9fa5]|[a-zA-Z0-9]+",
    )

    hybrid_retriever = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        mode="simple",
        num_queries=1,
        similarity_top_k=20,
        use_async=False,
        verbose=False,
    )
    logger.info("HybridRetriever 构建完成（向量+BM25, simple）")
    return hybrid_retriever


def build_reranker(top_n: int = 3) -> SentenceTransformerRerank:
    """BGE Reranker 重排器。"""
    return SentenceTransformerRerank(
        model=settings.RERANKER_MODEL_NAME,
        top_n=top_n,
    )


class DynamicTextQAPrompt(PromptTemplate):
    """动态 QA Prompt：根据问题类型拼接不同软知识维度组。

    继承 PromptTemplate，只需重写 format，其他接口（partial_format / kwargs / template_vars）
    由父类提供，避免 async response_synthesizer 炸掉。
    """

    def __init__(self):
        # 占位模板字符串，实际 format 会忽略它，用 build_qa_prompt 动态生成
        super().__init__(template="{context_str}\n\nQuery: {query_str}\n\nAnswer: ")

    def format(self, context_str: str, query_str: str, **kwargs) -> str:
        return build_qa_prompt(query_str, context_str)


class KeywordBoostPostprocessor:
    """关键词增强后处理：source_name 与查询有重叠时提升 score，travel_tips 额外加权。"""

    def __init__(self, boost: float = 1.5):
        self.boost = boost

    def postprocess_nodes(self, nodes, query_str=None, **kwargs):
        if not query_str:
            return nodes
        query_chars = set(query_str)
        for n in nodes:
            name = str(n.metadata.get("source_name", ""))
            overlap = len(set(name) & query_chars)
            if overlap > 0:
                n.score = (n.score or 0.0) * (1 + 0.1 * overlap) * self.boost
            # travel_tips 含票价/开放时间等硬事实，额外加权
            if n.metadata.get("chunk_type") == "travel_tips":
                n.score = (n.score or 0.0) * 1.3
        return sorted(nodes, key=lambda x: x.score or 0.0, reverse=True)

    async def apostprocess_nodes(self, nodes, query_str=None, **kwargs):
        """异步版本：直接调同步版（后处理无 IO 阻塞）。"""
        return self.postprocess_nodes(nodes, query_str=query_str, **kwargs)


def build_query_engine(index: Optional[VectorStoreIndex] = None):
    """组装完整 QueryEngine：HybridRetriever + BGE Reranker + 动态 Prompt。"""
    _ensure_settings()
    if index is None:
        index = build_index()

    retriever = build_hybrid_retriever(index)
    reranker = build_reranker(top_n=3)
    keyword_boost = KeywordBoostPostprocessor(boost=1.5)

    # Settings.llm 已在 _ensure_settings() 中配置为真实 LLM
    response_synthesizer = get_response_synthesizer(
        text_qa_template=DynamicTextQAPrompt(),
        response_mode="compact",
    )
    # QueryFusionRetriever 没有 as_query_engine，用 RetrieverQueryEngine.from_args
    from llama_index.core.query_engine import RetrieverQueryEngine
    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        response_synthesizer=response_synthesizer,
        node_postprocessors=[reranker, keyword_boost],
    )
    logger.info("QueryEngine 构建完成（HybridRetriever + BGE Reranker + 动态QA Prompt）")
    return query_engine
