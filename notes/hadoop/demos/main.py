#!/usr/bin/env python3
"""Hadoop 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "HDFS 存、YARN 管资源、MapReduce 算。Hadoop 是底座，Spark/Flink 是跑在上面的计算引擎。"),
    ("02", "HDFS 架构与原理", "NameNode 管元数据、DataNode 存块，默认 128MB/块、3 副本。SecondaryNameNode 只合并 EditLog，不是热备。"),
    ("03", "HDFS 实践与运维", "put/get/ls/fsck/balancer 是日常。小文件吃 NN 内存（约 150B/对象），优先在上游合并。"),
    ("04", "MapReduce 原理", "Split→Map→环形缓冲/Spill→Shuffle→Sort→Reduce。Combiner 能减少 Shuffle 量，但必须满足结合律。"),
    ("05", "MapReduce 进阶", "倾斜看 Reduce 输入分布；广播 Join 消灭 Shuffle；加盐两阶段聚合是通用解法。"),
    ("06", "YARN 资源管理", "RM 分资源、NM 起 Container、AM 管作业。CapacityScheduler 默认；内存/vcore 预算别超卖。"),
    ("07", "Hadoop 生态", "Hive 做 SQL 数仓、HBase 做点查、ZooKeeper 做协调；采集/同步/调度按场景选型。"),
    ("08", "部署与集群规划", "NN 独立、DN 与 NM 混布；QJM 3 台 JournalNode + ZKFC 做 HA；format 只能一次。"),
    ("09", "运维与故障排查", "盯 NN 堆与对象数、DN 磁盘与坏块、YARN 队列与 AM 失败率。排障先看时间线与日志。"),
    ("10", "生态对比与 FAQ", "HDFS vs 对象存储、YARN vs K8s、MR vs Spark/Flink；「Hadoop 已死」要分层看。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Hadoop 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（HDFS）、04（MapReduce）、06（YARN）、09（排障）。")
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
    print("Hadoop · 终端摘要版\n")
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
        print("  python3 demos/main.py 02        # 打开并定位到第 2 章")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 02  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
