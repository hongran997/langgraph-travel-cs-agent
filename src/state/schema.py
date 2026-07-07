"""
工单状态结构体定义
定义了工单信息、凭证信息、RAG结果、工作流决策、对话轮次等核心数据类型
"""
from typing import TypedDict, List, Optional, Dict, Any, Literal
from langchain_core.messages import BaseMessage


class TicketInfo(TypedDict):
    ticket_id: str
    order_id: str
    user_id: str
    product_type: Literal["flight", "hotel", "train", "other"]
    ticket_status: Literal["pending", "processing", "resolved", "escalated"]
    create_time: str
    update_time: str
    customer_message: str


class CredentialInfo(TypedDict):
    type: Literal["order_no", "ticket_no", "identity_card", "phone"]
    value: str
    verified: bool


class RAGResult(TypedDict):
    source: Literal["external", "internal"]
    query: str
    answer: str
    confidence: float
    sources: List[str]
    timestamp: str


class WorkflowDecision(TypedDict):
    node_name: str
    action: str
    confidence: float
    timestamp: str
    metadata: Dict[str, Any]


class ConversationTurn(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str


class TicketState(TypedDict):
    ticket_info: TicketInfo
    conversation_history: List[ConversationTurn]
    current_intent: Optional[str]
    intent_confidence: float
    credentials: List[CredentialInfo]
    rag_results: List[RAGResult]
    workflow_decisions: List[WorkflowDecision]
    current_node: str
    routing_path: List[str]
    need_human_escalation: bool
    escalation_reason: Optional[str]
    is_completed: bool
    completion_reason: Optional[str]