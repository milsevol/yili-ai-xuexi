"""最小 DAG 执行器：用拓扑顺序模拟海豚调度的任务推进。"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    KILLED = "killed"


@dataclass
class TaskNode:
    name: str
    run: Callable[[], None]
    retries: int = 0
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0


@dataclass
class WorkflowResult:
    success: bool
    order: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    statuses: Dict[str, TaskStatus] = field(default_factory=dict)


class DagExecutor:
    """入度为 0 的节点可运行；支持并行层、失败策略 continue/end。"""

    def __init__(
        self,
        tasks: Dict[str, TaskNode],
        edges: List[tuple],
        failure_strategy: str = "end",
        verbose: bool = True,
    ):
        self.tasks = tasks
        self.failure_strategy = failure_strategy  # end | continue
        self.verbose = verbose
        self.succ: Dict[str, List[str]] = defaultdict(list)
        self.pred_count: Dict[str, int] = {n: 0 for n in tasks}
        for u, v in edges:
            self.succ[u].append(v)
            self.pred_count[v] += 1
        self._validate_acyclic()

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _validate_acyclic(self) -> None:
        indeg = dict(self.pred_count)
        q = deque([n for n, c in indeg.items() if c == 0])
        seen = 0
        while q:
            u = q.popleft()
            seen += 1
            for v in self.succ[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        if seen != len(self.tasks):
            raise ValueError("DAG 中存在环，无法调度")

    def run(self) -> WorkflowResult:
        remaining_pred = dict(self.pred_count)
        ready = deque([n for n, c in remaining_pred.items() if c == 0])
        order: List[str] = []
        failed: List[str] = []
        aborted = False

        while ready and not aborted:
            # 同一「波次」视为可并行
            wave = list(ready)
            ready.clear()
            self._log(f"  >> 就绪并行组: {wave}")

            wave_failed = False
            for name in wave:
                if aborted:
                    self.tasks[name].status = TaskStatus.KILLED
                    continue
                ok = self._run_task(name)
                order.append(name)
                if ok:
                    for nxt in self.succ[name]:
                        remaining_pred[nxt] -= 1
                        if remaining_pred[nxt] == 0:
                            ready.append(nxt)
                else:
                    failed.append(name)
                    wave_failed = True
                    if self.failure_strategy == "end":
                        aborted = True
                        for other in wave:
                            if other != name and self.tasks[other].status == TaskStatus.PENDING:
                                self.tasks[other].status = TaskStatus.KILLED
                                self._log(f"  !! 失败策略=结束，杀掉并行任务意图: {other}")
                        for n, node in self.tasks.items():
                            if node.status == TaskStatus.PENDING:
                                node.status = TaskStatus.KILLED
                        break

            if wave_failed and self.failure_strategy == "continue":
                self._log("  .. 失败策略=继续，本波其余任务已执行完毕，后继不再解锁失败分支")

        statuses = {n: t.status for n, t in self.tasks.items()}
        success = not failed and all(
            t.status in (TaskStatus.SUCCESS, TaskStatus.SKIPPED) for t in self.tasks.values()
        )
        return WorkflowResult(success=success, order=order, failed=failed, statuses=statuses)

    def _run_task(self, name: str) -> bool:
        node = self.tasks[name]
        while True:
            node.attempts += 1
            node.status = TaskStatus.RUNNING
            self._log(f"  -> 运行 {name} (attempt {node.attempts}/{node.retries + 1})")
            try:
                node.run()
                node.status = TaskStatus.SUCCESS
                self._log(f"  OK {name}")
                return True
            except Exception as exc:  # noqa: BLE001 — 演示用
                self._log(f"  FAIL {name}: {exc}")
                if node.attempts <= node.retries:
                    self._log(f"  .. 重试 {name}")
                    continue
                node.status = TaskStatus.FAILED
                return False
