"""
凭证询问节点
检测缺失凭证并引导用户补充
"""
from typing import Dict, Any
from datetime import datetime
from src.state.schema import TicketState, WorkflowDecision, ConversationTurn
from src.utils.logger import get_logger
from src.config.templates import get_template

logger = get_logger(__name__)


def ask_credentials(state: TicketState) -> Dict[str, Any]:
    ticket_info = state["ticket_info"]
    
    # 根据业务类型加载对应模板获取凭证要求
    template = get_template(ticket_info.get("product_type", "other"))
    required_credentials = template.get_required_credentials()
    provided_credentials = {cred["type"] for cred in state["credentials"] if cred["verified"]}
    
    missing_credentials = required_credentials - provided_credentials
    
    # 使用模板中的提示语
    if missing_credentials:
        first_missing = list(missing_credentials)[0]
        ask_message = template.get_credential_prompt(first_missing)
    else:
        ask_message = "请提供相关信息，以便我为您查询。"
    
    logger.info(
        "asking_for_credentials",
        ticket_id=ticket_info["ticket_id"],
        missing_credentials=list(missing_credentials),
    )
    
    decision: WorkflowDecision = {
        "node_name": "ask_credentials",
        "action": "ask_missing_credentials",
        "confidence": 0.8,
        "timestamp": datetime.now().isoformat(),
        "metadata": {"missing_credentials": list(missing_credentials)},
    }
    
    new_turn: ConversationTurn = {
        "role": "assistant",
        "content": ask_message,
        "timestamp": datetime.now().isoformat(),
    }
    
    return {
        "current_node": "ask_credentials",
        "workflow_decisions": state["workflow_decisions"] + [decision],
        "conversation_history": state["conversation_history"] + [new_turn],
        "routing_path": state["routing_path"] + ["ask_credentials"],
    }