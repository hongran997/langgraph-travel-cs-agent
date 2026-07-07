"""
业务模板基类
定义 OTA 业务模板的通用接口和默认配置
"""
from typing import Dict, List, Set, Any


class BaseBusinessTemplate:
    """业务模板基类，所有业务模板需继承此类"""

    # 业务类型标识
    product_type: str = "other"

    # 意图关键词映射表（子类可覆盖）
    intent_keywords: Dict[str, List[str]] = {
        "refund": ["退票", "退款", "退钱", "退费"],
        "reschedule": ["改签", "改期", "改时间", "变更"],
        "complaint": ["投诉", "抱怨", "不满意", "问题"],
        "inquiry": ["查询", "查一下", "什么", "怎么", "为什么"],
        "booking": ["预订", "订票", "预约", "下单"],
        "cancel": ["取消", "作废", "撤销"],
    }

    # 所需凭证类型（子类可覆盖）
    required_credentials: Set[str] = {"order_no"}

    # 路由规则配置
    routing_rules: Dict[str, Any] = {
        "intent_confidence_threshold": 0.5,
        "rag_confidence_threshold": 0.6,
        "auto_resolve_enabled": True,
    }

    # 自动解决回复模板
    resolution_templates: Dict[str, str] = {
        "refund": "已为您提交退票申请，退款将在3-7个工作日内原路返回。",
        "reschedule": "已为您完成改签操作，请查收新的行程信息。",
        "cancel": "已为您取消订单，退款将在3-7个工作日内处理。",
        "default": "已为您处理相关操作，请确认是否还有其他问题。",
    }

    # 凭证询问提示语
    credential_prompts: Dict[str, str] = {
        "order_no": "请提供您的订单号，以便我为您查询。",
    }

    def get_intent_keywords(self) -> Dict[str, List[str]]:
        """获取意图关键词映射表"""
        return self.intent_keywords

    def get_required_credentials(self) -> Set[str]:
        """获取所需凭证类型集合"""
        return self.required_credentials

    def get_routing_rules(self) -> Dict[str, Any]:
        """获取路由规则配置"""
        return self.routing_rules

    def get_resolution_template(self, intent: str) -> str:
        """获取自动解决回复模板"""
        return self.resolution_templates.get(intent, self.resolution_templates["default"])

    def get_credential_prompt(self, credential_type: str) -> str:
        """获取凭证询问提示语"""
        return self.credential_prompts.get(
            credential_type,
            f"请提供您的{credential_type}信息。",
        )

    def check_credentials_complete(self, credentials: List[dict]) -> bool:
        """检查凭证是否完整"""
        provided = {cred["type"] for cred in credentials if cred.get("verified", False)}
        return self.required_credentials.issubset(provided)