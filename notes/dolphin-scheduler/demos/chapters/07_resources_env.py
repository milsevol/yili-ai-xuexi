"""07 资源中心 · 数据源 · Worker 组与环境：分组路由与环境注入模拟。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Environment:
    """3.x 环境配置：执行任务前 Worker 先 source 的一组 export。"""

    name: str
    worker_group: str
    exports: List[str] = field(default_factory=list)


@dataclass
class Worker:
    name: str
    group: str
    envs: Dict[str, Environment] = field(default_factory=dict)

    def execute(self, task: str, env: Optional[Environment], resources: List[str]) -> None:
        print(f"  [{self.name}][组={self.group}] 接活: {task}")
        for res in resources:
            print(f"    资源中心下载到执行目录: {res}")
        if env:
            print(f"    source 环境 [{env.name}]:")
            for line in env.exports:
                print(f"      {line}")
        print(f"    执行完成: {task}")


def demo_resource_center() -> None:
    print("--- A. 资源中心：文件托管与下发 ---")
    backends = [
        ("API Server 本地磁盘", "学习/演示（默认）；生产勿用——唯一副本且多 API 实例不一致"),
        ("HDFS", "已有 Hadoop 体系的生产"),
        ("S3 / OSS / GCS", "云原生体系"),
    ]
    for name, usage in backends:
        print(f"  {name:22} {usage}")
    print("  好习惯: 按目录管理；jar 带版本号（user-etl-1.3.0.jar），发布=传新文件+改引用，可回滚。\n")


def demo_worker_group() -> None:
    print("--- B. Worker 组路由：任务按组选执行机 ---")
    spark_env = Environment(
        "spark3-env",
        "spark",
        [
            "export JAVA_HOME=/usr/lib/jvm/java-8",
            "export SPARK_HOME=/opt/spark3",
            "export PATH=$SPARK_HOME/bin:$PATH",
        ],
    )
    workers = [
        Worker("worker-a", "default"),
        Worker("worker-b", "spark", envs={"spark3-env": spark_env}),
        Worker("worker-c", "python-ml"),
    ]
    print("  在线 Worker:")
    for w in workers:
        print(f"    {w.name} 组={w.group}")

    print("\n  提交 spark_dwd（组=spark, 环境=spark3-env, 资源=user-etl-1.3.0.jar）:")
    group, env_name = "spark", "spark3-env"
    target = next((w for w in workers if w.group == group), None)
    assert target is not None
    target.execute("spark_dwd", target.envs[env_name], ["user-etl-1.3.0.jar"])

    print("\n  组名打错（组=sparck）——最高频踩坑：")
    typo = "sparck"
    target2 = next((w for w in workers if w.group == typo), None)
    if target2 is None:
        print(f"    没有组 [{typo}] 的在线 Worker → 任务一直「提交成功」不运行，永远等下去")


def demo_datasource() -> None:
    print("\n--- C. 数据源中心：连接集中托管 ---")
    datasources = [
        ("hive_dw", "HIVE", "jdbc:hive2://hive-server:10000/dw", "Kerberos 环境另配 principal + keytab"),
        ("mysql_ods", "MYSQL", "jdbc:mysql://mysql:3306/ods", "密码加密存储，不落脚本"),
        ("ck_ads", "CLICKHOUSE", "jdbc:clickhouse://ck:8123/ads", "按用户授权可见性"),
    ]
    for name, ds_type, url, note in datasources:
        print(f"  [{ds_type:10}] {name:10} {url:38} {note}")
    print("  好处：换库只改数据源一处；Hive 填 HiveServer2 的 JDBC 地址。\n")


def demo_symptoms() -> None:
    print("--- D. 排障症状对照 ---")
    symptoms = [
        ("测试能跑生产挂", "Worker 组指错，机器没对应客户端"),
        ("资源文件找不到", "任务没勾选关联资源 / 资源中心后端不通"),
        ("SQL 连不上", "数据源配置错 / Worker 到 DB 网络不通"),
        ("环境变量没生效", "任务没选环境，或环境没绑定该 Worker 组"),
        ("所有 Worker 都不接活", "负载超阈值（CPU/内存保护），看 Worker 日志"),
    ]
    for symptom, cause in symptoms:
        print(f"  {symptom:22} → {cause}")


def run() -> None:
    print("=== 07 资源中心 · 数据源 · Worker 组与环境 ===\n")
    demo_resource_center()
    demo_worker_group()
    demo_datasource()
    demo_symptoms()
