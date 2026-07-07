"""
全链路追踪模块
提供节点执行追踪装饰器和工单生命周期追踪
"""
import time
import functools
from typing import Callable, Any
from datetime import datetime
from src.utils.logger import get_logger
from src.utils.metrics import (
    NODE_EXECUTION_DURATION,
    NODE_EXECUTION_ERRORS,
    TICKET_DURATION,
    TICKET_COMPLETED,
)

logger = get_logger(__name__)


def trace_node(node_name: str):
    """
    节点执行追踪装饰器
    记录节点执行耗时、输入输出和异常信息
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state: dict, *args, **kwargs) -> dict:
            ticket_id = state.get("ticket_info", {}).get("ticket_id", "unknown")
            start_time = time.time()
            
            logger.info(
                "节点开始执行",
                node_name=node_name,
                ticket_id=ticket_id,
                current_intent=state.get("current_intent"),
                current_node=state.get("current_node"),
            )
            
            try:
                result = func(state, *args, **kwargs)
                duration = time.time() - start_time
                
                NODE_EXECUTION_DURATION.labels(node_name=node_name).observe(duration)
                
                logger.info(
                    "节点执行成功",
                    node_name=node_name,
                    ticket_id=ticket_id,
                    duration=f"{duration:.3f}s",
                    next_node=result.get("current_node"),
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                NODE_EXECUTION_ERRORS.labels(
                    node_name=node_name,
                    error_type=type(e).__name__,
                ).inc()
                
                logger.error(
                    "节点执行失败",
                    node_name=node_name,
                    ticket_id=ticket_id,
                    duration=f"{duration:.3f}s",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
        return wrapper
    return decorator


def trace_ticket_lifecycle(ticket_info: dict, is_final: bool = False):
    """
    工单生命周期追踪
    记录工单从创建到闭环的完整生命周期
    """
    ticket_id = ticket_info.get("ticket_id", "unknown")
    status = ticket_info.get("ticket_status", "unknown")
    product_type = ticket_info.get("product_type", "other")
    create_time = ticket_info.get("create_time")
    
    if is_final and create_time:
        try:
            create_dt = datetime.fromisoformat(create_time)
            duration = (datetime.now() - create_dt).total_seconds()
            
            completion_type = "resolved" if status == "resolved" else "escalated"
            TICKET_DURATION.labels(
                product_type=product_type,
                completion_type=completion_type,
            ).observe(duration)
            TICKET_COMPLETED.labels(completion_type=completion_type).inc()
            
            logger.info(
                "工单生命周期结束",
                ticket_id=ticket_id,
                status=status,
                duration=f"{duration:.3f}s",
                product_type=product_type,
            )
        except Exception as e:
            logger.error("工单生命周期追踪失败", ticket_id=ticket_id, error=str(e))
    else:
        logger.info(
            "工单状态更新",
            ticket_id=ticket_id,
            status=status,
            product_type=product_type,
        )