"""
Agent State Schema — LangGraph 多智能体状态定义

核心设计：
- messages: list[BaseMessage]，用 add_messages reducer 自动追加
- worker_results: dict，自定义 merge_results reducer 合并并行 Worker 输出
- phase: "routing" | "summary"，明确区分 Supervisor 两轮职责
- debug_info: dict，记录各节点耗时、token 数等调试信息
"""
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages


def merge_results(left: dict, right: dict) -> dict:
    """并行 Worker 结果合并；空字典用于新请求重置旧结果。"""
    if right is not None and len(right) == 0:
        return {}
    return {**(left or {}), **(right or {})}


def merge_debug_info(left: dict, right: dict) -> dict:
    """调试信息合并：逐层 merge。"""
    merged = {**(left or {})}
    for k, v in (right or {}).items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


class MultiAgentState(TypedDict, total=False):
    """多智能体共享状态。"""

    messages: Annotated[list, add_messages]
    next_workers: list
    worker_results: Annotated[dict, merge_results]
    final_answer: str

    phase: Literal["routing", "summary"]

    user_id: str
    session_id: str

    debug_info: Annotated[dict, merge_debug_info]
