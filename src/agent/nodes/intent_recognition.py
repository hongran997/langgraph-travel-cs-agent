"""
意图识别节点
基于关键词匹配识别用户意图（退票、改签、投诉、查询等）
"""
from typing import Dict, Any
from datetime import datetime
from src.state.schema import TicketState, ConversationTurn, WorkflowDecision
from src.utils.logger import get_logger
from src.config.templates import get_template
from src.config.settings import settings
from src.utils.context_compressor import compress_conversation_history

logger = get_logger(__name__)


def recognize_intent(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    customer_message = ticket_info["customer_message"]

    conversation_history = state["conversation_history"]
    compressed_history = compress_conversation_history(
        conversation_history,
        max_turns=settings.max_conversation_history,
    )
    history_changed = compressed_history is not conversation_history

    for turn in reversed(compressed_history):
        if turn["role"] == "user":
            customer_message += " " + turn["content"]
    
    # 根据业务类型加载对应模板获取意图关键词
    template = get_template(ticket_info.get("product_type", "other"))
    intent_keywords = template.get_intent_keywords()
    
    intent_scores = {}
    for intent, keywords in intent_keywords.items():
        score = sum(1 for keyword in keywords if keyword in customer_message)
        if score > 0:
            intent_scores[intent] = score / len(keywords)
    
    if intent_scores:
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = intent_scores[best_intent]
    else:
        best_intent = "inquiry"
        confidence = 0.5
    
    logger.info(
        "intent_recognition_completed",
        ticket_id=ticket_info["ticket_id"],
        intent=best_intent,
        confidence=confidence,
    )
    
    decision: WorkflowDecision = {
        "node_name": "intent_recognition",
        "action": f"identified_intent_{best_intent}",
        "confidence": confidence,
        "timestamp": datetime.now().isoformat(),
        "metadata": {"intent_scores": intent_scores},
    }
    
    new_turn: ConversationTurn = {
        "role": "system",
        "content": f"识别到用户意图：{best_intent}，置信度：{confidence:.2f}",
        "timestamp": datetime.now().isoformat(),
    }
    
    return {
        "current_intent": best_intent,
        "intent_confidence": confidence,
        "current_node": "intent_recognition",
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": (compressed_history if history_changed else state["conversation_history"]) + [new_turn],
        "routing_path": state["routing_path"] + ["intent_recognition"],
    }