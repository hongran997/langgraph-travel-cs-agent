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
    product_type: str
    needed_credentials: List[str]
    collected_credentials: List[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]
    retry_count: int
    max_retries: int
    done: bool
    escalation_needed: bool
    escalation_reason: str


CREDENTIAL_PATTERNS = {
    "order_no": [
        r"ORD[A-Z0-9]{6,}",
        r"订单号[:：]?\s*([A-Z0-9]{6,})",
        r"[A-Z]{2,}\d{6,}",
    ],
    "ticket_no": [
        r"TICK[A-Z0-9]{6,}",
        r"票号[:：]?\s*([0-9\-]{10,})",
        r"\d{3}-\d{10}",
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
    """向用户询问下一个需要的凭证"""
    needed = state["needed_credentials"]
    product_type = state["product_type"]
    template = get_template(product_type)

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
    """从用户最新回复中提取并验证凭证"""
    history = state["conversation_history"]
    needed = list(state["needed_credentials"])
    collected = list(state["collected_credentials"])

    user_messages = [t for t in history if t.get("role") == "user"]
    newly_collected = []
    still_needed = []
    new_retry_count = state["retry_count"]

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

    if newly_collected:
        new_retry_count = 0
    else:
        new_retry_count = state["retry_count"] + 1

    escalation_needed = False
    escalation_reason = ""

    if new_retry_count > state["max_retries"] and still_needed:
        escalation_needed = True
        escalation_reason = f"凭证收集超过最大重试次数({state['max_retries']})"
        logger.warn(
            "凭证询问子图: 超过最大重试次数，转人工",
            max_retries=state["max_retries"],
        )

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
    """子图内部上下文压缩"""
    compressed = compress_conversation_history(
        state["conversation_history"],
        max_turns=20,
        keep_recent=8,
        max_total_tokens=2000,
    )
    return {"conversation_history": compressed}


def route_credential_agent(state: CredentialAgentState) -> str:
    """子图内部路由"""
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
    verify（从对话历史提取验证凭证） → ask（问下一个缺失的凭证） → END

    子图的"循环"体现在多次父图 invoke 之间：
    第1轮：用户发消息 → verify(没凭证) → ask(问订单号) → END
    第2轮：用户回复订单号 → verify(提取到) → ask(问票号) → END
    第3轮：用户回复票号 → verify(提取到，齐了) → END
    """
    sub_graph = StateGraph(CredentialAgentState)

    sub_graph.add_node("verify", verify_user_response)
    sub_graph.add_node("ask", ask_next_credential)
    sub_graph.add_node("compress", compress_history_if_needed)

    sub_graph.set_entry_point("verify")

    sub_graph.add_conditional_edges(
        "verify",
        route_credential_agent,
        {
            "ask": "ask",
            "done": END,
            "escalate": END,
        },
    )

    sub_graph.add_edge("ask", END)

    return sub_graph.compile()


credential_agent = None


def get_credential_agent():
    """获取凭证子图单例"""
    global credential_agent
    if credential_agent is None:
        credential_agent = build_credential_agent()
    return credential_agent
