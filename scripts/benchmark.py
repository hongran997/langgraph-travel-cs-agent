"""
性能压测脚本
模拟并发工单请求，测试系统吞吐量和响应延迟
"""
import time
import asyncio
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from src.agent.workflow import compile_workflow
from src.state.schema import TicketState, TicketInfo


# 测试场景配置
SCENARIOS = [
    {"product_type": "flight", "message": "我要退票", "credentials": []},
    {"product_type": "flight", "message": "我要改签", "credentials": [
        {"type": "order_no", "value": "ORD123", "verified": True},
        {"type": "ticket_no", "value": "TICK456", "verified": True},
    ]},
    {"product_type": "hotel", "message": "我要退房", "credentials": [
        {"type": "order_no", "value": "ORD789", "verified": True},
    ]},
    {"product_type": "train", "message": "我要改签", "credentials": [
        {"type": "order_no", "value": "ORD321", "verified": True},
    ]},
]


def _make_state(scenario: dict, ticket_id: str) -> TicketState:
    """构造测试 State"""
    now = datetime.now().isoformat()
    ticket_info: TicketInfo = {
        "ticket_id": ticket_id,
        "order_id": "",
        "user_id": "benchmark-user",
        "product_type": scenario["product_type"],
        "ticket_status": "pending",
        "create_time": now,
        "update_time": now,
        "customer_message": scenario["message"],
    }
    return {
        "ticket_info": ticket_info,
        "conversation_history": [],
        "current_intent": None,
        "intent_confidence": 0.0,
        "credentials": scenario["credentials"],
        "rag_results": [],
        "workflow_decisions": [],
        "current_node": "start",
        "routing_path": [],
        "need_human_escalation": False,
        "escalation_reason": None,
        "is_completed": False,
        "completion_reason": None,
    }


def run_single_ticket(workflow, scenario, ticket_id):
    """执行单个工单并返回耗时"""
    state = _make_state(scenario, ticket_id)
    start = time.time()
    try:
        result = workflow.invoke(state, config={"configurable": {"thread_id": ticket_id}})
        duration = time.time() - start
        return {
            "ticket_id": ticket_id,
            "duration": duration,
            "success": True,
            "path": result["routing_path"],
            "completed": result["is_completed"],
            "error": None,
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "ticket_id": ticket_id,
            "duration": duration,
            "success": False,
            "path": [],
            "completed": False,
            "error": str(e),
        }


def benchmark_concurrent(total_tickets: int = 100, max_workers: int = 10):
    """并发压测"""
    print(f"开始压测: 总工单数={total_tickets}, 并发数={max_workers}")
    print("=" * 60)

    workflow = compile_workflow(with_checkpoint=False)
    results = []

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in range(total_tickets):
            scenario = SCENARIOS[i % len(SCENARIOS)]
            ticket_id = f"bench-{i:04d}"
            future = executor.submit(run_single_ticket, workflow, scenario, ticket_id)
            futures.append(future)

        for future in futures:
            results.append(future.result())

    total_duration = time.time() - start_time

    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    failed_count = total_tickets - success_count
    durations = [r["duration"] for r in results if r["success"]]

    print(f"总耗时: {total_duration:.3f}s")
    print(f"成功率: {success_count}/{total_tickets} ({success_count/total_tickets*100:.1f}%)")
    print(f"吞吐量: {total_tickets/total_duration:.2f} 工单/秒")
    print()

    if durations:
        print("延迟统计:")
        print(f"  平均延迟: {statistics.mean(durations)*1000:.2f}ms")
        print(f"  最小延迟: {min(durations)*1000:.2f}ms")
        print(f"  最大延迟: {max(durations)*1000:.2f}ms")
        print(f"  P50 延迟: {statistics.median(durations)*1000:.2f}ms")
        if len(durations) >= 10:
            sorted_durations = sorted(durations)
            p95_idx = int(len(sorted_durations) * 0.95)
            p99_idx = int(len(sorted_durations) * 0.99)
            print(f"  P95 延迟: {sorted_durations[p95_idx]*1000:.2f}ms")
            print(f"  P99 延迟: {sorted_durations[p99_idx]*1000:.2f}ms")
    print()

    # 流转路径统计
    path_counts = {}
    for r in results:
        path_key = " -> ".join(r["path"])
        path_counts[path_key] = path_counts.get(path_key, 0) + 1

    print("流转路径分布:")
    for path, count in sorted(path_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"  {path}: {count} ({count/total_tickets*100:.1f}%)")

    if failed_count > 0:
        print()
        print("错误详情:")
        for r in results:
            if not r["success"]:
                print(f"  {r['ticket_id']}: {r['error']}")

    return results


def benchmark_single_thread(total_tickets: int = 50):
    """单线程串行压测"""
    print(f"开始单线程压测: 总工单数={total_tickets}")
    print("=" * 60)

    workflow = compile_workflow(with_checkpoint=False)
    results = []

    start_time = time.time()
    for i in range(total_tickets):
        scenario = SCENARIOS[i % len(SCENARIOS)]
        ticket_id = f"bench-seq-{i:04d}"
        result = run_single_ticket(workflow, scenario, ticket_id)
        results.append(result)

    total_duration = time.time() - start_time
    durations = [r["duration"] for r in results if r["success"]]

    print(f"总耗时: {total_duration:.3f}s")
    print(f"吞吐量: {total_tickets/total_duration:.2f} 工单/秒")
    if durations:
        print(f"平均延迟: {statistics.mean(durations)*1000:.2f}ms")

    return results


if __name__ == "__main__":
    import sys

    # 默认参数
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print("LangGraph 工单智能体 性能压测")
    print("=" * 60)
    print()

    # 单线程基线
    benchmark_single_thread(min(total // 2, 50))
    print()

    # 并发压测
    benchmark_concurrent(total, workers)
    print()
    print("压测完成")