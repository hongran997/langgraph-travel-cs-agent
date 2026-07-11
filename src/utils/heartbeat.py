"""
心跳检测模块
为节点执行提供心跳监控，长时间未返回时输出告警日志
"""
import time
import threading
from typing import Callable, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)


def with_heartbeat(
    node_name: str,
    timeout: float = 30.0,
    interval: float = 5.0,
):
    """
    心跳检测装饰器

    节点执行期间，后台线程每隔 interval 秒打一次心跳日志。
    若执行时间超过 timeout，则输出告警日志（不中断节点执行，仅做告警）。

    Args:
        node_name: 节点名称，用于日志标识
        timeout: 超时阈值（秒），超过则输出告警
        interval: 心跳间隔（秒）

    用法:
        @with_heartbeat("知识库查询", timeout=60)
        def query_knowledge_base(state):
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            stop_event = threading.Event()
            result_holder = []
            exception_holder = []
            timed_out = threading.Event()

            def heartbeat_thread():
                start = time.time()
                warned = False
                while not stop_event.is_set():
                    elapsed = time.time() - start
                    if elapsed > timeout and not warned:
                        logger.warn(
                            "节点执行超时告警",
                            node_name=node_name,
                            elapsed=f"{elapsed:.1f}s",
                            timeout=f"{timeout}s",
                        )
                        warned = True
                    else:
                        logger.debug(
                            "节点心跳",
                            node_name=node_name,
                            elapsed=f"{elapsed:.1f}s",
                        )
                    stop_event.wait(timeout=interval)

            def run_thread():
                try:
                    result_holder.append(func(*args, **kwargs))
                except Exception as e:
                    exception_holder.append(e)
                finally:
                    stop_event.set()

            hb_thread = threading.Thread(target=heartbeat_thread, daemon=True)
            exec_thread = threading.Thread(target=run_thread, daemon=True)

            hb_thread.start()
            exec_thread.start()
            exec_thread.join()

            if exception_holder:
                raise exception_holder[0]

            return result_holder[0]

        return wrapper
    return decorator
