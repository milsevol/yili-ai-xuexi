"""09 运维实践与故障排查：失败恢复、Master failover、排障决策树、实例表膨胀。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

# 保证可从 demos/ 或章节直接导入 lib
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.dag import DagExecutor, TaskNode, TaskStatus  # noqa: E402


def _ok(name: str):
    def _run() -> None:
        print(f"     [{name}] 业务逻辑执行…")

    return _run


def _skip(name: str):
    """恢复时已成功的节点：不重跑，直接视为成功以解锁后继。"""

    def _run() -> None:
        print(f"     [{name}] 已成功，跳过（恢复语义）")

    return _run


def _always_fail(name: str):
    def _run() -> None:
        raise RuntimeError(f"{name} 失败（脚本 bug / 数据问题）")

    return _run


def demo_recover() -> None:
    print("--- A. 从失败节点恢复（最常用的流程级操作） ---")
    edges = [("extract", "dwd"), ("dwd", "dq"), ("dq", "ads")]

    print("  第一次运行：dwd 失败，失败策略=结束")
    tasks = {
        "extract": TaskNode("extract", _ok("extract")),
        "dwd": TaskNode("dwd", _always_fail("dwd")),
        "dq": TaskNode("dq", _ok("dq")),
        "ads": TaskNode("ads", _ok("ads")),
    }
    result = DagExecutor(tasks, edges, failure_strategy="end").run()
    print(f"  statuses={ {k: v.value for k, v in result.statuses.items()} }\n")

    print("  修好 dwd 后「从失败节点恢复」：extract 不重跑，只跑 dwd 及后继")
    recovered: Dict[str, TaskNode] = {}
    for name, node in tasks.items():
        if node.status is TaskStatus.SUCCESS:
            recovered[name] = TaskNode(name, _skip(name))
        else:
            recovered[name] = TaskNode(name, _ok(name))
    result2 = DagExecutor(recovered, edges).run()
    print(f"  success={result2.success} 顺序={result2.order}\n")
    print("  其他流程级操作：重跑（口径变了整体重算）/ 从当前节点执行 / 暂停停止（止血）\n")


def demo_master_failover() -> None:
    print("--- B. Master failover：宕机接管 ---")
    registry_log: List[str] = []

    class Master:
        def __init__(self, name: str) -> None:
            self.name = name
            self.instances: List[str] = []
            self.alive = True

        def heartbeat(self) -> None:
            if self.alive:
                registry_log.append(f"[ZK] 心跳 {self.name}")

    m1, m2 = Master("master-1"), Master("master-2")
    m1.instances = ["实例#1024 (运行中)", "实例#1025 (运行中)"]
    print(f"  {m1.name} 持有: {m1.instances}；{m2.name} 待命")
    m1.heartbeat()
    m2.heartbeat()

    print("  … master-1 宕机！")
    m1.alive = False
    print("  [ZK] 会话超时，master-1 临时节点消失")
    taken = m1.instances
    m1.instances = []
    m2.instances.extend(taken)
    for inst in taken:
        print(f"  [{m2.name}] 生成容错命令 → 接管 {inst}，重新推进")
    print(f"  接管后 {m2.name} 持有: {m2.instances}")
    print("  Worker 宕机同理：其上运行中任务被标记失败，靠任务重试/人工恢复。")
    print("  前提永远是：任务幂等！\n")


def demo_troubleshoot_tree() -> None:
    print("--- C. 排障决策树（高频症状 → 检查点） ---")
    tree = {
        "任务一直「提交成功」不运行": [
            "Worker 组名打错 → 没有匹配组的在线 Worker（最常见）",
            "Worker 负载超阈值（CPU/内存保护）→ 看 Worker 日志",
            "Master 线程池打满 → 看 master.exec-threads 与命令积压",
        ],
        "调度没触发": [
            "工作流未上线 或 调度未上线（两个开关）",
            "cron 写错（Quartz 方言，秒开头）",
            "时区错乱：Server 与预期时区不一致",
        ],
        "UI 看日志失败": [
            "对应 Worker 已下线 / 日志已清理",
            "API 到 Worker 网络不通",
        ],
        "Master 频繁容错": [
            "Master 日志；ZK 会话超时参数；机器资源",
            "ZK 抖动 → ZK 独立部署、调大会话超时",
        ],
    }
    for symptom, checks in tree.items():
        print(f"  症状: {symptom}")
        for i, c in enumerate(checks, 1):
            print(f"    {i}. {c}")
    print("\n  标准动线：UI 实例 → 任务日志（80% 在这定位）→ 区分调度问题/执行问题 → 角色 logs/\n")


def demo_instance_bloat() -> None:
    print("--- D. 实例表膨胀：t_ds_process_instance 无限增长 ---")
    days = 12
    rows_per_day = 200
    total = 0
    print("  日增实例 200 条；第 5 天补数 10 月整月 ×3 条工作流（93×3=279 实例/天 ×3 天）:")
    for day in range(1, days + 1):
        inc = rows_per_day
        if 5 <= day <= 7:  # 补数尖峰
            inc += 93 * 3
        total += inc
        bar = "█" * (inc // 40)
        mark = " ← 补数尖峰" if inc > rows_per_day else ""
        print(f"    第{day:2}天 +{inc:4} {bar}{mark}")
    print(f"  累计 {total} 行。实例表拖慢 UI 列表与 Master 扫表。")
    print("  治理：定期归档/清理历史实例；监控表大小与慢查询；大规模补数后主动检查一轮。")
    print("  补数防爆：串行补数、限并行度、低峰期补、调低补数流程优先级。\n")


def run() -> None:
    print("=== 09 运维实践与故障排查 ===\n")
    demo_recover()
    demo_master_failover()
    demo_troubleshoot_tree()
    demo_instance_bloat()
