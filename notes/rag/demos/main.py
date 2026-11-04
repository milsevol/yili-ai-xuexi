#!/usr/bin/env python3
"""RAG 检索增强生成：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "RAG 解决「模型不知道私有知识」与「会编」两个问题。知识/时效/溯源类需求用 RAG；风格与格式需求用微调；精确计算与严格事务不要交给模型。"),
    ("02", "RAG 核心流程", "索引期：解析 → 切块 → 向量化 → 入库；查询期：检索 → 重排 → 拼装 → 生成。绝大多数效果问题出在索引期的切块与向量质量，而不是模型。"),
    ("03", "文档解析与 Chunking", "切块是 RAG 最易被低估的环节：块太大噪声多、太小丢上下文。经验 300~500 字 + 10%~20% 重叠；表格与条款按结构切，切忌按字数硬切。"),
    ("04", "检索优化与多路召回", "向量懂语义、BM25 认关键词，RRF 用 1/(k+rank) 融合两路排名（k 常取 60），无需调权重。查询改写与 HyDE 可显著提升长尾问题的召回。"),
    ("05", "重排序 Rerank", "Bi-Encoder 分开编码精度有限；Cross-Encoder 把 query+doc 拼接后全交互打分，精度高但只能算几十对。典型链路：召回 Top-20 → Rerank → Top-5。"),
    ("06", "RAG 评估 RAGAS", "四个指标分工：Context Recall/Precision 评检索，Faithfulness/Answer Relevancy 评生成。优化顺序先保召回，再提精排，最后约束 Prompt。"),
    ("07", "高级 RAG 架构", "多路召回、查询规划、迭代检索（Self-RAG）、分层检索、GraphRAG、Agentic RAG。用 badcase 驱动升级，GraphRAG 建图成本可达基础 RAG 的数十倍。"),
    ("08", "企业知识库实战与 FAQ", "最小可用 RAG 只需百来行代码，难在四件工程事：权限过滤下推到检索、引用可溯源、无答案兜底、全链路日志与反馈闭环。附 12 个面试问答。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 RAG 检索增强生成 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    推荐顺序：02（流程）→ 03（切块）→ 05（Rerank）→ 06（评估）。")
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
    print("RAG 检索增强生成 · 终端摘要版\n")
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
        print("  python3 demos/main.py 03        # 打开并定位到第 3 章")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 03  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
