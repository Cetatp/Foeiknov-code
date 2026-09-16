"""
LLM 客户端工厂
统一管理 DeepSeek API 调用，供所有数据扩充脚本复用
"""
import os
from dotenv import load_dotenv

# 加载 .env（项目根目录）
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def get_llm():
    """返回 LangChain DeepSeek LLM 实例"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(
            "未配置 DEEPSEEK_API_KEY。请在项目根目录创建 .env 文件，填入：\n"
            "DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx"
        )
    from langchain_deepseek import ChatDeepSeek
    return ChatDeepSeek(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.7,
        max_tokens=4096,
    )
