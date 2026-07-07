"""
业务模板测试
测试各业务模板的配置正确性
"""
import pytest
from src.config.templates import get_template, TEMPLATE_REGISTRY
from src.config.templates.base_template import BaseBusinessTemplate


class TestTemplateRegistry:
    """模板注册表测试"""

    def test_all_templates_registered(self):
        assert "flight" in TEMPLATE_REGISTRY
        assert "hotel" in TEMPLATE_REGISTRY
        assert "train" in TEMPLATE_REGISTRY

    def test_get_template_by_type(self):
        flight = get_template("flight")
        assert flight.product_type == "flight"

        hotel = get_template("hotel")
        assert hotel.product_type == "hotel"

        train = get_template("train")
        assert train.product_type == "train"

    def test_get_unknown_template_fallback(self):
        unknown = get_template("unknown")
        assert isinstance(unknown, BaseBusinessTemplate)
        assert unknown.product_type == "other"


class TestFlightTemplate:
    """机票模板测试"""

    def test_flight_intent_keywords(self):
        template = get_template("flight")
        keywords = template.get_intent_keywords()
        # 机票特有意图
        assert "baggage" in keywords
        assert "checkin" in keywords
        assert "航班取消" in keywords["refund"]

    def test_flight_required_credentials(self):
        template = get_template("flight")
        creds = template.get_required_credentials()
        assert "order_no" in creds
        assert "ticket_no" in creds

    def test_flight_auto_resolve_enabled(self):
        template = get_template("flight")
        rules = template.get_routing_rules()
        assert rules["auto_refund_enabled"] is True
        assert rules["auto_reschedule_enabled"] is True

    def test_flight_resolution_template(self):
        template = get_template("flight")
        refund_msg = template.get_resolution_template("refund")
        assert "机票" in refund_msg
        assert "退票" in refund_msg


class TestHotelTemplate:
    """酒店模板测试"""

    def test_hotel_intent_keywords(self):
        template = get_template("hotel")
        keywords = template.get_intent_keywords()
        assert "modify" in keywords
        assert "加床" in keywords["modify"]

    def test_hotel_required_credentials(self):
        template = get_template("hotel")
        creds = template.get_required_credentials()
        assert "order_no" in creds
        assert "ticket_no" not in creds

    def test_hotel_auto_resolve_disabled_for_refund(self):
        template = get_template("hotel")
        rules = template.get_routing_rules()
        assert rules["auto_refund_enabled"] is False
        assert rules["auto_reschedule_enabled"] is False

    def test_hotel_credential_prompt(self):
        template = get_template("hotel")
        prompt = template.get_credential_prompt("order_no")
        assert "酒店" in prompt


class TestTrainTemplate:
    """火车票模板测试"""

    def test_train_intent_keywords(self):
        template = get_template("train")
        keywords = template.get_intent_keywords()
        assert "seat" in keywords
        assert "选座" in keywords["seat"]

    def test_train_required_credentials(self):
        template = get_template("train")
        creds = template.get_required_credentials()
        assert "order_no" in creds

    def test_train_resolution_template(self):
        template = get_template("train")
        refund_msg = template.get_resolution_template("refund")
        assert "12306" in refund_msg
        assert "退票费" in refund_msg


class TestBaseTemplate:
    """基类模板测试"""

    def test_default_fallbacks(self):
        template = BaseBusinessTemplate()
        # 默认意图关键词
        assert "refund" in template.get_intent_keywords()
        # 默认凭证要求
        assert template.get_required_credentials() == {"order_no"}
        # 默认路由规则
        rules = template.get_routing_rules()
        assert rules["intent_confidence_threshold"] == 0.5
        # 未知意图使用默认模板
        msg = template.get_resolution_template("unknown_intent")
        assert msg == template.resolution_templates["default"]

    def test_credentials_check(self):
        template = get_template("flight")
        # 完整凭证
        complete = [
            {"type": "order_no", "value": "123", "verified": True},
            {"type": "ticket_no", "value": "456", "verified": True},
        ]
        assert template.check_credentials_complete(complete) is True

        # 缺少凭证
        incomplete = [
            {"type": "order_no", "value": "123", "verified": True},
        ]
        assert template.check_credentials_complete(incomplete) is False

        # 未验证凭证
        unverified = [
            {"type": "order_no", "value": "123", "verified": False},
        ]
        assert template.check_credentials_complete(unverified) is False