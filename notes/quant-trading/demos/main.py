#!/usr/bin/env python3
"""量化交易演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "量化用系统化规则替代临场判断，追求可验证、可复制、可规模化。完整链路：数据 → 因子 → 信号 → 组合 → 执行 → 风控 → 归因。策略谱系包括趋势、均值回归、多因子、统计套利、CTA、事件驱动、做市等，各自的容量与换手完全不同。"),
    ("02", "市场微结构与交易规则", "订单簿、限价/市价单、价格优先时间优先。A 股 T+1、涨跌停、100 股整手、卖出印花税、集合竞价，直接决定回测里的成交假设。显性成本之外，滑点与冲击成本才是隐性大头。"),
    ("03", "数据与因子研究", "行情、财报、另类数据；前复权/后复权、Point-in-Time、幸存者偏差是三大数据陷阱。因子研究流程：去极值 → 标准化 → 中性化；用 IC/RankIC、分组收益、衰减与拥挤度评价。"),
    ("04", "策略体系与信号构建", "趋势跟踪低胜率高盈亏比，均值回归高胜率但尾部风险大；多因子选股靠横截面排序，统计套利靠价差回归。信号要经过流动性过滤、仓位映射与持有期设计，参数要看平台而非单点最优。"),
    ("05", "回测系统与绩效评估", "回测是筛选器，不是证明。七大偏差：前视、幸存者、数据窥探、过拟合、忽略成本、理想成交、时间对齐。绩效看年化、波动、夏普、最大回撤、Calmar、换手与容量，并做成本敏感性。"),
    ("06", "组合优化与风险管理", "Markowitz 均值方差对输入误差极度敏感，实盘常用最小方差、风险平价、Black-Litterman 与因子风险模型。风险度量包括 VaR/CVaR、压力测试；仓位用凯利、波动率目标与回撤降杠杆。"),
    ("07", "交易执行与算法下单", "执行成本包括价差、冲击、择时风险与机会成本。TWAP 等分、VWAP 跟随成交量、POV 控制参与率、IS 权衡冲击与风险。订单状态机要处理部分成交、超时、撤单与幂等。"),
    ("08", "工程架构与实盘落地", "研究-回测-实盘最大的问题是口径不一致。系统分数据、研究、信号、交易、风控、监控六层；实盘要解决幂等下单、断线重连、状态恢复、对账、告警与 kill switch，并满足程序化交易报备等合规要求。"),
    ("09", "AI 与量化投研", "机器学习更适合做非线性因子合成与信息处理。时序验证要用 Purged K-Fold + Embargo；试验次数越多，最优回测夏普越虚高。LLM 适合财报摘要、事件抽取与研报问答，不适合直接预测涨跌。"),
    ("10", "工具生态与 FAQ", "数据用 numpy/pandas/polars，回测用 backtrader/vectorbt/Qlib，优化用 cvxpy/PyPortfolioOpt，交易接 vn.py/QMT/CTP。先跑通含成本的回测，再小资金实盘，最后做多策略与运维。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开「量化交易」可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（订单簿）、03（因子 IC）、05（回测成本）、09（多重检验）。")
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
    print("量化交易 · 终端摘要版\n")
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
        print("  python3 demos/main.py 05        # 打开并定位到第 5 章")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 05  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
