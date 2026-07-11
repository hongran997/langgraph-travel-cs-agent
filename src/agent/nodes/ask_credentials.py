"""
凭证询问节点
调用凭证询问子图（Agent Loop），负责多轮凭证收集与验证
"""
from typing import Dict, Any, List
from datetime import datetime
from src.state.schema import TicketState, WorkflowDecision, ConversationTurn
from src.utils.logger import get_logger
from src.config.templates import get_template
from src.agent.subgraphs import get_credential_agent, CredentialAgentState

logger = get_logger(__name__)


def ask_credentials(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    product_type = ticket_info.get("product_type", "other")

    # 加载业务模板，获取该产品类型要求的全部凭证集合
    template = get_template(product_type)
    required_credentials = template.get_required_credentials()

    # 从 state 中提取已验证的凭证类型
    provided_credentials = {cred["type"] for cred in state["credentials"] if cred.get("verified")}

    # 计算还缺哪些凭证
    missing_credentials = list(required_credentials - provided_credentials)

    # 如果不缺凭证，直接标志完成，让 _after_ask_credentials 回到路由节点
    if not missing_credentials:
        decision: WorkflowDecision = {
            "node_name": "ask_credentials",
            "action": "credentials_complete",
            "confidence": 1.0,
            "timestamp": datetime.now().isoformat(),
            "metadata": {},
        }
        return {
            "current_node": "ask_credentials",
            "workflow_decisions": state["workflow_decisions"] + [decision],
            "routing_path": state["routing_path"] + ["ask_credentials"],
        }

    # 构造凭证子图的初始状态
    # 把 state 中已有凭证和历史对话传给子图，让子图在已有基础上继续收集
    sub_state: CredentialAgentState = {
        "product_type": product_type,
        "needed_credentials": missing_credentials,
        "collected_credentials": [
            {"type": c["type"], "value": c["value"], "verified": c.get("verified", True)}
            for c in state["credentials"]
        ],
        "conversation_history": list(state["conversation_history"]),
        "retry_count": 0,
        "max_retries": 3,
        "done": False,
        "escalation_needed": False,
        "escalation_reason": "",
    }

    # 执行凭证子图（内部先 verify 再 ask，只跑一轮）
    agent = get_credential_agent()
    sub_result = agent.invoke(sub_state)

    # 将子图收集到的凭证写回父图 state
    new_credentials = []
    for cred in sub_result.get("collected_credentials", []):
        if cred["type"] in required_credentials:
            new_credentials.append({
                "type": cred["type"],
                "value": cred.get("value", ""),
                "verified": cred.get("verified", True),
            })

    # 更新后的对话历史（子图内部追加了 ask 和 verify 产生的消息）
    history_from_sub = sub_result.get("conversation_history", [])

    # 场景 1：子图判定需要转人工（超过最大重试次数）
    if sub_result.get("escalation_needed"):
        decision = {
            "node_name": "ask_credentials",
            "action": "escalate_to_human",
            "confidence": 0.3,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "reason": sub_result.get("escalation_reason", "凭证收集失败"),
            },
        }
        escalate_turn: ConversationTurn = {
            "role": "assistant",
            "content": "非常抱歉，多次尝试未能收集到完整的凭证信息，我将为您转接人工客服。",
            "timestamp": datetime.now().isoformat(),
        }
        return {
            "current_node": "ask_credentials",
            "credentials": new_credentials,
            "workflow_decisions": state["workflow_decisions"] + [decision],
            "conversation_history": history_from_sub + [escalate_turn],
            "routing_path": state["routing_path"] + ["ask_credentials"],
            "need_human_escalation": True,
            "escalation_reason": sub_result.get("escalation_reason", "凭证收集失败"),
        }

    # 场景 2：子图本轮收集结果——还缺还是齐了
    still_missing = sub_result.get("needed_credentials", [])
    action = "credentials_complete" if not still_missing else "ask_missing_credentials"

    decision: WorkflowDecision = {
        "node_name": "ask_credentials",
        "action": action,
        "confidence": 0.9 if action == "credentials_complete" else 0.8,
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "missing_credentials": still_missing,
            "collected_count": len(new_credentials),
        },
    }

    logger.info(
        "凭证询问子图执行完成",
        ticket_id=ticket_info.get("ticket_id"),
        action=action,
        missing_count=len(still_missing),
        collected_count=len(new_credentials),
    )

    # action 为 credentials_complete → _after_ask_credentials 回路由节点
    # action 为 ask_missing_credentials → _after_ask_credentials 走 END
    return {
        "current_node": "ask_credentials",
        "credentials": new_credentials,
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": history_from_sub,
        "routing_path": state["routing_path"] + ["ask_credentials"],
    }
