#!/usr/bin/env python3
"""Flink 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "Flink 是真正的流计算引擎，统一批流，核心是 State、Checkpoint、Watermark、Exactly-Once。真正的流 vs Spark 的微批。"),
    ("02", "架构与运行原理", "JM 管集群，TM 跑 Task。StreamGraph → JobGraph（算子链）→ ExecutionGraph。Slot 是 TM 的资源分片，默认 Slot=CPU 核数。"),
    ("03", "DataStream API", "Source → Transformation → Sink。map/flatMap/filter/keyBy/process。KeyedProcessFunction 最灵活（状态 + Timer + 侧输出）。异步 IO 解高延迟。"),
    ("04", "时间语义与Watermark", "Event-Time 优先。Watermark 单调递增 = max_seen_ts - allowed_lateness。多上游取 min。迟到数据三策略：丢弃/延迟触发/侧输出。"),
    ("05", "Window窗口机制", "四种 Assigner（滚动/滑动/会话/全局）。增量 AggregateFunction 省状态。allowedLateness + 侧输出流处理迟到。Session 按 gap 切。"),
    ("06", "State与Checkpoint", "KeyedState 按 Key Group 分片。State Backend：生产用 RocksDB（磁盘 + Managed Memory）。Checkpoint Barrier 对齐保证 Exactly-Once，增量 checkpoint 降压力。"),
    ("07", "Flink SQL与Table API", "官方主推声明式 API。CDC 入湖（MySQL → Iceberg）是最炸裂场景。Temporal Join 关联维表。Flink SQL Gateway 1.20+。"),
    ("08", "部署与集群规划", "Standalone / YARN / K8s（生产首选）。JM HA 至少 2。TM 内存四件：Heap / Off-Heap / Managed(RocksDB) / Network Buffer。G1GC 推荐。"),
    ("09", "性能调优与故障排查", "排障路径：反压 → 倾斜 → Checkpoint → State → GC。Flink UI 看 Subtask Records。State TTL 清理过期 Key。RocksDB + 增量 checkpoint 是标配。"),
    ("10", "生态对比与 FAQ", "Flink=实时流，Spark=批/ML，Trino=交互查询，ClickHouse=OLAP。CDC vs SeaTunnel 是流引擎 vs 同步工具。流批一体 + 湖仓一体 = 现代数仓。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Flink 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（架构）、04（Watermark）、06（State/Checkpoint）、09（排障）。")
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
    print("Flink · 终端摘要版\n")
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
        print("  python3 demos/main.py 04        # 打开并定位到第 4 章（Watermark）")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 04  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
