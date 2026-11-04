#!/usr/bin/env python3
"""HBase 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "HBase 是建在 HDFS 上的分布式列式 KV：LSM-Tree 拉写性能、RowKey 有序、Region 分片扩容。高并发点查/范围扫，不做 Join。"),
    ("02", "架构与组件", "HMaster 管 Region 分配/Split（不扛读写）、RegionServer 扛读写/Flush/Compaction、ZooKeeper 当通讯录协调、WAL 保数据不丢。"),
    ("03", "数据模型与 RowKey", "RowKey + CF + Qualifier + Version。RowKey 设计决定热点：加盐、哈希、反转、业务前缀。时间戳不能单独当 RowKey——永远热点。"),
    ("04", "LSM-Tree 原理", "MemStore 内存追加写、满了 Flush 成 HFile（顺序写）、多 HFile 再 Compaction 合并。BloomFilter 加速读、BlockCache 缓存 HFile 块。"),
    ("05", "API 与 CRUD", "Java API：Put/Get/Delete/Scan/Increment/CheckAndPut；Python happybase；Scan 务必 setCaching 避免逐条 RPC；BufferedMutator 高频写。"),
    ("06", "Region 管理与调优", "Split 阈值 10GB、Compaction 选 ExploringCompactionPolicy（默认）、WAL 用 AsyncFSWAL、RS 堆 BlockCache+MemStore 各 40%。必禁用 swap。"),
    ("07", "部署与集群规划", "HMaster（2 台独立 HA）+ RegionServer（跟 HDFS DataNode 混布）+ ZooKeeper（3/5 台独立）。RS 堆 16–64GB，G1GC。Short-Circuit Read 必开。"),
    ("08", "运维与故障排查", "盯 MemStore 大小、BlockCache 命中率（>90% 正常）、Compaction Queue、GC Pause（<1s）。排障动线：客户端 → RS → HDFS → ZK → HMaster。"),
    ("09", "HBase 与周边", "Phoenix（SQL+二级索引）、OpenTSDB（时序）、Hive on HBase（弱）、Spark 读写、ES 做搜索。竞品：Cassandra（无主多 DC）、RocksDB（嵌入式）。"),
    ("10", "生态对比与 FAQ", "HBase（随机读写）vs Hive（离线批）vs ClickHouse（聚合 OLAP）vs TiDB（事务）。HBase on K8s 不成熟，2.6 仍无官方 Operator。高频面试题整理。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 HBase 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（架构）、03（RowKey 热点）、04（LSM 动画）、09（组件对比）。")
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
    print("HBase · 终端摘要版\n")
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
        print("  python3 demos/main.py 03        # 打开并定位到第 3 章（RowKey 热点）")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 03  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
