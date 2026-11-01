"""01 概述：调度要解决的问题——用「裸 cron」对比「DAG 调度」。"""

from __future__ import annotations


def run() -> None:
    print("=== 01 概述：为什么需要工作流调度 ===\n")

    print("场景：每天要跑 4 步数仓任务，且有依赖。\n")
    print("[坏味道] 只用 crontab：")
    print("  02:00  extract.sh")
    print("  02:30  transform.sh   # 靠「多睡 30 分钟」赌 extract 已完成")
    print("  03:30  aggregate.sh")
    print("  04:00  publish.sh")
    print("  问题：上游慢了就脏读；失败了要人工找从哪重跑；补历史更痛苦。\n")

    print("[海豚思路] 用 DAG 声明依赖：")
    print("  extract → transform → aggregate → publish")
    print("  引擎保证：前驱成功才跑后继；失败可重试/从失败点恢复；可按业务日期补数。\n")

    steps = [
        ("定义", "在项目里拖拽/配置工作流模板（Definition）"),
        ("上线", "上线后定时或手动才会按该版本跑"),
        ("触发", "cron / 手动 / API / 补数 → 产生流程实例"),
        ("执行", "Master 拆任务，Worker 执行，状态回流"),
        ("运维", "日志、告警、重跑、从失败节点恢复"),
    ]
    print("一条主线：")
    for i, (title, desc) in enumerate(steps, 1):
        print(f"  {i}. {title}: {desc}")

    print("\n选型一句：数仓可视化协作偏海豚；Python DAG 即代码偏 Airflow。")
