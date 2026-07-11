"""
知识库调用节点
查询外部/内部 RAG 服务获取解决方案，支持通过 MCP 查询实时数据（如天气）
"""
import re
from typing import Dict, Any, List
from datetime import datetime
from src.state.schema import TicketState, RAGResult, WorkflowDecision, ConversationTurn
from src.utils.logger import get_logger
from src.services.rag_service import RAGService
from src.agent.mcp import get_weather_client

logger = get_logger(__name__)

# 天气查询关键词（中英文）
WEATHER_KEYWORDS = ["天气", "气温", "下雨", "下雪", "台风", "温度", "晴", "阴",
                    "weather", "temperature", "rain", "snow", "forecast"]


def _is_weather_query(text: str) -> bool:
    """判断用户消息是否与天气相关"""
    return any(kw in text for kw in WEATHER_KEYWORDS)


def _extract_city(text: str) -> str | None:
    """从用户消息中提取城市名称"""

    known_cities = ["北京", "上海", "广州", "深圳", "成都", "杭州",
                    "三亚", "哈尔滨", "昆明", "重庆", "西安", "厦门",
                    "南京", "武汉", "长沙", "青岛", "大连", "拉萨"]

    patterns = [
        r"(?:去|到|在|从)([\u4e00-\u9fff]{2,3})(?:的天气|天气)",
        r"([\u4e00-\u9fff]{2,3})的?(?:天气|气温|温度|天气预报)",
        r"([\u4e00-\u9fff]{2,3})(?:怎么样|如何|天气怎样)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            city = match.group(1)
            if city in known_cities:
                return city

    for city in known_cities:
        if city in text:
            return city

    return None


def query_knowledge_base(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    intent = state["current_intent"]

    # 拼接完整的用户查询文本
    query = f"{intent}: {ticket_info['customer_message']}"
    for turn in reversed(state["conversation_history"]):
        if turn["role"] == "user":
            query += " " + turn["content"]

    # 判断是否为天气查询，若是则走 MCP 而非 RAG
    weather_response = None
    if intent == "inquiry" and _is_weather_query(query):
        city = _extract_city(query)
        if city:
            try:
                weather_client = get_weather_client()
                weather_response = weather_client.call_tool(
                    "query_weather",
                    {"city": city},
                )
                if weather_response:
                    logger.info(
                        "通过MCP查询天气成功",
                        city=city,
                        response_length=len(weather_response),
                    )
            except Exception as e:
                logger.error("MCP天气查询失败", city=city, error=str(e))

    if weather_response:
        result: RAGResult = {
            "source": "external",
            "query": query[:200],
            "answer": weather_response,
            "confidence": 0.95,
            "sources": ["mcp-weather"],
            "timestamp": datetime.now().isoformat(),
        }
        results = [result]

        new_turn: ConversationTurn = {
            "role": "assistant",
            "content": weather_response,
            "timestamp": datetime.now().isoformat(),
        }

        decision: WorkflowDecision = {
            "node_name": "knowledge_base",
            "action": "query_knowledge_base",
            "confidence": 0.95,
            "timestamp": datetime.now().isoformat(),
            "metadata": {"query": query[:100], "source": "mcp-weather"},
        }

        logger.info(
            "knowledge_base_query_completed",
            ticket_id=ticket_info["ticket_id"],
            query=query[:100],
            source="mcp-weather",
        )

        return {
            "rag_results": state["rag_results"] + results,
            "current_node": "knowledge_base",
            "workflow_decisions": state["workflow_decisions"] + [decision],
            "conversation_history": state["conversation_history"] + [new_turn],
            "routing_path": state["routing_path"] + ["knowledge_base"],
            "is_completed": True,
            "completion_reason": "weather_query",
        }

    rag_service = RAGService()
    results = rag_service.query(query)

    new_turn: ConversationTurn = {
        "role": "assistant",
        "content": results[0]["answer"] if results else "暂无相关解决方案",
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(
        "knowledge_base_query_completed",
        ticket_id=ticket_info["ticket_id"],
        query=query[:100],
        result_count=len(results),
        source="rag",
    )

    decision: WorkflowDecision = {
        "node_name": "knowledge_base",
        "action": "query_knowledge_base",
        "confidence": results[0]["confidence"] if results else 0.0,
        "timestamp": datetime.now().isoformat(),
        "metadata": {"query": query[:100], "result_count": len(results)},
    }

    return {
        "rag_results": state["rag_results"] + results,
        "current_node": "knowledge_base",
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": state["conversation_history"] + [new_turn],
        "routing_path": state["routing_path"] + ["knowledge_base"],
    }
