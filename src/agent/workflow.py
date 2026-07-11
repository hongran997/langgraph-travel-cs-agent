"""
LangGraph 状态机工作流
定义工单状态流转图，包含意图识别、知识库查询、分支路由等节点
"""
from langgraph.graph import StateGraph, END
from src.state.schema import TicketState
from src.agent.nodes import (
    recognize_intent,
    query_knowledge_base,
    route_decision,
    human_escalation,
    ask_credentials,
    auto_resolve,
)
from src.config.settings import settings
from src.services.redis_service import RedisService
from src.utils.logger import get_logger
from src.utils.tracing import trace_node

logger = get_logger(__name__)


def build_workflow() -> StateGraph:
    workflow = StateGraph(TicketState)
    
    workflow.add_node("recognize_intent", trace_node("意图识别")(recognize_intent))
    workflow.add_node("query_knowledge_base", trace_node("知识库查询")(query_knowledge_base))
    workflow.add_node("route_decision", trace_node("分支路由")(route_decision))
    workflow.add_node("human_escalation", trace_node("人工兜底")(human_escalation))
    workflow.add_node("ask_credentials", trace_node("凭证询问")(ask_credentials))
    workflow.add_node("auto_resolve", trace_node("自动解决")(auto_resolve))
    
    workflow.set_entry_point("recognize_intent")
    
    workflow.add_conditional_edges(
        "recognize_intent",
        _after_intent_recognition,
        {
            "query_knowledge_base": "query_knowledge_base",
            "human_escalation": "human_escalation",
        },
    )
    workflow.add_edge("query_knowledge_base", "route_decision")
    
    workflow.add_conditional_edges(
        "route_decision",
        _get_next_node,
        {
            "ask_credentials": "ask_credentials",
            "human_escalation": "human_escalation",
            "auto_resolve": "auto_resolve",
            "ask_clarification": "recognize_intent",
            "recognize_intent": "recognize_intent",
        },
    )
    
    workflow.add_conditional_edges(
        "ask_credentials",
        _after_ask_credentials,
        {
            "__end__": END,
            "route_decision": "route_decision",
        },
    )
    workflow.add_edge("human_escalation", END)
    workflow.add_edge("auto_resolve", END)
    
    return workflow


def _after_intent_recognition(state: TicketState) -> str:
    intent = state.get("current_intent")
    confidence = state.get("intent_confidence", 0.0)
    # 只有完全无法识别意图时（inquiry + 0.5 = 无关键词命中），才直接转人工
    if intent == "inquiry" and confidence <= 0.5:
        return "human_escalation"
    return "query_knowledge_base"


def _get_next_node(state: TicketState) -> str:
    decisions = state["workflow_decisions"]
    if not decisions:
        return "recognize_intent"
    
    last_decision = decisions[-1]
    action = last_decision["action"]
    
    if action == "ask_credentials":
        return "ask_credentials"
    elif action == "auto_resolve":
        return "auto_resolve"
    elif action == "escalate_to_human":
        return "human_escalation"
    elif action == "ask_clarification":
        return "ask_clarification"
    else:
        return "recognize_intent"


def _after_ask_credentials(state: TicketState) -> str:
    decisions = state["workflow_decisions"]
    if not decisions:
        return "route_decision"
    
    last_decision = decisions[-1]
    action = last_decision.get("action", "")

    if action == "ask_missing_credentials":
        return "__end__"
    elif action == "escalate_to_human":
        return "__end__"
    return "route_decision"


def _build_retry_policy():
    """
    构建工作流节点的自动重试策略：
    - 最大重试 3 次
    - 指数退避（初始 1s，上限 10s，backoff_factor=2）
    - 仅对连接类、超时类异常重试
    """
    if not settings.node_retry_enabled:
        return None
    return {
        "stop_after_attempt": settings.node_retry_max_attempts,
        "retry_if_exception_type": (ConnectionError, TimeoutError,),
        "wait_exponential_jitter": True,
    }


def compile_workflow(with_checkpoint: bool = True):
    workflow = build_workflow()
    
    if with_checkpoint and settings.checkpoint_enabled:
        try:
            from langgraph.checkpoint.redis import RedisSaver
            redis_service = RedisService()
            checkpointer = RedisSaver(redis_service.client)
            app = workflow.compile(checkpointer=checkpointer)
            logger.info("workflow_compiled_with_checkpoint")
        except Exception as e:
            logger.warn("checkpoint_init_failed", error=str(e))
            app = workflow.compile()
    else:
        app = workflow.compile()
        logger.info("workflow_compiled_without_checkpoint")

    retry_policy = _build_retry_policy()
    if retry_policy:
        app = app.with_retry(**retry_policy)
        logger.info(
            "workflow_retry_policy_enabled",
            max_attempts=retry_policy["stop_after_attempt"],
            wait_exponential_jitter=retry_policy["wait_exponential_jitter"],
        )
    
    return app