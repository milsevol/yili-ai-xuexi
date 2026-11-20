#!/usr/bin/env python3
"""OceanBase 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "OceanBase 是蚂蚁自研的分布式关系型数据库：shared-nothing + Paxos 多副本，RPO=0、在线扩容、多租户、MySQL/Oracle 双兼容。适合金融核心、政务大集中与 Oracle 存量替换，不适合极小单机业务。"),
    ("02", "架构与核心组件", "OBServer 承担 SQL/事务/存储/Paxos；RootService 内置于 OBServer，负责调度与元数据；OBProxy 无状态路由。Zone 是故障域，分区副本组成 Paxos 组，Leader 读写、多数派提交。"),
    ("03", "存储引擎与多副本", "LSM-Tree：写入进 MemTable，冻结转储成增量 SSTable，后台 Major Compaction 合并成基线。clog 通过 Paxos 同步多数派后提交。编码 + 压缩带来高压缩率，读放大靠合并与索引缓解。"),
    ("04", "多租户与资源管理", "Resource Unit 定义资源规格，Resource Pool 定义份数与 Zone，Tenant 承载业务。租户独立 CPU/内存/日志盘/用户/兼容模式。三 Zone、UNIT_NUM=1 的租户需要 3 个 Unit。"),
    ("05", "SQL 与兼容模式", "建租户时选 MySQL 或 Oracle 模式，之后不能改。MySQL 模式用 LIMIT/AUTO_INCREMENT/information_schema；Oracle 模式用 ROWNUM/SEQUENCE/VARCHAR2/ALL_* 视图/PL-SQL。空串在 Oracle 模式按 NULL。"),
    ("06", "部署运维与性能调优", "OBD 适合 POC，OCP 适合生产；至少三 Zone、3F 起步。巡检看节点/租户/合并/磁盘/SQL。备份 = 数据备份 + 日志归档。调优先 SQL、索引、分区裁剪、统计信息，再动参数。"),
    ("07", "Oracle 迁移 OceanBase", "评估 → POC → 结构迁移 → 全量 → 增量 → 校验 → 割接 → 回滚。用 OMA/OMS 评估与迁移；重点处理无主键表、空串、字符语义、时区、IOT/AQ/调度等不兼容对象；回滚用 OMS 反向增量。"),
    ("08", "生态对比与 FAQ", "OB vs TiDB vs PolarDB-X vs GaussDB vs Oracle RAC：强一致、多租户、Oracle 兼容是 OB 的差异化。OLAP 交给 ClickHouse/StarRocks，缓存交给 Redis，离线交给 Hive/Spark。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 OceanBase 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    推荐顺序：02（架构与选主）→ 03（LSM 合并）→ 04（租户资源）→ 07（Oracle 迁移）。")
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
    print("OceanBase · 终端摘要版\n")
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
        print("  python3 demos/main.py 07        # 打开并定位到第 7 章")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 03  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
