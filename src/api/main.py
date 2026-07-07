"""
FastAPI 接口层
提供工单创建、消息交互、状态查询等 REST API
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from src.config.settings import settings
from src.state.schema import TicketState, TicketInfo, ConversationTurn
from src.agent.workflow import compile_workflow
from src.services.redis_service import RedisService
from src.utils.logger import get_logger
from src.utils.metrics import init_metrics, TICKET_CREATED, ACTIVE_TICKETS
from src.utils.tracing import trace_ticket_lifecycle

logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="基于 LangGraph 搭建有状态工单智能体",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.workflow = compile_workflow()
app.state.redis_service = RedisService()
init_metrics(settings.app_name, "0.1.0")


class CreateTicketRequest(BaseModel):
    user_id: str
    product_type: str = "other"
    customer_message: str


class TicketResponse(BaseModel):
    ticket_id: str
    ticket_status: str
    conversation_history: list
    current_node: str
    is_completed: bool


class AddMessageRequest(BaseModel):
    ticket_id: str
    user_message: str


@app.post("/api/v1/tickets", response_model=TicketResponse)
async def create_ticket(request: CreateTicketRequest):
    try:
        ticket_id = str(uuid4())
        now = datetime.now().isoformat()
        
        ticket_info: TicketInfo = {
            "ticket_id": ticket_id,
            "order_id": "",
            "user_id": request.user_id,
            "product_type": request.product_type,
            "ticket_status": "pending",
            "create_time": now,
            "update_time": now,
            "customer_message": request.customer_message,
        }
        
        initial_state: TicketState = {
            "ticket_info": ticket_info,
            "conversation_history": [],
            "current_intent": None,
            "intent_confidence": 0.0,
            "credentials": [],
            "rag_results": [],
            "workflow_decisions": [],
            "current_node": "start",
            "routing_path": [],
            "need_human_escalation": False,
            "escalation_reason": None,
            "is_completed": False,
            "completion_reason": None,
        }
        
        result = app.state.workflow.invoke(
            initial_state,
            config={"configurable": {"thread_id": ticket_id}},
        )
        
        app.state.redis_service.set_ticket(ticket_id, result)
        
        # 记录工单创建指标
        TICKET_CREATED.labels(product_type=request.product_type).inc()
        ACTIVE_TICKETS.inc()
        
        logger.info("工单创建成功", ticket_id=ticket_id, user_id=request.user_id)
        
        # 若工单已闭环，记录生命周期结束
        if result["is_completed"]:
            ACTIVE_TICKETS.dec()
            trace_ticket_lifecycle(result["ticket_info"], is_final=True)
        
        return TicketResponse(
            ticket_id=result["ticket_info"]["ticket_id"],
            ticket_status=result["ticket_info"]["ticket_status"],
            conversation_history=result["conversation_history"],
            current_node=result["current_node"],
            is_completed=result["is_completed"],
        )
    except Exception as e:
        logger.error("工单创建失败", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tickets/{ticket_id}/messages", response_model=TicketResponse)
async def add_message(ticket_id: str, request: AddMessageRequest):
    try:
        stored_state = app.state.redis_service.get_ticket(ticket_id)
        
        if not stored_state:
            raise HTTPException(status_code=404, detail="工单不存在")
        
        new_turn: ConversationTurn = {
            "role": "user",
            "content": request.user_message,
            "timestamp": datetime.now().isoformat(),
        }
        
        stored_state["conversation_history"].append(new_turn)
        stored_state["ticket_info"]["customer_message"] += " " + request.user_message
        stored_state["ticket_info"]["update_time"] = datetime.now().isoformat()
        
        result = app.state.workflow.invoke(
            stored_state,
            config={"configurable": {"thread_id": ticket_id}},
        )
        
        app.state.redis_service.set_ticket(ticket_id, result)
        
        # 若工单在本次交互后闭环，记录生命周期结束
        if result["is_completed"]:
            ACTIVE_TICKETS.dec()
            trace_ticket_lifecycle(result["ticket_info"], is_final=True)
        
        logger.info("消息添加成功", ticket_id=ticket_id)
        
        return TicketResponse(
            ticket_id=result["ticket_info"]["ticket_id"],
            ticket_status=result["ticket_info"]["ticket_status"],
            conversation_history=result["conversation_history"],
            current_node=result["current_node"],
            is_completed=result["is_completed"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("消息添加失败", ticket_id=ticket_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str):
    try:
        stored_state = app.state.redis_service.get_ticket(ticket_id)
        
        if not stored_state:
            raise HTTPException(status_code=404, detail="工单不存在")
        
        return TicketResponse(
            ticket_id=stored_state["ticket_info"]["ticket_id"],
            ticket_status=stored_state["ticket_info"]["ticket_status"],
            conversation_history=stored_state["conversation_history"],
            current_node=stored_state["current_node"],
            is_completed=stored_state["is_completed"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("工单查询失败", ticket_id=ticket_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/tickets/{ticket_id}")
async def delete_ticket(ticket_id: str):
    try:
        result = app.state.redis_service.delete_session(ticket_id)
        
        if result == 0:
            raise HTTPException(status_code=404, detail="工单不存在")
        
        logger.info("工单删除成功", ticket_id=ticket_id)
        return {"message": "工单删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("工单删除失败", ticket_id=ticket_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health")
async def health_check():
    return {"status": "健康", "service": settings.app_name, "version": "0.1.0"}


@app.get("/api/v1/metrics")
async def metrics():
    """Prometheus 指标暴露端点"""
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )