"""10 生态对比与 FAQ：海豚 vs Airflow、选型决策树、高频问题。"""

from __future__ import annotations


def demo_compare() -> None:
    print("--- A. 海豚 vs Airflow 对照 ---")
    rows = [
        ("DAG 定义", "UI 拖拽为主 + OpenAPI/Python SDK", "Python 代码（DAG as Code）"),
        ("目标用户", "数仓/数据运营（可视化）", "数据工程/平台工程（写代码）"),
        ("大数据任务", "内置 Spark/Flink/Hive 插件，页面化", "靠 Provider Operator，灵活但要写代码"),
        ("补数", "UI 选区间，串行/并行一键", "catchup/backfill，强但需懂框架"),
        ("多租户权限", "完善（项目/租户/资源授权）", "RBAC 有但偏粗"),
        ("测试", "相对弱（偏平台操作）", "pytest 直接测 DAG，CI 友好"),
        ("社区生态", "国内活跃，中文资料多", "全球活跃，Provider 生态巨大"),
    ]
    print(f"  {'维度':12} {'DolphinScheduler':38} {'Airflow'}")
    print(f"  {'-' * 12} {'-' * 38} {'-' * 30}")
    for dim, ds, af in rows:
        print(f"  {dim:12} {ds:38} {af}")
    print("\n  常见组合：数仓日批与可视化运维用海豚；复杂动态编排、ML 流水线用 Airflow 或自研。\n")


def demo_decision_tree() -> None:
    print("--- B. 选型决策树（4 个场景走一遍） ---")

    def decide(has_deps: bool, collab: str | None = None) -> str:
        if not has_deps:
            return "XXL-JOB / crontab（无复杂 DAG，只是分布式定时执行）"
        return {
            "ui": "DolphinScheduler（UI 可视化 + 数仓同学为主）",
            "python": "Airflow（Python 代码评审 + 工程化）",
            "k8s": "Argo Workflows（全 K8s + 容器化任务）",
        }[collab or "ui"]

    scenarios = [
        ("服务内定时任务，无依赖", False, None),
        ("数仓日批，运营同学也要看懂", True, "ui"),
        ("ML 流水线，团队全 Python", True, "python"),
        ("CI/ML 场景，全面 K8s 化", True, "k8s"),
    ]
    for scene, has_deps, collab in scenarios:
        print(f"  场景「{scene}」 → {decide(has_deps, collab)}")
    print()


def demo_faq() -> None:
    print("--- C. 高频 FAQ（精选 6 条） ---")
    faqs = [
        ("改了工作流，为什么还按旧逻辑跑？", "定义改了要重新「上线」；运行中的实例用的是创建时的快照。"),
        ("工作流上线了，定时就是不跑？", "检查调度是否单独「上线」；cron 方言（Quartz 秒开头）；时区。"),
        ("补数会重复写数据吗？", "平台只按区间生成实例；是否重复写取决于任务是否幂等。分区覆盖写是标准姿势。"),
        ("任务日志在哪里？", "Worker 本地执行目录，UI 查看时由 API 实时拉取；Worker 下线或清理后看不到。"),
        ("海豚适合跑实时流任务吗？", "不适合。它是批调度平台；流任务用 Flink 平台/K8s，海豚只负责启停编排。"),
        ("能用 API 触发工作流吗？", "可以。OpenAPI + Token（安全中心创建），第三方系统可编程触发、传参。"),
    ]
    for i, (q, a) in enumerate(faqs, 1):
        print(f"  Q{i}: {q}")
        print(f"      A: {a}")


def run() -> None:
    print("=== 10 生态对比与 FAQ ===\n")
    demo_compare()
    demo_decision_tree()
    demo_faq()
