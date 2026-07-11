"""
凭证询问子图（Agent Loop）
独立的 Agent，负责多轮凭证收集与验证
"""
import re
from typing import TypedDict, List, Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, END
from src.utils.logger import get_logger
from src.config.templates import get_template
from src.utils.context_compressor import compress_conversation_history

logger = get_logger(__name__)


class CredentialAgentState(TypedDict):
    """
    凭证子图的内部状态，与父图 TicketState 完全独立
    """
    product_type: str                          # 产品类型（flight/hotel/train）
    needed_credentials: List[str]              # 当前还缺哪些凭证
    collected_credentials: List[Dict[str, Any]] # 已收集的凭证列表
    conversation_history: List[Dict[str, Any]]  # 子图内部对话上下文
    retry_count: int                            # 当前重试次数
    max_retries: int                            # 最大重试上限
    done: bool                                  # 是否完成收集
    escalation_needed: bool                     # 是否需要转人工
    escalation_reason: str                      # 转人工原因


# 各凭证类型的正则提取规则
# 每个类型支持多种格式，按优先级排列
CREDENTIAL_PATTERNS = {
    "order_no": [
        r"ORD[A-Z0-9]{6,}",                    # 纯 ORD 前缀
        r"订单号[:：]?\s*([A-Z0-9]{6,})",      # "订单号：xxx"
        r"[A-Z]{2,}\d{6,}",                    # 其他字母+数字组合
    ],
    "ticket_no": [
        r"TICK[A-Z0-9]{6,}",                   # 纯 TICK 前缀
        r"票号[:：]?\s*([0-9\-]{10,})",        # "票号：xxx"
        r"\d{3}-\d{10}",                        # 标准票号格式 999-1234567890
    ],
    "id_card": [
        r"身份证[:：]?\s*([1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx])",
        r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]",
    ],
    "phone": [
        r"1[3-9]\d{9}",
    ],
    "booking_reference": [
        r"[A-Z0-9]{6}",
    ],
}


def _extract_credential(text: str, cred_type: str) -> str | None:
    """从文本中提取指定类型的凭证"""
    patterns = CREDENTIAL_PATTERNS.get(cred_type, [])
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if groups:
                return groups[0]
            return match.group(0)
    return None


def _verify_credential(cred_type: str, value: str) -> bool:
    """简单验证凭证格式"""
    if not value or len(value) < 4:
        return False
    return True


def ask_next_credential(state: CredentialAgentState) -> Dict[str, Any]:
    """
    向用户询问下一个需要的凭证
    从 needed_credentials 列表取第一个缺失的凭证，使用业务模板的提示语
    """
    needed = state["needed_credentials"]
    product_type = state["product_type"]
    template = get_template(product_type)

    # 没有需要问的了，直接完成
    if not needed:
        return {"done": True}

    next_needed = needed[0]
    prompt = template.get_credential_prompt(next_needed)

    new_turn = {
        "role": "assistant",
        "content": prompt,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(
        "凭证询问子图: 询问凭证",
        credential_type=next_needed,
        retry_count=state["retry_count"],
    )

    return {
        "conversation_history": state["conversation_history"] + [new_turn],
    }


def verify_user_response(state: CredentialAgentState) -> Dict[str, Any]:
    """
    从用户最新回复中提取并验证凭证

    逻辑：
    1. 取出对话历史中最新一条用户消息
    2. 对 still_needed 中每种凭证尝试用正则提取
    3. 提取成功 → 加入 collected，从 still_needed 移除
    4. 提取失败 → 保留在 still_needed，重试计数 +1
    5. 重试超过 max_retries → 标记转人工
    6. 无用户消息（首次调用）→ 直接去 ask，不计重试
    """
    history = state["conversation_history"]
    needed = list(state["needed_credentials"])
    collected = list(state["collected_credentials"])

    # 提取所有用户消息
    user_messages = [t for t in history if t.get("role") == "user"]
    newly_collected = []
    still_needed = []
    new_retry_count = state["retry_count"]

    # 没有用户消息 → 首次进入，去 ask 问，不计重试
    if not user_messages:
        return {
            "needed_credentials": needed,
            "collected_credentials": collected,
            "retry_count": 0,
            "done": False,
            "escalation_needed": False,
            "escalation_reason": "",
        }

    latest_user_msg = user_messages[-1]["content"]

    # 遍历每种缺失的凭证，尝试提取
    for cred_type in needed:
        value = _extract_credential(latest_user_msg, cred_type)
        if value and _verify_credential(cred_type, value):
            collected.append({
                "type": cred_type,
                "value": value,
                "verified": True,
                "collected_at": datetime.now().isoformat(),
            })
            newly_collected.append(cred_type)
            logger.info(
                "凭证询问子图: 凭证验证通过",
                credential_type=cred_type,
            )
        else:
            still_needed.append(cred_type)

    # 至少提取到一个有效凭证 → 重置重试计数
    # 什么都没提取到 → 重试计数 +1
    if newly_collected:
        new_retry_count = 0
    else:
        new_retry_count = state["retry_count"] + 1

    escalation_needed = False
    escalation_reason = ""

    # 超过最大重试次数且仍有缺失凭证 → 转人工
    if new_retry_count > state["max_retries"] and still_needed:
        escalation_needed = True
        escalation_reason = f"凭证收集超过最大重试次数({state['max_retries']})"
        logger.warn(
            "凭证询问子图: 超过最大重试次数，转人工",
            max_retries=state["max_retries"],
        )

    # 凭证收齐且不需要转人工 → 完成
    done = len(still_needed) == 0 and not escalation_needed

    return {
        "needed_credentials": still_needed,
        "collected_credentials": collected,
        "retry_count": new_retry_count,
        "done": done,
        "escalation_needed": escalation_needed,
        "escalation_reason": escalation_reason,
    }


def compress_history_if_needed(state: CredentialAgentState) -> Dict[str, Any]:
    """
    子图内部上下文压缩
    使用主图的 context_compressor，参数更保守（上限 20 轮，保留 8 轮）
    """
    compressed = compress_conversation_history(
        state["conversation_history"],
        max_turns=20,
        keep_recent=8,
        max_total_tokens=2000,
    )
    return {"conversation_history": compressed}


def route_credential_agent(state: CredentialAgentState) -> str:
    """
    子图内部路由

    判断 verify 节点之后的路径：
    - escalate → 转人工（超过重试次数）
    - done     → 凭证收齐，退出子图
    - ask      → 还有缺的，去 ask 问下一个
    """
    if state.get("escalation_needed"):
        return "escalate"

    if state.get("done") or not state["needed_credentials"]:
        return "done"

    if state["retry_count"] > state["max_retries"]:
        return "escalate"

    return "ask"


def build_credential_agent() -> StateGraph:
    """
    构建凭证询问子图（Agent Loop）

    每次调用流程：
    verify（从对话历史提取验证凭证）
      → compress（压缩对话历史，防止上下文超限）
      → ask（问下一个缺失的凭证）
      → END

    子图的"循环"体现在多次父图 invoke 之间：
    第1轮：用户发消息 → verify(没凭证) → compress → ask(问订单号) → END
    第2轮：用户回复订单号 → verify(提取到) → compress → ask(问票号) → END
    第3轮：用户回复票号 → verify(提取到，齐了) → END
    """
    sub_graph = StateGraph(CredentialAgentState)

    sub_graph.add_node("verify", verify_user_response)
    sub_graph.add_node("ask", ask_next_credential)
    sub_graph.add_node("compress", compress_history_if_needed)

    sub_graph.set_entry_point("verify")

    # verify 完成后根据结果走 compress / done / escalate
    sub_graph.add_conditional_edges(
        "verify",
        route_credential_agent,
        {
            "ask": "compress",
            "done": END,
            "escalate": END,
        },
    )

    # compress 完再去 ask，防止 ask 节点对话历史超限
    sub_graph.add_edge("compress", "ask")

    # ask 结束后直接 END（等下一轮父图 invoke 再回来）
    sub_graph.add_edge("ask", END)

    return sub_graph.compile()


credential_agent = None


def get_credential_agent():
    """获取凭证子图单例"""
    global credential_agent
    if credential_agent is None:
        credential_agent = build_credential_agent()
    return credential_agent
