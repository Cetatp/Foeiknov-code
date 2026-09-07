"""
BGE Embedding 封装（兼容 LlamaIndex Embedding 接口）

★ BGE v1.5 官方规定：Query 路径必须加 instruction 前缀，否则召回率↓10%+。
"""
from typing import List
from llama_index.core.embeddings import BaseEmbedding
from sentence_transformers import SentenceTransformer
from app.config import settings
from app.logger import logger

# BGE v1.5 Query instruction 前缀（官方强制）
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


class EmbeddingService(BaseEmbedding):
    """BGE 向量化服务，LlamaIndex BaseEmbedding 兼容。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._model_name = settings.EMBED_MODEL_NAME
        self._device = settings.EMBED_DEVICE
        logger.info(f"加载 Embedding 模型: {self._model_name} (device={self._device})")
        self._model = SentenceTransformer(self._model_name, device=self._device)
        self._dim = self._model.get_sentence_embedding_dimension()
        logger.info(f"Embedding 维度: {self._dim}")

    @property
    def dim(self) -> int:
        return self._dim

    def _get_query_embedding(self, query: str) -> List[float]:
        """Query 路径：加 instruction 前缀 + L2 归一化。"""
        prompted = BGE_QUERY_PREFIX + query
        embedding = self._model.encode(
            prompted, normalize_embeddings=True, convert_to_numpy=True
        )
        return embedding.tolist()

    def _get_text_embedding(self, text: str) -> List[float]:
        """文档路径：不加前缀 + L2 归一化。"""
        embedding = self._model.encode(
            text, normalize_embeddings=True, convert_to_numpy=True
        )
        return embedding.tolist()

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return embeddings.tolist()

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)
