"""
指标收集模块
基于 Prometheus 收集系统吞吐量、成功率、延迟等指标
"""
from prometheus_client import Counter, Histogram, Gauge, Info
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 工单相关指标
TICKET_CREATED = Counter(
    "ticket_created_total",
    "工单创建总数",
    ["product_type"],
)

TICKET_COMPLETED = Counter(
    "ticket_completed_total",
    "工单完成总数",
    ["completion_type"],
)

TICKET_DURATION = Histogram(
    "ticket_duration_seconds",
    "工单处理耗时",
    ["product_type", "completion_type"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# 节点执行指标
NODE_EXECUTION_DURATION = Histogram(
    "node_execution_duration_seconds",
    "节点执行耗时",
    ["node_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0],
)

NODE_EXECUTION_ERRORS = Counter(
    "node_execution_errors_total",
    "节点执行错误数",
    ["node_name", "error_type"],
)

# RAG 服务指标
RAG_QUERY_DURATION = Histogram(
    "rag_query_duration_seconds",
    "RAG 查询耗时",
    ["source"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

RAG_QUERY_ERRORS = Counter(
    "rag_query_errors_total",
    "RAG 查询错误数",
    ["source", "error_type"],
)

# 当前活跃工单数
ACTIVE_TICKETS = Gauge(
    "active_tickets",
    "当前活跃工单数",
)

# 应用信息
APP_INFO = Info("app", "应用信息")


def init_metrics(app_name: str, app_version: str):
    """初始化指标应用信息"""
    APP_INFO.info({"name": app_name, "version": app_version})
    logger.info("指标收集模块初始化完成")