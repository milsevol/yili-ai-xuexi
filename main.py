#!/usr/bin/env python3
"""仓库总入口：选择主题并进入该主题的演示程序。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES_ROOT = ROOT / "notes"

# 新增主题时在此登记：(编号显示名, notes/ 下的主题目录名, 一句话说明)
TOPICS = [
    ("1", "dolphin-scheduler", "海豚调度（DolphinScheduler）"),
    ("2", "spark", "Apache Spark（PySpark）"),
    ("3", "hadoop", "Apache Hadoop（HDFS / YARN / MapReduce）"),
    ("4", "llm-foundations", "Transformer 与大模型原理"),
    ("5", "prompt-engineering", "提示词工程"),
    ("6", "vector-db", "向量数据库与 Embedding"),
    ("7", "rag", "RAG 检索增强生成"),
    ("8", "agent", "Agent 智能体"),
    ("9", "flink", "Apache Flink（流处理）"),
    ("10", "hbase", "Apache HBase（列式 KV）"),
    ("11", "kafka", "Apache Kafka（消息队列）"),
    ("12", "hive", "Apache Hive（数仓 SQL）"),
    ("13", "clickhouse", "ClickHouse（列式 OLAP）"),
    ("14", "iceberg", "Apache Iceberg（湖仓表格式）"),
    ("15", "quant-trading", "量化交易（从研究到实盘）"),
]


def load_topic_main(topic_dir: Path) -> Path:
    main_py = topic_dir / "demos" / "main.py"
    if not main_py.is_file():
        raise FileNotFoundError(f"主题入口不存在: {main_py}")
    return main_py


def enter_topic(topic_dir_name: str, chapter_args: list[str]) -> None:
    topic_dir = NOTES_ROOT / topic_dir_name
    if not topic_dir.is_dir():
        # 兼容误传 notes/xxx
        alt = ROOT / topic_dir_name
        if alt.is_dir() and (alt / "demos" / "main.py").is_file():
            topic_dir = alt
        else:
            raise FileNotFoundError(f"主题目录不存在: {NOTES_ROOT / topic_dir_name}")
    main_py = load_topic_main(topic_dir)
    demos_dir = str(topic_dir / "demos")
    if demos_dir not in sys.path:
        sys.path.insert(0, demos_dir)
    sys.argv = [str(main_py), *chapter_args]
    runpy.run_path(str(main_py), run_name="__main__")


def print_menu() -> None:
    print("yili-ai-xuexi — 选择主题\n")
    if not TOPICS:
        print("（暂无主题。新增主题后在 main.py 的 TOPICS 中登记。）")
        return
    for num, dirname, desc in TOPICS:
        print(f"  {num}. {desc}  [notes/{dirname}]")
    print("  q. 退出")


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] not in {"-h", "--help"}:
        enter_topic(sys.argv[1], sys.argv[2:])
        return

    while True:
        print_menu()
        if not TOPICS:
            return
        choice = input("\n请输入编号: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            return
        matched = [t for t in TOPICS if t[0] == choice]
        if not matched:
            print("无效编号，请重试。\n")
            continue
        _, dirname, _ = matched[0]
        enter_topic(dirname, [])
        print()


if __name__ == "__main__":
    main()
