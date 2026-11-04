#!/usr/bin/env python3
"""Hive 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "Hive 把 HDFS 文件映射成表，用 SQL 查。4.x 回归 Metastore + SQL 兼容层，真正执行的是 Tez/Spark/Flink。"),
    ("02", "架构与核心组件", "Client → HiveServer2 → Compiler → Execution Engine，全程 Metastore 提供元数据。Remote 模式让 Spark/Flink/Trino 直连。"),
    ("03", "数据模型与存储格式", "内部表 DROP 删数据，外部表只删元数据。分区目录级切分，分桶文件级切分。ORC（ACID）vs Parquet（通用列式）。"),
    ("04", "SQL 与分区管理", "WHERE 里分区键必须等值才能触发分区裁剪。静态分区写死，动态分区 SET hive.exec.dynamic.partition=true。EXPLAIN 看裁剪是否生效。"),
    ("05", "数仓分层设计", "ODS 贴源 → DWD 明细清洗 → DWS 公共汇总 → ADS 应用明细。拉链表处理历史回溯（SCD Type 2），维度建模用星形模型。"),
    ("06", "执行引擎与 Tez/Spark 切换", "MR（废弃）→ Tez（4.x 默认，DAG 减少落盘）→ Spark（Catalyst 快，迭代支持）。SET hive.execution.engine=xxx 切引擎。"),
    ("07", "性能调优", "优先级：分区裁剪 → 谓词下推 → MapJoin 广播 → 倾斜处理 → CBO 基于代价优化 → 矢量化。自动 MapJoin ≤25MB 触发。"),
    ("08", "ACID 与事务", "ACID = ORC 文件格式 × Bucket 分桶表 × Compaction。MERGE/UPDATE/DELETE 通过 Delta 目录 + 后台合并实现。Iceberg/Hudi/Delta 正在取代。"),
    ("09", "Hive 与周边组件", "Metastore 是通用元数据中心，Spark SQL/Flink/Trino 直连 9083。湖仓表格式（Iceberg/Hudi/Delta）都能接 Hive Metastore 当 Catalog。"),
    ("10", "生态对比与 FAQ", "Hive on Tez 做 ETL、Spark SQL 做 ML、Trino 做交互式查询、ClickHouse 做 ADS 报表。湖仓一体后 Hive 回归 Metastore 基础设施。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Hive 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（架构）、03（存储格式）、05（数仓分层）、07（调优）。")
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
    print("Hive · 终端摘要版\n")
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
