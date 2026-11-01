"""04 DAG 与调度：拓扑执行、重试、失败策略、补数。"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 保证可从 demos/ 或章节直接导入 lib
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.dag import DagExecutor, TaskNode  # noqa: E402


def _ok(name: str):
    def _run() -> None:
        print(f"     [{name}] 业务逻辑执行…")

    return _run


def _fail_once(name: str, box: dict):
    def _run() -> None:
        if box.get("n", 0) < 1:
            box["n"] = box.get("n", 0) + 1
            raise RuntimeError("模拟瞬时失败")
        print(f"     [{name}] 重试后成功")

    return _run


def _always_fail(name: str):
    def _run() -> None:
        raise RuntimeError(f"{name} 永久失败")

    return _run


def demo_topo() -> None:
    print("--- A. 正常 DAG：并行分支 ---")
    tasks = {
        "extract": TaskNode("extract", _ok("extract")),
        "dwd": TaskNode("dwd", _ok("dwd")),
        "dq": TaskNode("dq", _ok("dq")),
        "ads": TaskNode("ads", _ok("ads")),
    }
    edges = [("extract", "dwd"), ("dwd", "dq"), ("dwd", "ads")]
    result = DagExecutor(tasks, edges).run()
    print(f"结果 success={result.success} 顺序={result.order}\n")


def demo_retry() -> None:
    print("--- B. 任务级失败重试 ---")
    box: dict = {}
    tasks = {
        "a": TaskNode("a", _ok("a")),
        "b": TaskNode("b", _fail_once("b", box), retries=2),
        "c": TaskNode("c", _ok("c")),
    }
    edges = [("a", "b"), ("b", "c")]
    result = DagExecutor(tasks, edges).run()
    print(f"结果 success={result.success} attempts(b)={tasks['b'].attempts}\n")


def demo_failure_strategy() -> None:
    print("--- C. 失败策略 end：并行任务失败则结束 ---")
    tasks = {
        "root": TaskNode("root", _ok("root")),
        "left": TaskNode("left", _always_fail("left")),
        "right": TaskNode("right", _ok("right")),
        "join": TaskNode("join", _ok("join")),
    }
    edges = [("root", "left"), ("root", "right"), ("left", "join"), ("right", "join")]
    result = DagExecutor(tasks, edges, failure_strategy="end").run()
    print(f"statuses={ {k: v.value for k, v in result.statuses.items()} }")
    print(f"failed={result.failed}\n")

    print("--- D. 失败策略 continue：尽量跑完并行分支 ---")
    tasks2 = {
        "root": TaskNode("root", _ok("root")),
        "left": TaskNode("left", _always_fail("left")),
        "right": TaskNode("right", _ok("right")),
        "join": TaskNode("join", _ok("join")),
    }
    result2 = DagExecutor(tasks2, edges, failure_strategy="continue").run()
    print(f"statuses={ {k: v.value for k, v in result2.statuses.items()} }")
    print("说明：left 失败不会解锁 join；right 仍可成功。\n")


def demo_backfill() -> None:
    print("--- E. 补数：按业务日期生成多个实例（串行示意） ---")
    start = datetime(2026, 10, 28)
    end = datetime(2026, 10, 30)
    day = start
    while day <= end:
        biz = day.strftime("%Y-%m-%d")
        print(f"  补数实例 biz_date={biz} → 跑完整 DAG（此处省略，只打印日期）")
        day += timedelta(days=1)
    print("  并行补数 = 多天同时跑；串行 = 一天成功再下一天。务必幂等！\n")


def run() -> None:
    print("=== 04 DAG 与调度演示 ===\n")
    demo_topo()
    demo_retry()
    demo_failure_strategy()
    demo_backfill()
