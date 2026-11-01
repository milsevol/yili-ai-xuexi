"""05 任务类型与资源：用「伪工作流配置」展示常见节点与资源引用。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ResourceRef:
    path: str
    kind: str  # file | jar | config


@dataclass
class DatasourceRef:
    name: str
    ds_type: str


@dataclass
class TaskConf:
    name: str
    task_type: str
    worker_group: str = "default"
    resources: List[ResourceRef] = field(default_factory=list)
    datasource: Optional[DatasourceRef] = None
    script: str = ""
    depends_on: List[str] = field(default_factory=list)


def run() -> None:
    print("=== 05 任务类型与资源（配置素描） ===\n")

    ds_hive = DatasourceRef("hive_dw", "HIVE")
    res_sql = ResourceRef("etl/dwd_user.sql", "file")
    res_jar = ResourceRef("jobs/user-etl.jar", "jar")
    res_sh = ResourceRef("scripts/publish.sh", "file")

    workflow: List[TaskConf] = [
        TaskConf(
            name="wait_upstream",
            task_type="DEPENDENT",
            script="依赖: project=ods_domain workflow=ods_user 昨日成功",
        ),
        TaskConf(
            name="spark_dwd",
            task_type="SPARK",
            worker_group="spark",
            resources=[res_jar],
            script="spark-submit --class com.dw.UserDwd ${jar} --bizdate ${bizdate}",
            depends_on=["wait_upstream"],
        ),
        TaskConf(
            name="sql_dq",
            task_type="SQL",
            datasource=ds_hive,
            resources=[res_sql],
            script="SELECT COUNT(*) FROM dwd_user WHERE dt='${bizdate}' ...",
            depends_on=["spark_dwd"],
        ),
        TaskConf(
            name="publish",
            task_type="SHELL",
            resources=[res_sh],
            script="bash publish.sh ${bizdate}",
            depends_on=["sql_dq"],
        ),
        TaskConf(
            name="notify",
            task_type="HTTP",
            script="POST https://hooks.example/report-ready {bizdate}",
            depends_on=["publish"],
        ),
    ]

    print("工作流节点：")
    for t in workflow:
        deps = ",".join(t.depends_on) if t.depends_on else "-"
        print(f"  [{t.task_type:10}] {t.name:14} worker={t.worker_group:8} deps={deps}")
        if t.datasource:
            print(f"               数据源: {t.datasource.name} ({t.datasource.ds_type})")
        if t.resources:
            print(f"               资源: {[r.path for r in t.resources]}")
        print(f"               摘要: {t.script[:70]}")

    print("\n记忆口诀：")
    print("  脚本进资源中心 · 连接进数据源 · 环境靠 Worker 组 · 跨流靠 DEPENDENT")
