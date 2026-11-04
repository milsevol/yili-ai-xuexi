#!/usr/bin/env python3
"""Kafka 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "分布式提交日志 + 发布订阅。三大消息队列流派，Kafka vs RocketMQ vs RabbitMQ 选型。磁盘顺序写 + 零拷贝 = 百万级吞吐。"),
    ("02", "架构与核心概念", "Broker → Topic → Partition → Replica → ISR → Leader/Follower。KRaft 用 Raft 替代 ZooKeeper 做元数据，Controller 是集群大脑。"),
    ("03", "Producer 生产者", "发送流程：拦截器→序列化→分片器→累加器→Sender 线程。acks=0/1/all、重试、幂等 Producer、跨 Partition 事务。"),
    ("04", "Consumer 消费者", "拉模式，自己管 offset。Consumer Group 内每个 Partition 只能被一个 Consumer 消费。Rebalance 触发条件、提交策略、消费语义三档。"),
    ("05", "存储与分区原理", "Partition = 追加日志 + Segment 滚动 + 稀疏索引。零拷贝 sendfile 读、磁盘顺序写、分区并行度 = 吞吐。ISR/OSR、ack=all 真实含义。"),
    ("06", "高级特性", "Streams API（有状态流处理）、Connect API（Source/Sink CDC）、EOS v2 事务、动态分区分配、压缩算法选择。"),
    ("07", "部署与集群规划", "数据量→Partition→Broker 四步规划。KRaft 合并部署 vs 独立 Controller、JDK17 + G1GC、Linux 内核调优、磁盘 JBOD。"),
    ("08", "运维监控与故障排查", "UnderReplicatedPartitions、Rebalance 频繁、ConsumerLag 排障决策树。核心指标清单：Broker/Consumer/Producer 三端。"),
    ("09", "Kafka 与周边生态", "大数据链路位置：采集→缓冲→计算→落地。Flink Kafka Source vs Spark Structured Streaming、Debezium CDC。"),
    ("10", "生态对比与 FAQ", "Kafka vs Pulsar vs RocketMQ vs RabbitMQ 综合对比。KRaft 替代 ZK 时间表、Kafka on K8s、面试 12 题。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Kafka 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（架构）、03（Producer 流程）、04（Rebalance）、05（存储）、08（排障）。")
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
    print("Kafka · 终端摘要版\n")
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
