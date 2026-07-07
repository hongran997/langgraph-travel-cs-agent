"""
自动解决节点
基于知识库结果自动完成工单闭环
"""
from typing import Dict, Any
from datetime import datetime
from src.state.schema import TicketState, WorkflowDecision, ConversationTurn
from src.utils.logger import get_logger
from src.config.templates import get_template

logger = get_logger(__name__)


def auto_resolve(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    rag_results = state["rag_results"]
    intent = state.get("current_intent", "default")
    
    # 根据业务类型加载对应模板获取回复模板
    template = get_template(ticket_info.get("product_type", "other"))
    
    # 优先使用业务模板回复，兜底使用RAG结果
    template_solution = template.get_resolution_template(intent)
    solution = rag_results[0]["answer"] if rag_results else template_solution
    
    logger.info(
        "ticket_auto_resolved",
        ticket_id=ticket_info["ticket_id"],
        confidence=rag_results[0]["confidence"] if rag_results else 0.0,
    )
    
    decision: WorkflowDecision = {
        "node_name": "auto_resolve",
        "action": "resolve_successfully",
        "confidence": rag_results[0]["confidence"] if rag_results else 0.7,
        "timestamp": datetime.now().isoformat(),
        "metadata": {"solution": solution[:100]},
    }
    
    new_turn: ConversationTurn = {
        "role": "assistant",
        "content": f"{solution}\n\n请问还有其他问题需要帮助吗？",
        "timestamp": datetime.now().isoformat(),
    }
    
    return {
        "current_node": "auto_resolve",
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": state["conversation_history"] + [new_turn],
        "routing_path": state["routing_path"] + ["auto_resolve"],
        "is_completed": True,
        "completion_reason": "自动解决成功",
        "ticket_info": {
            **ticket_info,
            "ticket_status": "resolved",
            "update_time": datetime.now().isoformat(),
        },
    }