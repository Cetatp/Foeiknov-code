"""
RAG 核心引擎：LlamaIndex VectorStoreIndex + HybridRetriever + BGE Reranker

核心链路：
用户Query → VectorIndexRetriever（BGE向量Top10）→ BM25Retriever（关键词Top10）
→ QueryFusionRetriever 融合 → BGE Reranker 重排 Top3 → 动态QA Prompt → LLM生成
"""
from typing import Optional, List
from llama_index.core import VectorStoreIndex, StorageContext, Settings, PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever, QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.schema import TextNode
from llama_index.vector_stores.milvus import MilvusVectorStore
from app.rag.embeddings import EmbeddingService
from app.rag.prompt_templates import build_qa_prompt
from app.config import settings
from app.logger import logger


def _build_vector_store(overwrite: bool = False) -> MilvusVectorStore:
    kwargs = {
        "uri": settings.milvus_uri,
        "collection_name": settings.MILVUS_COLLECTION_SPOTS,
        "dim": settings.MILVUS_DIM,
        "overwrite": overwrite,
    }
    if not settings.is_milvus_lite and settings.MILVUS_DB_NAME:
        kwargs["db_name"] = settings.MILVUS_DB_NAME
    return MilvusVectorStore(**kwargs)


def _ensure_settings():
    """初始化 BGE Embedding 与默认 DeepSeek LLM。"""
    if Settings._embed_model is None:
        Settings.embed_model = EmbeddingService()

    from llama_index.llms.openai import utils as _llm_utils
    _llm_utils.ALL_AVAILABLE_MODELS.setdefault(settings.DEEPSEEK_MODEL, 131072)

    import tiktoken.model as _tiktoken_model
    _tiktoken_model.MODEL_TO_ENCODING.setdefault(settings.DEEPSEEK_MODEL, "cl100k_base")

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
        return CompletionResponse(text=resp.choices[0].message.content or "")

    async def _patched_acomplete(self, prompt, **kwargs):
        client = self._get_client()
        resp = await client.chat.completions.create(
            model=self._get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.3),
            stream=False,
        )
        return CompletionResponse(text=resp.choices[0].message.content or "")

    _LlmOpenAI._complete = _patched_complete
    _LlmOpenAI._acomplete = _patched_acomplete

    Settings.llm = _LlmOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        api_base=settings.DEEPSEEK_BASE_URL,
        temperature=0.3,
        max_tokens=getattr(settings, "DEEPSEEK_MAX_TOKENS", 4096),
    )


def build_index(vector_store: Optional[MilvusVectorStore] = None) -> VectorStoreIndex:
    _ensure_settings()
    if vector_store is None:
        vector_store = _build_vector_store(overwrite=False)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)


def _load_all_nodes_from_milvus(vector_store: MilvusVectorStore) -> List[TextNode]:
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
            try:
                content = json.loads(row.get("_node_content", "{}"))
            except (json.JSONDecodeError, TypeError):
                content = {}
            text = content.get("text", "")
            metadata = content.get("metadata", {})
            source_name = metadata.get("source_name", "")
            if source_name and source_name not in text:
                text = f"{source_name} {text}"
            nodes.append(TextNode(id_=str(row["id"]), text=text, metadata=metadata))

        offset += len(rows)
        if len(rows) < batch_size:
            break

    logger.info(f"从 Milvus 加载 {len(nodes)} 个节点用于 BM25")
    return nodes


def build_hybrid_retriever(index: VectorStoreIndex) -> QueryFusionRetriever:
    vector_retriever = VectorIndexRetriever(index=index, similarity_top_k=10)
    nodes = _load_all_nodes_from_milvus(index.vector_store)
    bm25_retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=10,
        verbose=False,
        token_pattern=r"[\u4e00-\u9fa5]|[a-zA-Z0-9]+",
    )
    return QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        mode="simple",
        num_queries=1,
        similarity_top_k=20,
        use_async=False,
        verbose=False,
    )


def build_reranker(top_n: int = 3) -> SentenceTransformerRerank:
    return SentenceTransformerRerank(model=settings.RERANKER_MODEL_NAME, top_n=top_n)


class DynamicTextQAPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(template="{context_str}\n\nQuery: {query_str}\n\nAnswer: ")

    def format(self, context_str: str, query_str: str, **kwargs) -> str:
        return build_qa_prompt(query_str, context_str)


class KeywordBoostPostprocessor:
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
            if n.metadata.get("chunk_type") == "travel_tips":
                n.score = (n.score or 0.0) * 1.3
        return sorted(nodes, key=lambda x: x.score or 0.0, reverse=True)

    async def apostprocess_nodes(self, nodes, query_str=None, **kwargs):
        return self.postprocess_nodes(nodes, query_str=query_str, **kwargs)


def build_query_engine(index: Optional[VectorStoreIndex] = None):
    _ensure_settings()
    if index is None:
        index = build_index()

    from llama_index.core.query_engine import RetrieverQueryEngine

    return RetrieverQueryEngine.from_args(
        retriever=build_hybrid_retriever(index),
        response_synthesizer=get_response_synthesizer(
            text_qa_template=DynamicTextQAPrompt(),
            response_mode="compact",
        ),
        node_postprocessors=[build_reranker(top_n=3), KeywordBoostPostprocessor(boost=1.5)],
    )
