"""08 部署与快速上手：部署形态、生产要点、首次使用最小闭环（含两个「上线」开关）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


def demo_deploy_forms() -> None:
    print("--- A. 部署形态对比 ---")
    forms = [
        ("Standalone", "快速体验", "单进程起所有角色，内置注册与存储，勿用于生产"),
        ("Docker Compose", "学习/演示", "一键拉起 PG + ZK + Master/Worker/API/Alert"),
        ("伪集群", "预发/验证", "一台机器多进程，接近真实角色划分"),
        ("集群", "生产", "多 Master + 多 Worker + 外部 DB + 注册中心"),
        ("Kubernetes", "云原生", "官方 Helm Chart"),
    ]
    for name, scene, feature in forms:
        print(f"  {name:16} {scene:8} {feature}")
    print("\n  Docker Compose 体验：")
    print("    git clone https://github.com/apache/dolphinscheduler.git")
    print("    cd dolphinscheduler/deploy/docker && docker compose up -d")
    print("    访问 http://localhost:12345/dolphinscheduler/ui （默认 admin / dolphinscheduler123）\n")


def demo_prod_topology() -> None:
    print("--- B. 生产集群拓扑 ---")
    print("                    ┌─ LB（Nginx）─┐")
    print("  用户/第三方 ─────►│              │────► API Server ×2+")
    print("                    └──────────────┘")
    print("  Master ×2+      Worker ×N（按组分机器）     Alert ×2")
    print("      │                │                      │")
    print("      └─────── 注册中心（ZK ×3 / Etcd ×3）─────┘")
    print("                        │")
    print("              元数据库 MySQL（主从 + 定时备份）")
    print("              资源中心 HDFS / S3\n")
    checklist = [
        "JDK 版本符合所选 DS 版本要求（3.x: JDK 8/11）",
        "元数据库高可用 + 备份；连接池按并发调",
        "注册中心独立部署且高可用",
        "Master ≥ 2；Worker 按组分机组、按负载扩",
        "资源中心指向 HDFS/S3，不用 API 本地盘",
        "Alert 配好通道并实测一次",
        "日志目录磁盘监控（任务日志写在 Worker 本地，会胀）",
        "时区全链路统一（Server / DB / Worker / UI）",
    ]
    print("  检查清单:")
    for item in checklist:
        print(f"    [ ] {item}")
    print()


@dataclass
class MinimalLoop:
    """首次使用最小闭环：重点演示「工作流上线」和「调度上线」是两个独立开关。"""

    workflow_online: bool = False
    schedule_online: bool = False

    def cron_tick(self) -> None:
        if self.workflow_online and self.schedule_online:
            biz = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"    ⏰ cron 触发 → 生成流程实例，Shell 输出: bizdate=$[yyyy-MM-dd-1] → {biz}")
        else:
            missing = []
            if not self.workflow_online:
                missing.append("工作流未上线")
            if not self.schedule_online:
                missing.append("调度未上线")
            print(f"    ⏰ cron 到点但不触发：{' + '.join(missing)}")


def demo_minimal_loop() -> None:
    print("--- C. 首次使用最小闭环（7 步） ---")
    steps = [
        "安全中心：建租户（Worker 机上有同名 Linux 用户）→ 建用户并绑租户",
        "数据源中心：建一个 MySQL / Hive 数据源",
        "项目管理：建项目 demo",
        "工作流定义：拖一个 Shell 任务 echo \"bizdate=$[yyyy-MM-dd-1]\" → 保存 → 上线 ★",
        "定时调度：配 cron 0 0 2 * * ? → 调度上线 ★（两个开关别漏）",
        "手动运行 → 工作流实例看状态 → 点任务实例看日志",
        "故意把脚本改成 exit 1 → 重跑 → 观察失败告警与「从失败节点恢复」",
    ]
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s}")

    loop = MinimalLoop()
    print("\n  演示最容易漏的两个开关：")
    print("  情况1：只把工作流上线，忘了调度上线")
    loop.workflow_online, loop.schedule_online = True, False
    loop.cron_tick()
    print("  情况2：两个都上线")
    loop.schedule_online = True
    loop.cron_tick()
    print("  结论：定义要上线 + 调度也要上线，缺一不可。\n")


def demo_deploy_issues() -> None:
    print("--- D. 常见部署问题 ---")
    issues = [
        ("页面打不开 / 502", "API 进程是否活；12345 端口；nginx 转发"),
        ("任务一直「提交成功」不运行", "Worker 是否注册成功（看注册中心）；Worker 组是否匹配"),
        ("Master 频繁容错", "Master 日志；ZK 会话超时参数；机器资源"),
        ("元数据库连接爆", "连接池上限；慢 SQL；实例表是否过大"),
        ("改完配置不生效", "是否重启对应角色；改的是不是对的 conf 目录"),
    ]
    for problem, check in issues:
        print(f"  {problem:26} → {check}")


def run() -> None:
    print("=== 08 部署与快速上手 ===\n")
    demo_deploy_forms()
    demo_prod_topology()
    demo_minimal_loop()
    demo_deploy_issues()
