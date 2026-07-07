"""
人工兜底节点
无法自动处理时转人工客服
"""
from typing import Dict, Any
from datetime import datetime
from src.state.schema import TicketState, WorkflowDecision, ConversationTurn
from src.utils.logger import get_logger

logger = get_logger(__name__)


def human_escalation(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    
    logger.warn(
        "ticket_escalated_to_human",
        ticket_id=ticket_info["ticket_id"],
        reason=state["escalation_reason"],
    )
    
    decision: WorkflowDecision = {
        "node_name": "human_escalation",
        "action": "escalate",
        "confidence": 0.0,
        "timestamp": datetime.now().isoformat(),
        "metadata": {"reason": state["escalation_reason"], "workflow_path": state["routing_path"]},
    }
    
    new_turn: ConversationTurn = {
        "role": "assistant",
        "content": "抱歉，我无法处理您的问题，已为您转接人工客服，请稍候...",
        "timestamp": datetime.now().isoformat(),
    }
    
    return {
        "current_node": "human_escalation",
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": state["conversation_history"] + [new_turn],
        "routing_path": state["routing_path"] + ["human_escalation"],
        "need_human_escalation": True,
        "is_completed": True,
        "completion_reason": "已转接人工客服",
        "ticket_info": {
            **ticket_info,
            "ticket_status": "escalated",
            "update_time": datetime.now().isoformat(),
        },
    }