"""
LangGraph StateGraph — Supervisor + 4 Worker 多智能体

核心机制：
- Supervisor 意图分类 → Send API 并行 fan-out 到多个 Worker
- Worker 执行完自动 join 回 Supervisor 汇总
- worker_results 字段用自定义 reducer 合并并行结果
- 编译时注入 Checkpointer（默认 SqliteSaver）
- 支持 Mermaid 图可视化 + 流式输出
"""
from langgraph.graph import StateGraph, END
from langgraph.types import Send

from app.schemas.agent_models import MultiAgentState
from app.agents.nodes import (
    supervisor, qa_worker, plan_worker, advice_worker, nearby_worker,
)
from app.logger import logger


def build_graph(checkpointer=None):
    """构建并编译多智能体图。"""
    workflow = StateGraph(MultiAgentState)

    # 1. 添加节点
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("qa_worker", qa_worker)
    workflow.add_node("plan_worker", plan_worker)
    workflow.add_node("advice_worker", advice_worker)
    workflow.add_node("nearby_worker", nearby_worker)

    # 2. 入口
    workflow.set_entry_point("supervisor")

    # 3. 多意图并行路由
    def route(state: MultiAgentState):
        workers = state.get("next_workers", [])
        if not workers:
            return [END]
        # Send API：每个 Worker 并行执行，共享 state
        return [Send(worker, state) for worker in workers]

    workflow.add_conditional_edges("supervisor", route)

    # 4. Worker 执行完自动 join 回 Supervisor（汇总）
    workflow.add_edge("qa_worker", "supervisor")
    workflow.add_edge("plan_worker", "supervisor")
    workflow.add_edge("advice_worker", "supervisor")
    workflow.add_edge("nearby_worker", "supervisor")

    # 5. 编译 + Checkpointer
    graph = workflow.compile(checkpointer=checkpointer)
    logger.info("LangGraph 多智能体图构建完成（Supervisor + 4 Worker）")
    return graph


def get_mermaid_graph() -> str:
    """
    返回 Mermaid 流程图源码，用于调试可视化。

    用法：粘贴到 https://mermaid.live/ 或支持 Mermaid 的 Markdown 编辑器。
    """
    return """graph TD
    START([开始]) --> supervisor[Supervisor<br/>意图分类]
    supervisor -->|next_workers 非空| route{路由判断}
    route -->|qa_worker| qa[qa_worker<br/>RAG 问答]
    route -->|plan_worker| plan[plan_worker<br/>行程规划]
    route -->|advice_worker| advice[advice_worker<br/>六维建议]
    route -->|nearby_worker| nearby[nearby_worker<br/>周边推荐]
    qa --> summary[Supervisor<br/>汇总输出]
    plan --> summary
    advice --> summary
    nearby --> summary
    summary --> END([结束])
    """


async def astream_graph(graph, state: dict, config: dict):
    """
    流式执行图，yield 每个节点的增量输出。

    Args:
        graph: build_graph() 返回的编译图
        state: 初始状态 {"messages": [...], ...}
        config: LangGraph 配置 {"configurable": {"thread_id": "..."}}

    Yields:
        dict: {"node": 节点名, "chunk": 增量文本}
    """
    async for event in graph.astream(state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            # Worker 输出
            if "worker_results" in node_output:
                for worker, content in node_output["worker_results"].items():
                    yield {"node": worker, "chunk": content}
            # Supervisor 最终回答
            if "final_answer" in node_output:
                yield {"node": "supervisor", "chunk": node_output["final_answer"]}
