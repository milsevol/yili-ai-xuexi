#!/usr/bin/env python3
"""Spark 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "Spark=内存计算+DAG 调度；批/流/SQL/ML 一套引擎；离线选 Spark，强实时选 Flink。"),
    ("02", "架构与运行原理", "Driver 建 DAG 切 Stage，Cluster Manager 分资源，Executor 跑 Task。口诀：Action 生 Job，Shuffle 切 Stage，Partition 定 Task。"),
    ("03", "RDD 核心抽象", "只读+分区+血缘+惰性。窄依赖流水线，宽依赖 Shuffle。cache 供 ≥2 个 Action 复用；checkpoint 切断血缘。"),
    ("04", "DataFrame 操作", "Schema+Catalyst+Tungsten 让 DF 快于 RDD。窗口/Join/聚合是主力；UDF 优先内置函数，其次 pandas_udf。"),
    ("05", "SQL 与 Catalyst", "SQL 与 DataFrame 同一优化器。四阶段：未解析→解析→优化→物理。白嫖优化：谓词下推、列裁剪、Join 策略。"),
    ("06", "Shuffle 与 Join", "Shuffle=磁盘+网络+序列化，最贵操作。小表广播消灭 Shuffle；shuffle.partitions 目标单 Task 100~200MB；3.x 开 AQE。"),
    ("07", "部署与资源", "local/standalone/YARN/K8s。executor 4~6 核、8~16G 为甜点；PySpark worker 吃 overhead 堆外内存。"),
    ("08", "性能调优", "先 UI 证据后改动。倾斜：广播/热点拆分/加盐/AQE；小文件：repartition/AQE 合并；GC：Kryo+G1+减对象。"),
    ("09", "Structured Streaming", "流=无限增长的表。Watermark 控乱序与状态过期；Exactly-Once 需可重放 Source+幂等 Sink+Checkpoint。"),
    ("10", "生态对比与 FAQ", "Spark 离线强、Flink 实时强；湖仓 Delta/Iceberg/Hudi 解决 ACID/演进；12 道高频面试题见笔记。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Spark 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 03（RDD）、06（Shuffle）、08（调优）。")
    webbrowser.open(uri)


def print_chapter(code: str) -> None:
    code = code.strip().zfill(2) if code.isdigit() else code.strip()
    for num, title, summary in CHAPTERS:
        if code in (num, num.lstrip("0") or "0"):
            print(f"\n## {num} {title}\n\n{summary}\n")
            return
    print(f"未找到章节: {code}，可选: {[c[0] for c in CHAPTERS]}")
    sys.exit(1)


def cli_menu() -> None:
    print("Spark · 终端摘要版\n")
    for num, title, _ in CHAPTERS:
        print(f"  {num}  {title}")
    choice = input("\n选择章节编号（q 退出）: ").strip().lower()
    if choice not in ("q", "quit", "exit", ""):
        print_chapter(choice)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help"}:
        print("用法:")
        print("  python3 demos/main.py           # 打开可视化交互页")
        print("  python3 demos/main.py 06        # 打开并定位到第 6 章")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 06  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
