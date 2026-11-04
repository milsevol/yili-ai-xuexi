#!/usr/bin/env python3
"""Agent 智能体：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "Agent = LLM + 工具 + 记忆 + 循环。演进四步：Prompt（会说）→ RAG（有知识）→ Agent（会动手）→ 多 Agent（会协作）。能确定性流程化的任务不要交给模型自由发挥。"),
    ("02", "Agent 核心架构", "三要素：规划（拆解与重规划）、记忆（短期对话 + 长期向量/图谱）、工具（检索/API/计算）。循环必须设最大步数、超时与重复动作检测。"),
    ("03", "ReAct 推理范式", "Thought → Action → Observation 交替进行，直到得出 Final。最常见失败是死循环与幻觉工具；必须限制步数并校验工具参数。"),
    ("04", "Function Calling 与 MCP", "工具设计三原则：原子性、幂等性、错误可读。写入类工具必须二次确认 + 权限校验；MCP 把工具标准化成可复用服务，权限与审计统一。"),
    ("05", "LangGraph 状态机", "节点=动作、边=条件、State 在节点间传递。图编排可中断、可重放、可人工介入；checkpointer 让失败能从断点续跑。"),
    ("06", "多 Agent 协作", "主管-工人、辩论、流水线三种模式各有代价。判断标准：任务能否切成独立子任务；串行依赖强时单 Agent + 好工具更稳更省。"),
    ("07", "记忆与上下文管理", "上下文是有限预算：system、工具定义、历史、检索片段、工具结果互相争抢。历史要摘要、工具结果要压缩、检索片段按相关性截断。"),
    ("08", "投研助手实战与 FAQ", "金融投研 Agent：行情/财报/新闻/计算器四类工具 + 研报 RAG + LangGraph 编排 + 输出风控。红线：不给投资建议、数字可溯源、时效带时间戳。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Agent 智能体 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    推荐顺序：02（三要素）→ 03（ReAct）→ 05（LangGraph）→ 07（上下文预算）。")
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
    print("Agent 智能体 · 终端摘要版\n")
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
