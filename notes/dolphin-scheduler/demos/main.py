#!/usr/bin/env python3
"""海豚调度主题演示入口：菜单选择或 python3 demos/main.py 04 直达。"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHAPTERS = [
    ("01", "概述与定位", "chapters.01_overview"),
    ("02", "架构与组件", "chapters.02_architecture"),
    ("03", "核心概念", "chapters.03_concepts"),
    ("04", "DAG与调度", "chapters.04_dag_schedule"),
    ("05", "任务类型与资源", "chapters.05_tasks_resources"),
]


def run_chapter(code: str) -> None:
    code = code.strip().zfill(2) if code.isdigit() else code.strip()
    for num, title, module_name in CHAPTERS:
        if code in (num, num.lstrip("0") or "0"):
            print(f"\n######## 第 {num} 章 · {title} ########\n")
            mod = importlib.import_module(module_name)
            mod.run()
            return
    print(f"未找到章节: {code}，可选: {[c[0] for c in CHAPTERS]}")
    sys.exit(1)


def menu() -> None:
    print("海豚调度（DolphinScheduler）演示\n")
    for num, title, _ in CHAPTERS:
        print(f"  {num}  {title}")
    print("  q   退出")
    choice = input("\n选择章节编号: ").strip().lower()
    if choice in ("q", "quit", "exit"):
        return
    run_chapter(choice)


def main() -> None:
    if len(sys.argv) > 1:
        run_chapter(sys.argv[1])
    else:
        menu()


if __name__ == "__main__":
    main()
