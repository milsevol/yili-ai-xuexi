#!/usr/bin/env python3
"""ClickHouse 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "ClickHouse 是列式 OLAP 数据库，核心 MergeTree 引擎 + 向量化执行 + SIMD。同量级数据单表聚合通常比 Hive / Spark SQL / Trino 快 5–100 倍。适合实时看板、用户行为分析、日志分析。"),
    ("02", "架构与核心组件", "Server 进程同时承载 HTTP、查询引擎、存储引擎。数据写入后以 Part（列分片）落到磁盘，后台 Merge 线程异步合并成有序 Part。Distributed 引擎做跨节点路由，ReplicatedMergeTree + Keeper 保证副本一致性。"),
    ("03", "MergeTree 引擎家族", "MergeTree 基类 + ReplacingMergeTree（去重）+ SummingMergeTree（预求和）+ AggregatingMergeTree（预聚合）+ CollapsingMergeTree（抵消）+ VersionedCollapsingMergeTree（带版本抵消）。引擎选择直接决定数据存储行为和查询性能。"),
    ("04", "数据类型与 SQL", "类 PostgreSQL 方言，有 UInt/Int、FixedString、AggregateFunction、JSON 类型。核心坑：Nullable 列降低压缩率和查询性能、ORDER BY 必须是非 Nullable。INSERT 推荐批量 VALUES（≥ 5000 行）。"),
    ("05", "分区排序与索引", "PARTITION BY 分区裁剪（第一道关卡）、ORDER BY 排序键（决定物理顺序和主索引精度）、跳数索引 minmax/set/bloom_filter/ngrambf、Projections 预存多排序副本。设计口诀：最常用查询条件放最前。"),
    ("06", "向量化执行与查询原理", "列式存储 + SIMD = 高吞吐。SIMD 一次处理 64–256 行数据，比逐行快 5–10x。Pipeline 模式避免中间结果落盘。EXPLAIN PIPELINE 看分区裁剪、跳数索引、Marks 跳过比例。"),
    ("07", "分布式与集群", "每个节点对等（无 Master/Worker）。Distributed 引擎查询路由、ReplicatedMergeTree + ClickHouse Keeper 副本同步。写入推荐业务层直连本地表（不经过 Distributed 引擎）。集群规模从几个节点到上百节点。"),
    ("08", "物化视图与 CDC", "物化视图是写入触发器——源表 INSERT 自动把 SELECT 结果写到目标表。目标表必须是 MergeTree 家族引擎。TTL 自动过期。Kafka 引擎 + 物化视图实现 CDC 入仓，或 Flink CDC + ClickHouse Sink。"),
    ("09", "性能调优与实践", "Part 太多是第一杀手——从根源解决（批量写入）比调参数有效。写入：AsyncInsert 异步合并。查询：分区裁剪 → 跳数索引 → 主索引 → 列裁剪 → IN 代替 JOIN。Mutation（ALTER UPDATE/DELETE）慢，用 ReplacingMergeTree 替代。"),
    ("10", "生态对比与 FAQ", "ClickHouse vs Doris vs StarRocks vs TiDB vs HBase vs Trino：没有银弹。只做 ADS/报表层、追求极简 → ClickHouse；需要事务、MySQL 协议、复杂 JOIN → Doris/StarRocks；湖仓一体 → Iceberg + Spark。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 ClickHouse 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（架构）、03（MergeTree 引擎）、05（分区排序索引）、06（向量化执行）。")
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
    print("ClickHouse · 终端摘要版\n")
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
