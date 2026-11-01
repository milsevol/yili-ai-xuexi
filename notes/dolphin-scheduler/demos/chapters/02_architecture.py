"""02 架构：用角色扮演模拟 Master / Worker / Registry 一次调度。"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import List


@dataclass
class Worker:
    name: str
    group: str
    busy: bool = False

    def execute(self, task: str) -> str:
        self.busy = True
        result = f"{self.name}[{self.group}] 执行完成: {task}"
        self.busy = False
        return result


@dataclass
class Registry:
    masters: List[str] = field(default_factory=list)
    workers: List[Worker] = field(default_factory=list)

    def register_master(self, name: str) -> None:
        self.masters.append(name)
        print(f"[Registry] Master 上线: {name} → 当前 Masters={self.masters}")

    def register_worker(self, worker: Worker) -> None:
        self.workers.append(worker)
        print(f"[Registry] Worker 上线: {worker.name} group={worker.group}")

    def pick_worker(self, group: str) -> Worker:
        for w in self.workers:
            if w.group == group and not w.busy:
                return w
        raise RuntimeError(f"没有可用的 Worker 组: {group}")


@dataclass
class Master:
    name: str
    registry: Registry
    _rr: itertools.cycle = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rr = itertools.cycle([])

    def handle_command(self, command: str, dag_tasks: List[tuple]) -> None:
        """dag_tasks: [(task_name, worker_group), ...] 已按拓扑排好的简化队列。"""
        print(f"\n[{self.name}] 收到命令: {command}")
        print(f"[{self.name}] 创建流程实例，开始按拓扑提交任务…")
        for task_name, group in dag_tasks:
            worker = self.registry.pick_worker(group)
            print(f"[{self.name}] 分发 {task_name} → Worker组={group}")
            print(f"  {worker.execute(task_name)}")
        print(f"[{self.name}] 流程实例成功\n")


def run() -> None:
    print("=== 02 架构：Master / Worker / Registry 模拟 ===\n")

    registry = Registry()
    registry.register_master("master-1")
    registry.register_master("master-2")
    registry.register_worker(Worker("worker-a", "default"))
    registry.register_worker(Worker("worker-b", "spark"))
    registry.register_worker(Worker("worker-c", "default"))

    master = Master("master-1", registry)
    # 简化：假设已拓扑排序
    dag_tasks = [
        ("extract_ods", "default"),
        ("spark_dwd", "spark"),
        ("sql_dq", "default"),
        ("publish", "default"),
    ]
    master.handle_command("START_PROCESS (定时触发)", dag_tasks)

    print("对照真实系统：")
    print("  - Registry ≈ ZK/Etcd：心跳、发现、容错协调")
    print("  - Master：扫 command、拆 DAG、监控、failover")
    print("  - Worker：真正执行；按组隔离环境")
    print("  - API/UI/Alert/DB 未出演，但生产同样关键")
