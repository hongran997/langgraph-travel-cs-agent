"""
节点单元测试
测试各个核心节点的独立功能
"""
import pytest
from datetime import datetime
from src.agent.nodes.intent_recognition import recognize_intent
from src.agent.nodes.routing import route_decision, _check_credentials
from src.agent.nodes.ask_credentials import ask_credentials
from src.agent.nodes.auto_resolve import auto_resolve
from src.agent.nodes.human_escalation import human_escalation
from src.config.templates import get_template


def _make_state(product_type="flight", message="", intent=None, confidence=0.0,
                credentials=None, rag_results=None, completed=False):
    """构造测试用 State"""
    return {
        "ticket_info": {
            "ticket_id": "test-001",
            "order_id": "",
            "user_id": "user-001",
            "product_type": product_type,
            "ticket_status": "pending",
            "create_time": datetime.now().isoformat(),
            "update_time": datetime.now().isoformat(),
            "customer_message": message,
        },
        "conversation_history": [],
        "current_intent": intent,
        "intent_confidence": confidence,
        "credentials": credentials or [],
        "rag_results": rag_results or [],
        "workflow_decisions": [],
        "current_node": "start",
        "routing_path": [],
        "need_human_escalation": False,
        "escalation_reason": None,
        "is_completed": completed,
        "completion_reason": None,
    }


class TestIntentRecognition:
    """意图识别节点测试"""

    def test_recognize_refund_intent(self):
        state = _make_state(message="我要退票")
        result = recognize_intent(state)
        assert result["current_intent"] == "refund"
        assert result["intent_confidence"] > 0

    def test_recognize_reschedule_intent(self):
        state = _make_state(message="我要改签")
        result = recognize_intent(state)
        assert result["current_intent"] == "reschedule"

    def test_recognize_flight_specific_intent(self):
        # 机票业务特有意图：行李
        state = _make_state(product_type="flight", message="行李超重怎么办")
        result = recognize_intent(state)
        assert result["current_intent"] == "baggage"

    def test_recognize_hotel_specific_intent(self):
        # 酒店业务特有意图：修改订单
        state = _make_state(product_type="hotel", message="我要加床")
        result = recognize_intent(state)
        assert result["current_intent"] == "modify"

    def test_recognize_unknown_intent(self):
        state = _make_state(message="随便说点什么")
        result = recognize_intent(state)
        assert result["current_intent"] == "inquiry"

    def test_decision_recorded(self):
        state = _make_state(message="我要退票")
        result = recognize_intent(state)
        assert len(result["workflow_decisions"]) == 1
        assert result["workflow_decisions"][0]["node_name"] == "intent_recognition"


class TestRouting:
    """分支路由节点测试"""

    def test_route_ask_credentials_when_missing(self):
        # 缺少凭证 -> 询问凭证
        state = _make_state(
            product_type="flight",
            intent="refund",
            confidence=0.9,
            credentials=[],
            rag_results=[{"confidence": 0.8}],
        )
        result = route_decision(state)
        assert result["workflow_decisions"][-1]["action"] == "ask_credentials"

    def test_route_auto_resolve_when_confident(self):
        # 高置信度 + 完整凭证 + RAG结果 -> 自动解决
        state = _make_state(
            product_type="flight",
            intent="refund",
            confidence=0.9,
            credentials=[{"type": "order_no", "value": "123", "verified": True},
                        {"type": "ticket_no", "value": "456", "verified": True}],
            rag_results=[{"confidence": 0.8, "answer": "可以退票"}],
        )
        result = route_decision(state)
        assert result["workflow_decisions"][-1]["action"] == "auto_resolve"

    def test_route_escalate_when_low_confidence(self):
        # 低置信度 -> 人工兜底
        state = _make_state(
            intent="refund",
            confidence=0.3,
            credentials=[{"type": "order_no", "value": "123", "verified": True}],
            rag_results=[{"confidence": 0.8}],
        )
        result = route_decision(state)
        assert result["workflow_decisions"][-1]["action"] == "escalate_to_human"
        assert result["need_human_escalation"] is True

    def test_hotel_refund_escalate(self):
        # 酒店退款按模板配置自动转人工
        state = _make_state(
            product_type="hotel",
            intent="refund",
            confidence=0.9,
            credentials=[{"type": "order_no", "value": "123", "verified": True}],
            rag_results=[{"confidence": 0.8}],
        )
        result = route_decision(state)
        assert result["workflow_decisions"][-1]["action"] == "escalate_to_human"

    def test_check_credentials_flight(self):
        # 机票需要订单号 + 票号
        template = get_template("flight")
        state = _make_state(credentials=[{"type": "order_no", "value": "123", "verified": True}])
        assert _check_credentials(state, template) is True  # 缺少 ticket_no

    def test_check_credentials_hotel(self):
        # 酒店只需要订单号
        template = get_template("hotel")
        state = _make_state(credentials=[{"type": "order_no", "value": "123", "verified": True}])
        assert _check_credentials(state, template) is False  # 已完整


class TestAskCredentials:
    """凭证询问节点测试"""

    def test_ask_flight_credentials(self):
        state = _make_state(product_type="flight", credentials=[])
        result = ask_credentials(state)
        # 机票模板提示语包含"机票订单号"
        assert "机票" in result["conversation_history"][-1]["content"]

    def test_ask_hotel_credentials(self):
        state = _make_state(product_type="hotel", credentials=[])
        result = ask_credentials(state)
        # 酒店模板提示语包含"酒店订单号"
        assert "酒店" in result["conversation_history"][-1]["content"]


class TestAutoResolve:
    """自动解决节点测试"""

    def test_auto_resolve_flight(self):
        state = _make_state(
            product_type="flight",
            intent="refund",
            rag_results=[{"confidence": 0.8, "answer": "test"}],
        )
        result = auto_resolve(state)
        assert result["is_completed"] is True
        assert result["ticket_info"]["ticket_status"] == "resolved"

    def test_auto_resolve_uses_template(self):
        # 无RAG结果时使用模板回复
        state = _make_state(product_type="train", intent="refund", rag_results=[])
        result = auto_resolve(state)
        # 火车票模板回复包含"12306"
        assert "12306" in result["conversation_history"][-1]["content"]


class TestHumanEscalation:
    """人工兜底节点测试"""

    def test_escalation_completes_ticket(self):
        state = _make_state(escalation_reason="测试转人工")
        result = human_escalation(state)
        assert result["is_completed"] is True
        assert result["ticket_info"]["ticket_status"] == "escalated"
        assert "人工客服" in result["conversation_history"][-1]["content"]

    def test_escalation_records_decision(self):
        state = _make_state(escalation_reason="测试")
        result = human_escalation(state)
        assert len(result["workflow_decisions"]) == 1
        assert result["workflow_decisions"][0]["action"] == "escalate"