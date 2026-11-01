"""03 核心概念：Definition vs Instance，以及一次「上线→调度→实例」。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4


@dataclass
class WorkflowDefinition:
    name: str
    version: int = 1
    online: bool = False
    tasks: List[str] = field(default_factory=list)
    cron: Optional[str] = None


@dataclass
class TaskInstance:
    name: str
    status: str = "submitted"


@dataclass
class WorkflowInstance:
    defn_name: str
    defn_version: int
    biz_date: str
    instance_id: str = field(default_factory=lambda: uuid4().hex[:8])
    status: str = "running"
    tasks: Dict[str, TaskInstance] = field(default_factory=dict)


def run() -> None:
    print("=== 03 核心概念：定义 vs 实例 ===\n")

    # 租户 / 用户 / 项目（示意）
    tenant = "dw_tenant"
    user = "alice"
    project = "user_domain"
    print(f"租户={tenant} 用户={user} 项目={project}\n")

    defn = WorkflowDefinition(
        name="dwd_user_daily",
        tasks=["extract", "transform", "dq_check"],
        cron="0 0 2 * * ?",
    )
    print(f"创建工作流定义: {defn.name} v{defn.version} online={defn.online}")
    print("  （此时定时不会跑——未上线）")

    defn.online = True
    print(f"上线: {defn.name} v{defn.version} online={defn.online} cron={defn.cron}")

    # 模拟连续两天定时触发 → 两个实例，同一份定义
    base = datetime(2026, 11, 1)
    instances: List[WorkflowInstance] = []
    for day in range(2):
        biz = (base - timedelta(days=day)).strftime("%Y-%m-%d")
        inst = WorkflowInstance(defn.name, defn.version, biz)
        for t in defn.tasks:
            inst.tasks[t] = TaskInstance(t, status="success")
        inst.status = "success"
        instances.append(inst)
        print(
            f"触发实例 id={inst.instance_id} biz_date={inst.biz_date} "
            f"defn={inst.defn_name}@v{inst.defn_version} status={inst.status}"
        )

    print("\n关键点：")
    print("  - 定义改了要上线才影响后续实例")
    print("  - 每个 biz_date / 每次触发 → 新的流程实例 + 任务实例")
    print("  - 重跑/恢复是针对「实例」的运维动作，不是改定义")
