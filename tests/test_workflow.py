"""
工作流集成测试
测试完整工单流转逻辑
"""
import pytest
from datetime import datetime
from src.agent.workflow import compile_workflow
from src.state.schema import TicketState, TicketInfo


def _make_initial_state(product_type="flight", message=""):
    """构造初始 State"""
    now = datetime.now().isoformat()
    ticket_info: TicketInfo = {
        "ticket_id": "test-001",
        "order_id": "",
        "user_id": "user-001",
        "product_type": product_type,
        "ticket_status": "pending",
        "create_time": now,
        "update_time": now,
        "customer_message": message,
    }
    return {
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


class TestWorkflowIntegration:
    """工作流集成测试"""

    def test_flight_refund_auto_resolve_path(self):
        """测试机票退款自动解决路径"""
        workflow = compile_workflow(with_checkpoint=False)
        state = _make_initial_state(
            product_type="flight",
            message="我要退票",
        )
        # 模拟已有完整凭证（跳过凭证询问）
        state["credentials"] = [
            {"type": "order_no", "value": "ORD123", "verified": True},
            {"type": "ticket_no", "value": "TICK456", "verified": True},
        ]
        # 给 knowledge_base 节点提供模拟 RAG 结果
        # 由于 RAG 服务需要外部连接，这里只测试到路由节点前的路径
        result = workflow.invoke(state, config={"configurable": {"thread_id": "test-001"}})

        # 验证流转路径
        assert "intent_recognition" in result["routing_path"]
        assert "knowledge_base" in result["routing_path"]
        assert "routing" in result["routing_path"]

    def test_flight_missing_credentials_path(self):
        """测试机票缺少凭证路径"""
        workflow = compile_workflow(with_checkpoint=False)
        state = _make_initial_state(
            product_type="flight",
            message="我要退票",
        )
        result = workflow.invoke(state, config={"configurable": {"thread_id": "test-002"}})

        # 缺少凭证 -> 询问凭证
        assert "ask_credentials" in result["routing_path"]
        assert result["current_node"] == "ask_credentials"

    def test_hotel_refund_escalation_path(self):
        """测试酒店退款转人工路径"""
        workflow = compile_workflow(with_checkpoint=False)
        state = _make_initial_state(
            product_type="hotel",
            message="我要退房退款",
        )
        state["credentials"] = [
            {"type": "order_no", "value": "ORD123", "verified": True},
        ]
        result = workflow.invoke(state, config={"configurable": {"thread_id": "test-003"}})

        # 酒店退款按模板配置自动转人工
        assert "human_escalation" in result["routing_path"]
        assert result["is_completed"] is True
        assert result["ticket_info"]["ticket_status"] == "escalated"

    def test_low_confidence_escalation_path(self):
        """测试低置信度转人工路径"""
        workflow = compile_workflow(with_checkpoint=False)
        state = _make_initial_state(
            product_type="flight",
            message="*&^%$#@!",  # 无意义输入
        )
        state["credentials"] = [
            {"type": "order_no", "value": "ORD123", "verified": True},
            {"type": "ticket_no", "value": "TICK456", "verified": True},
        ]
        result = workflow.invoke(state, config={"configurable": {"thread_id": "test-004"}})

        # 低置信度 -> 转人工
        assert "human_escalation" in result["routing_path"]
        assert result["need_human_escalation"] is True

    def test_workflow_decisions_recorded(self):
        """测试工作流决策被完整记录"""
        workflow = compile_workflow(with_checkpoint=False)
        state = _make_initial_state(message="我要退票")
        result = workflow.invoke(state, config={"configurable": {"thread_id": "test-005"}})

        # 验证决策记录非空
        assert len(result["workflow_decisions"]) > 0
        # 每个决策都包含必要字段
        for decision in result["workflow_decisions"]:
            assert "node_name" in decision
            assert "action" in decision
            assert "timestamp" in decision

    def test_conversation_history_updated(self):
        """测试对话历史被更新"""
        workflow = compile_workflow(with_checkpoint=False)
        state = _make_initial_state(message="我要退票")
        result = workflow.invoke(state, config={"configurable": {"thread_id": "test-006"}})

        # 对话历史应有系统回复
        assert len(result["conversation_history"]) > 0
        # 最后一条是 ask_credentials 的回复
        assert result["conversation_history"][-1]["role"] == "assistant"