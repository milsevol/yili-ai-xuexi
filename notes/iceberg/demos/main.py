#!/usr/bin/env python3
"""Iceberg 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与湖仓一体", "Iceberg 是开放表格式：在 Parquet/ORC 上加元数据树 + 快照。解决 Hive 表的四大痛点：无 ACID、分区演进难、小文件、无 Time Travel。"),
    ("02", "架构与元数据层级", "Catalog 只存指针 → metadata.json → Manifest List → Manifest → Data File。每层都是索引，逐层裁剪。一次提交只原子切换 Catalog 指针。"),
    ("03", "表格式与文件组织", "数据文件支持 Parquet/ORC/Avro；Manifest 记录路径、分区、record_count、每列 min/max/null_count。COW 重写文件，MOR 写 delete file。"),
    ("04", "ACID 与快照隔离", "元数据不可变 + Catalog CAS 换指针 = 原子提交。并发写用乐观锁，冲突则 retry/rebase。快照隔离读不阻塞写。小文件靠 compaction 合并。"),
    ("05", "分区演进与隐藏分区", "分区由 days(ts)/hours(ts)/bucket(N,col)/truncate(W,col) 派生，不是真实列。partition spec 可演进：新增/删除/替换，历史数据不重写。"),
    ("06", "Time Travel 与版本管理", "每个快照不可变：VERSION AS OF / TIMESTAMP AS OF 查历史；rollback/cherrypick/set_current 切版本；branch 可写、tag 只读；记得 expire_snapshots。"),
    ("07", "Schema 演进与数据类型", "靠列 ID 而非列名：加列读旧文件为 null、删列不复用 ID、改名自动映射、类型只允许安全提升（int→long）。分区 spec 变更与 Schema 变更是两件事。"),
    ("08", "与 Spark/Flink/Hive 集成", "Spark 批写、Flink checkpoint 两阶段提交做 exactly-once、Trino 交互查询、Hive 4 只读。关键是 runtime jar 版本匹配 + 共享 Catalog + 统一维护。"),
    ("09", "性能优化与实践", "写入控制 128MB 文件 + hash 分发；定期 rewrite_data_files（binpack/sort/zorder）、rewrite_manifests、expire_snapshots、remove_orphan_files。"),
    ("10", "生态对比与 FAQ", "多引擎开放选 Iceberg，高频 CDC Upsert 选 Hudi，Databricks 选 Delta，Flink 流批一体选 Paimon。湖仓落地：统一 Catalog + Parquet + 分工写入 + 统一维护。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Iceberg 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（元数据层级）、04（ACID）、05（隐藏分区）、09（调优）。")
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
    print("Iceberg · 终端摘要版\n")
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
