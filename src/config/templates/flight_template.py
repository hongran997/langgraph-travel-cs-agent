"""
机票业务模板
定义机票业务的意图关键词、凭证要求、路由规则等
"""
from typing import Dict, List, Set
from .base_template import BaseBusinessTemplate


class FlightTemplate(BaseBusinessTemplate):
    """机票业务模板"""

    product_type: str = "flight"

    intent_keywords: Dict[str, List[str]] = {
        "refund": ["退票", "退机票", "航班取消", "航班延误", "非自愿退票"],
        "reschedule": ["改签", "改期", "改航班", "变更", "升舱", "降舱"],
        "complaint": ["投诉", "抱怨", "不满意", "服务质量", "航班问题"],
        "inquiry": ["查询", "查一下", "航班动态", "登机口", "行李", "值机"],
        "booking": ["预订", "订票", "买机票", "航班", "下单"],
        "cancel": ["取消", "作废", "撤销", "退订"],
        "baggage": ["行李", "托运", "随身携带", "超重"],
        "checkin": ["值机", "选座", "登机牌", "网上值机"],
    }

    required_credentials: Set[str] = {"order_no", "ticket_no"}

    routing_rules: Dict[str, any] = {
        "intent_confidence_threshold": 0.5,
        "rag_confidence_threshold": 0.6,
        "auto_resolve_enabled": True,
        # 机票业务支持自动退改签
        "auto_refund_enabled": True,
        "auto_reschedule_enabled": True,
    }

    resolution_templates: Dict[str, str] = {
        "refund": "已为您提交机票退票申请，非自愿退票将在1-3个工作日内全额退款，自愿退票按航司规定扣款后退回。",
        "reschedule": "已为您完成航班改签，新航班信息已通过短信发送，请留意查收。",
        "cancel": "已为您取消机票订单，退款金额将在3-7个工作日内原路返回。",
        "baggage": "已为您查询行李额信息，您的航班包含20kg免费托运行李额。",
        "checkin": "您可以在航班起飞前2小时通过APP或官网办理网上值机。",
        "default": "已为您处理机票相关操作，如有其他问题请随时联系。",
    }

    credential_prompts: Dict[str, str] = {
        "order_no": "请提供您的机票订单号（如：ORD-12345678），以便我为您查询。",
        "ticket_no": "请提供您的机票票号（13位数字），以便我为您处理退改签业务。",
        "identity_card": "请提供乘机人身份证号，以便核实订单信息。",
    }