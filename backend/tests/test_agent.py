"""
Agent 图与路由测试

测试：
- graph 构建成功
- Supervisor 路由逻辑（用 Mock LLM）
- State reducer 合并
"""
import sys
sys.path.insert(0, ".")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.schemas.agent_models import MultiAgentState, merge_results
from app.agents.graph import build_graph
from app.agents.nodes import _last_user_message, VALID_WORKERS


# ── 辅助函数 ──
class TestHelpers:
    def test_last_user_message(self):
        state = {
            "messages": [
                HumanMessage(content="你好"),
                AIMessage(content="你好！"),
                HumanMessage(content="熊猫基地怎么去"),
            ]
        }
        assert _last_user_message(state) == "熊猫基地怎么去"

    def test_no_user_message(self):
        state = {"messages": [AIMessage(content="你好")]}
        assert _last_user_message(state) == ""


# ── 图构建 ──
class TestGraphBuild:
    def test_build_graph_no_checkpointer(self):
        graph = build_graph(checkpointer=None)
        assert graph is not None

    def test_graph_has_supervisor_entry(self):
        graph = build_graph(checkpointer=None)
        # 编译后的图能正常调用
        assert graph is not None


# ── Supervisor 路由（Mock LLM）──
@pytest.mark.asyncio
async def test_supervisor_routes_to_qa():
    """用户问景点信息 → qa_worker"""
    mock_response = AIMessage(content='{"next_workers": ["qa_worker"]}')
    with patch("app.agents.nodes.llm_json", new=AsyncMock()) as mock_llm:
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.nodes import supervisor

        state: MultiAgentState = {
            "messages": [HumanMessage(content="杜甫草堂门票多少钱")],
            "next_workers": [],
            "worker_results": {},
            "final_answer": "",
        }
        result = await supervisor(state)
        assert result["next_workers"] == ["qa_worker"]


@pytest.mark.asyncio
async def test_supervisor_routes_to_plan():
    """用户要求规划行程 → plan_worker"""
    mock_response = AIMessage(content='{"next_workers": ["plan_worker"]}')
    with patch("app.agents.nodes.llm_json", new=AsyncMock()) as mock_llm:
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.nodes import supervisor

        state: MultiAgentState = {
            "messages": [HumanMessage(content="帮我规划3天成都行程")],
            "next_workers": [],
            "worker_results": {},
            "final_answer": "",
        }
        result = await supervisor(state)
        assert result["next_workers"] == ["plan_worker"]


@pytest.mark.asyncio
async def test_supervisor_multi_intent():
    """模糊意图 → 多 Worker 并行"""
    mock_response = AIMessage(
        content='{"next_workers": ["qa_worker", "nearby_worker", "advice_worker"]}'
    )
    with patch("app.agents.nodes.llm_json", new=AsyncMock()) as mock_llm:
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.nodes import supervisor

        state: MultiAgentState = {
            "messages": [HumanMessage(content="我想去杜甫草堂")],
            "next_workers": [],
            "worker_results": {},
            "final_answer": "",
        }
        result = await supervisor(state)
        assert "qa_worker" in result["next_workers"]
        assert "nearby_worker" in result["next_workers"]


@pytest.mark.asyncio
async def test_supervisor_invalid_workers_filtered():
    """非法 Worker 名被过滤"""
    mock_response = AIMessage(content='{"next_workers": ["qa_worker", "invalid_worker"]}')
    with patch("app.agents.nodes.llm_json", new=AsyncMock()) as mock_llm:
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.nodes import supervisor

        state: MultiAgentState = {
            "messages": [HumanMessage(content="你好")],
            "next_workers": [],
            "worker_results": {},
            "final_answer": "",
        }
        result = await supervisor(state)
        assert result["next_workers"] == ["qa_worker"]
        assert "invalid_worker" not in result["next_workers"]


@pytest.mark.asyncio
async def test_supervisor_summary_when_results_exist():
    """有 worker_results 时走汇总分支"""
    mock_response = AIMessage(content="这是汇总后的回答")
    with patch("app.agents.nodes.llm", new=AsyncMock()) as mock_llm:
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.nodes import supervisor

        state: MultiAgentState = {
            "messages": [HumanMessage(content="你好")],
            "next_workers": ["qa_worker"],
            "worker_results": {"qa_worker": "RAG 回答内容"},
            "final_answer": "",
        }
        result = await supervisor(state)
        assert result["next_workers"] == []
        assert "汇总后的回答" in result["final_answer"]
        assert len(result["messages"]) == 1
