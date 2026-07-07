"""
知识库调用节点
查询外部/内部 RAG 服务获取解决方案
"""
from typing import Dict, Any, List
from datetime import datetime
from src.state.schema import TicketState, RAGResult, WorkflowDecision, ConversationTurn
from src.utils.logger import get_logger
from src.services.rag_service import RAGService

logger = get_logger(__name__)


def query_knowledge_base(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    intent = state["current_intent"]
    
    query = f"{intent}: {ticket_info['customer_message']}"
    for turn in reversed(state["conversation_history"]):
        if turn["role"] == "user":
            query += " " + turn["content"]
    
    rag_service = RAGService()
    results = rag_service.query(query)
    
    logger.info(
        "knowledge_base_query_completed",
        ticket_id=ticket_info["ticket_id"],
        query=query[:100],
        result_count=len(results),
    )
    
    decision: WorkflowDecision = {
        "node_name": "knowledge_base",
        "action": "query_knowledge_base",
        "confidence": results[0]["confidence"] if results else 0.0,
        "timestamp": datetime.now().isoformat(),
        "metadata": {"query": query[:100], "result_count": len(results)},
    }
    
    new_turn: ConversationTurn = {
        "role": "assistant",
        "content": results[0]["answer"] if results else "暂无相关解决方案",
        "timestamp": datetime.now().isoformat(),
    }
    
    return {
        "rag_results": state["rag_results"] + results,
        "current_node": "knowledge_base",
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": state["conversation_history"] + [new_turn],
        "routing_path": state["routing_path"] + ["knowledge_base"],
    }