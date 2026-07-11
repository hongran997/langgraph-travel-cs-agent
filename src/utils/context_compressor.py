"""
上下文压缩模块
对话历史过长时自动压缩，保留关键信息，避免 token 超限
"""
from typing import List, Dict, Any
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_KEEP_RECENT = 10
DEFAULT_MAX_TURNS = 50


def estimate_turn_tokens(turn: Dict[str, Any]) -> int:
    """
    粗略估算单轮对话的 token 数
    按中文字符 1:1、英文字符 4:1 估算
    """
    content = turn.get("content", "")
    zh_count = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    en_count = len(content) - zh_count
    return zh_count + en_count // 4


def compress_conversation_history(
    conversation_history: List[Dict[str, Any]],
    max_turns: int = DEFAULT_MAX_TURNS,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    max_total_tokens: int = 4000,
) -> List[Dict[str, Any]]:
    """
    压缩对话历史

    策略：
    1. 若总轮数 <= max_turns 且 token 估算 <= max_total_tokens，直接返回
    2. 保留最近 keep_recent 轮对话
    3. 早期对话压缩为一条摘要消息，放在最前面

    Args:
        conversation_history: 原始对话历史列表
        max_turns: 最大轮数阈值，超过则触发压缩
        keep_recent: 保留最近多少轮
        max_total_tokens: 最大 token 估算阈值

    Returns:
        压缩后的对话历史
    """
    if not conversation_history:
        return conversation_history

    total_tokens = sum(estimate_turn_tokens(t) for t in conversation_history)
    total_turns = len(conversation_history)

    if total_turns <= max_turns and total_tokens <= max_total_tokens:
        return conversation_history

    if total_turns <= keep_recent:
        return conversation_history

    early_turns = conversation_history[:-keep_recent]
    recent_turns = conversation_history[-keep_recent:]

    summary = _generate_summary(early_turns)

    summary_turn: Dict[str, Any] = {
        "role": "system",
        "content": summary,
        "timestamp": datetime.now().isoformat(),
        "compressed": True,
        "compressed_turns": len(early_turns),
    }

    result = [summary_turn] + recent_turns

    logger.info(
        "对话历史已压缩",
        original_turns=total_turns,
        compressed_turns=len(result),
        original_tokens=total_tokens,
        compressed_tokens=sum(estimate_turn_tokens(t) for t in result),
    )

    return result


def _generate_summary(early_turns: List[Dict[str, Any]]) -> str:
    """
    生成早期对话摘要

    简易版摘要策略：
    - 统计用户说的总轮数
    - 提取已识别的意图和关键信息
    - 列出已收集的凭证类型
    - 记录当前工单状态
    """
    user_turns = [t for t in early_turns if t.get("role") == "user"]
    assistant_turns = [t for t in early_turns if t.get("role") == "assistant"]

    user_keywords = []
    for turn in user_turns[-3:]:
        content = turn.get("content", "")
        if len(content) > 50:
            content = content[:50] + "..."
        user_keywords.append(content)

    collected_credentials = set()
    for turn in early_turns:
        if turn.get("role") == "user":
            content = turn.get("content", "")
            if "订单号" in content or "ORD" in content:
                collected_credentials.add("订单号")
            if "票号" in content or "TICK" in content:
                collected_credentials.add("票号")
            if "身份证" in content:
                collected_credentials.add("身份证")

    summary_parts = [
        f"[历史对话摘要] 共 {len(early_turns)} 轮对话",
        f"用户消息 {len(user_turns)} 条，系统回复 {len(assistant_turns)} 条",
    ]

    if user_keywords:
        summary_parts.append("用户核心诉求关键词：" + "、".join(user_keywords))

    if collected_credentials:
        summary_parts.append("已收集凭证：" + "、".join(sorted(collected_credentials)))
    else:
        summary_parts.append("已收集凭证：暂无")

    return "；".join(summary_parts)
