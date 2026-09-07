"""
Agent State Schema — LangGraph 多智能体状态定义

核心设计：
- messages: list[BaseMessage]，用 add_messages reducer 自动追加
- worker_results: dict，自定义 merge_results reducer 合并并行 Worker 输出
- phase: "routing" | "summary"，明确区分 Supervisor 两轮职责
- debug_info: dict，记录各节点耗时、token 数等调试信息
"""
from typing import TypedDict, Annotated, Any, Literal
from langgraph.graph.message import add_messages


def merge_results(left: dict, right: dict) -> dict:
    """并行 Worker 结果合并：right 覆盖 left 中同名 key，其余保留。
    
    特殊处理：
    - right 为空字典时 → 完全替换 left（用于 Supervisor routing 阶段清空旧中间状态）
    - 正常 Worker 输出时 → 合并（right 覆盖同名 key）
    """
    # 新请求重置：routing 阶段 Supervisor 返回 {} 时，清空旧值
    if right is not None and len(right) == 0:
        return {}
    return {**(left or {}), **(right or {})}


def merge_debug_info(left: dict, right: dict) -> dict:
    """调试信息合并：逐层 deep merge，不覆盖已有节点的统计。"""
    merged = {**(left or {})}
    for k, v in (right or {}).items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


class MultiAgentState(TypedDict, total=False):
    """多智能体共享状态（total=False 允许部分字段缺失）。"""

    # ── 核心流转字段 ──
    messages: Annotated[list, add_messages]          # 聊天历史（LangGraph 一等字段，随 Checkpointer 自动持久化）
    next_workers: list                                # Supervisor 意图分类结果：需要并行派发的 Worker 列表
    worker_results: Annotated[dict, merge_results]    # 各 Worker 输出结果：{worker_name: content}
    final_answer: str                                 # 最终汇总回答（Supervisor 第二轮生成）
    reasoning: str                                    # 深度思考过程（reasoner 模型的 thinking 内容）

    # ── 阶段标识 ──
    phase: Literal["routing", "summary"]              # Supervisor 当前阶段，避免隐式判断

    # ── 运行模式（前端传入）──
    mode: Literal["fast", "expert", "vision"]         # 快速/专家/识图
    deep_think: bool                                  # 是否开启深度思考
    smart_search: bool                                # 是否开启智能搜索（联网）
    image: str                                        # 图片 base64 dataURL（识图模式）

    # ── 多租户/用户上下文 ──
    user_id: str                                      # 用户标识
    session_id: str                                   # 会话 ID

    # ── 调试/可观测 ──
    debug_info: Annotated[dict, merge_debug_info]     # 各节点耗时、token 数等

