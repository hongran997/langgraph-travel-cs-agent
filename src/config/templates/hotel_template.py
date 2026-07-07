"""
酒店业务模板
定义酒店业务的意图关键词、凭证要求、路由规则等
"""
from typing import Dict, List, Set
from .base_template import BaseBusinessTemplate


class HotelTemplate(BaseBusinessTemplate):
    """酒店业务模板"""

    product_type: str = "hotel"

    intent_keywords: Dict[str, List[str]] = {
        "refund": ["退房", "退款", "取消入住", "未入住退款"],
        "reschedule": ["改期", "改入住日期", "延期", "提前入住"],
        "complaint": ["投诉", "抱怨", "不满意", "卫生", "设施", "服务态度"],
        "inquiry": ["查询", "查一下", "酒店信息", "地址", "电话", "设施"],
        "booking": ["预订", "订房", "下单", "入住"],
        "cancel": ["取消", "作废", "撤销", "退订"],
        "modify": ["修改订单", "加床", "换房", "升级房型"],
    }

    required_credentials: Set[str] = {"order_no"}

    routing_rules: Dict[str, any] = {
        "intent_confidence_threshold": 0.5,
        "rag_confidence_threshold": 0.55,
        "auto_resolve_enabled": True,
        # 酒店退改政策较复杂，部分场景需人工确认
        "auto_refund_enabled": False,
        "auto_reschedule_enabled": False,
    }

    resolution_templates: Dict[str, str] = {
        "refund": "已收到您的退房申请，酒店将在核实后1-3个工作日内处理退款，具体金额以酒店政策为准。",
        "reschedule": "已为您记录改期需求，酒店确认后将通过短信通知您。",
        "cancel": "已为您提交酒店订单取消申请，取消政策以预订时规则为准。",
        "modify": "已为您记录订单修改需求，酒店确认后将通过短信通知您。",
        "default": "已为您处理酒店相关操作，如有其他问题请随时联系。",
    }

    credential_prompts: Dict[str, str] = {
        "order_no": "请提供您的酒店订单号，以便我为您查询入住信息。",
        "phone": "请提供预订时使用的手机号，以便核实订单。",
    }