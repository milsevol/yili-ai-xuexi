#!/usr/bin/env python3
"""向量数据库与 Embedding 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "向量数据库解决「语义检索」：文本经 Embedding 编码成高维向量，按距离找最相似 Top-K。与 ES（关键词 BM25）、关系库（精确匹配）互补。核心场景：语义搜索、RAG、推荐去重。主流产品 FAISS（库）/ Milvus（分布式）/ Qdrant（轻量）/ Chroma（原型）。"),
    ("02", "Embedding 原理与模型", "从 Word2Vec（词级静态）到 BERT（上下文相关）到现代对比学习 Embedding。中文自部署首选 bge-m3 / bge-large-zh，云端用 text-embedding-3。注意：裸 BERT 不适合直接检索；归一化后点积 = 余弦；1 亿条 1024 维 float32 ≈ 400GB，量化是刚需。"),
    ("03", "ANN 算法原理", "暴力检索 O(N·D) 百万级就要几百毫秒。HNSW 分层图导航 O(log N)、召回 95~99%、内存高（在线首选）；IVF 聚类分桶只扫 nprobe 个桶；PQ 分段量化压缩 32 倍需配重排。efSearch/nprobe 是召回-延迟旋钮，用 Recall@K 评估。"),
    ("04", "FAISS 与 Milvus 实战", "FAISS 索引选择：Flat（<10万拿真值）→ HNSWFlat（千万级首选）→ IVFPQ（亿级省内存）。余弦场景务必 normalize_L2 后用 IP。Milvus 存算分离分布式架构，collection + HNSW 索引 + 标量过滤；Qdrant 轻量、Chroma 原型首选。"),
    ("05", "混合检索与调优", "向量懂语义、BM25 精关键词，RRF 排名融合（k=60）两路互补。标量过滤主流用 In-search（图遍历中过滤）。HNSW 调优顺序：先调 efSearch，再回调 M/efConstruction。分片扛数据量、副本扛 QPS，内存估算公式 N×(D×4+M×2×8)。"),
    ("06", "语义搜索实战与 FAQ", "生产管线五步：切块（300~500字+重叠）→ Embedding（bge-m3）→ 入库 → 混合检索 → Rerank（bge-reranker，质量跃升关键）。常见坑：维度不一致、忘归一化、IVF 增量退化、超长截断、距离方向搞反。附 10 个高频面试问答。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开向量数据库可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（Embedding）、03（ANN 算法）、05（混合检索调优）。")
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
    print("向量数据库与 Embedding · 终端摘要版\n")
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
