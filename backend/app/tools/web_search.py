"""
联网搜索工具 — 基于 DuckDuckGo HTML 搜索

用于"智能搜索"模式：在回答前检索互联网最新信息，增强时效性。

注意：DuckDuckGo 在国内可能不稳定，失败时降级返回提示。
"""
import re
import html
import requests
from app.logger import logger

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def web_search(query: str, max_results: int = 5) -> str:
    """
    联网搜索，返回格式化的搜索结果文本。

    Args:
        query: 搜索关键词
        max_results: 返回结果条数

    Returns:
        格式化的搜索结果（Markdown 列表），失败时返回空字符串
    """
    try:
        url = "https://html.duckduckgo.com/html/"
        resp = requests.post(
            url,
            data={"q": query},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()

        # 解析结果链接和摘要
        results = []
        # DuckDuckGo HTML 结果结构：<a class="result__a" href="...">标题</a>
        # <a class="result__snippet">摘要</a>
        link_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL,
        )

        links = link_pattern.findall(resp.text)
        snippets = snippet_pattern.findall(resp.text)

        for i, (href, title_raw) in enumerate(links[:max_results]):
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            title = html.unescape(title)
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
                snippet = html.unescape(snippet)
            # 清理 DuckDuckGo 的跳转链接
            if "uddg=" in href:
                import urllib.parse
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                href = qs.get("uddg", [href])[0]
            results.append(f"**{title}**\n{href}\n{snippet}")

        if not results:
            logger.warning(f"web_search 无结果: {query}")
            return ""

        logger.info(f"web_search 成功: {query} → {len(results)} 条结果")
        return "\n\n".join(results)

    except Exception as e:
        logger.warning(f"web_search 失败（联网不可用）: {e}")
        return ""
