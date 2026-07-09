"""
火车票业务模板
定义火车票业务的意图关键词、凭证要求、路由规则等
"""
from typing import Dict, List, Set
from .base_template import BaseBusinessTemplate


class TrainTemplate(BaseBusinessTemplate):
    """火车票业务模板"""

    product_type: str = "train"

    intent_keywords: Dict[str, List[str]] = {
        "refund": ["退票", "退火车票", "列车停运", "列车晚点"],
        "reschedule": ["改签", "变更到站", "改车次", "改时间", "变更"],
        "complaint": ["投诉", "抱怨", "不满意", "车厢环境", "服务态度"],
        "inquiry": ["查询", "查一下", "车次", "时刻表", "余票", "座位"],
        "booking": ["预订", "订票", "买票", "车次", "下单"],
        "cancel": ["取消", "作废", "撤销", "退订"],
        "seat": ["选座", "靠窗", "靠过道", "卧铺", "下铺"],
    }

    required_credentials: Set[str] = {"order_no"}

    routing_rules: Dict[str, any] = {
        "intent_confidence_threshold": 0.5,
        "rag_confidence_threshold": 0.6,
        "auto_resolve_enabled": True,
        # 火车票支持123直连退改签
        "auto_refund_enabled": True,
        "auto_reschedule_enabled": True,
    }

    resolution_templates: Dict[str, str] = {
        "refund": "已为您办理火车票退票，您可在12306官网或APP查看退款进度，退款将在1-15个工作日内退回，开车前8天以上免收退票费。",
        "reschedule": "已为您完成火车票改签，新车次信息已通过短信发送，请留意查收。",
        "cancel": "已为您取消火车票订单，退款将在1-15个工作日内原路返回。",
        "seat": "已为您查询座位信息，您可以在12306官网或APP上办理选座。",
        "default": "已为您处理火车票相关操作，如有其他问题请随时联系。",
    }

    credential_prompts: Dict[str, str] = {
        "order_no": "请提供您的火车票订单号，以便我为您查询车次信息。",
        "identity_card": "请提供乘车人身份证号，以便核实订单信息。",
    }