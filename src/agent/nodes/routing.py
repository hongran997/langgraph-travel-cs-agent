"""
分支路由节点
根据意图置信度、知识库结果、凭证完整性决定流转路径
"""
from typing import Dict, Any
from datetime import datetime
from src.state.schema import TicketState, WorkflowDecision, ConversationTurn
from src.utils.logger import get_logger
from src.config.templates import get_template

logger = get_logger(__name__)


def route_decision(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    intent = state["current_intent"]
    confidence = state["intent_confidence"]
    rag_results = state["rag_results"]
    
    # 根据业务类型加载对应模板获取路由规则
    template = get_template(ticket_info.get("product_type", "other"))
    rules = template.get_routing_rules()
    
    need_credentials = _check_credentials(state, template)
    rag_confidence = rag_results[0]["confidence"] if rag_results else 0.0
    
    intent_threshold = rules.get("intent_confidence_threshold", 0.5)
    rag_threshold = rules.get("rag_confidence_threshold", 0.6)
    auto_resolve_enabled = rules.get("auto_resolve_enabled", True)
    
    # 酒店退改需人工确认（按业务模板配置）
    if intent in ("refund", "reschedule", "modify"):
        auto_refund = rules.get("auto_refund_enabled", True)
        auto_reschedule = rules.get("auto_reschedule_enabled", True)
        if intent == "refund" and not auto_refund:
            action = "escalate_to_human"
            next_node = "human_escalation"
        elif intent == "reschedule" and not auto_reschedule:
            action = "escalate_to_human"
            next_node = "human_escalation"
        elif need_credentials:
            action = "ask_credentials"
            next_node = "ask_credentials"
        elif confidence < intent_threshold or rag_confidence < rag_threshold:
            action = "escalate_to_human"
            next_node = "human_escalation"
        elif rag_results and auto_resolve_enabled:
            action = "auto_resolve"
            next_node = "auto_resolve"
        else:
            action = "ask_clarification"
            next_node = "ask_clarification"
    elif need_credentials:
        action = "ask_credentials"
        next_node = "ask_credentials"
    elif confidence < intent_threshold or rag_confidence < rag_threshold:
        action = "escalate_to_human"
        next_node = "human_escalation"
    elif rag_results and auto_resolve_enabled:
        action = "auto_resolve"
        next_node = "auto_resolve"
    else:
        action = "ask_clarification"
        next_node = "ask_clarification"
    
    logger.info(
        "routing_decision_made",
        ticket_id=ticket_info["ticket_id"],
        intent=intent,
        action=action,
        next_node=next_node,
    )
    
    decision: WorkflowDecision = {
        "node_name": "routing",
        "action": action,
        "confidence": min(confidence, rag_confidence),
        "timestamp": datetime.now().isoformat(),
        "metadata": {"intent": intent, "intent_confidence": confidence, "rag_confidence": rag_confidence},
    }
    
    new_turn: ConversationTurn = {
        "role": "system",
        "content": f"路由决策：{action} -> {next_node}",
        "timestamp": datetime.now().isoformat(),
    }
    
    return {
        "current_node": "routing",
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": state["conversation_history"] + [new_turn],
        "routing_path": state["routing_path"] + ["routing"],
        "need_human_escalation": action == "escalate_to_human",
        "escalation_reason": "意图识别置信度不足或知识库查询结果置信度不足" if action == "escalate_to_human" else None,
    }


def _check_credentials(state: TicketState, template) -> bool:
    required_credentials = template.get_required_credentials()
    provided_credentials = {cred["type"] for cred in state["credentials"] if cred["verified"]}
    return not required_credentials.issubset(provided_credentials)