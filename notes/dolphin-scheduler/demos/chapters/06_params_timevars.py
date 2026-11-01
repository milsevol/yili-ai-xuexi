"""06 参数传递与内置时间变量：$[...] 解析、参数优先级、任务间传参。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, Optional

# Java SimpleDateFormat → Python strftime（注意先 yyyy 再 MM，MM 与 mm 区分）
JAVA_TO_PY_FMT = (
    ("yyyy", "%Y"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("HH", "%H"),
    ("mm", "%M"),
    ("ss", "%S"),
)

# 尾部偏移：±N 天、±N/24 小时、±N/(24*60) 分钟
# 注意：偏移数字不允许前导零——这样 $[yyyy-MM-01] 的「01」会被当字面量而非偏移
_OFFSET_RE = re.compile(r"([+-](?:0|[1-9]\d*)(?:/24|/\(24\*60\))?)$")
_FUNC_RE = re.compile(r"add_(months|years)\((.+),([+-]?\d+)\)$")


def _java_fmt(fmt: str) -> str:
    out = fmt
    for j, p in JAVA_TO_PY_FMT:
        out = out.replace(j, p)
    return out


def _days_in_month(year: int, month: int) -> int:
    nxt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day


def _add_months(dt: datetime, n: int) -> datetime:
    month = dt.month - 1 + n
    year = dt.year + month // 12
    month = month % 12 + 1
    return dt.replace(year=year, month=month, day=min(dt.day, _days_in_month(year, month)))


def _add_years(dt: datetime, n: int) -> datetime:
    try:
        return dt.replace(year=dt.year + n)
    except ValueError:  # 2 月 29 日 → 平年 28 日
        return dt.replace(year=dt.year + n, day=28)


def eval_time_var(expr: str, schedule: datetime) -> str:
    """解析 $[...] 时间表达式（演示简化版）。

    基于「流程实例的调度时间」计算——补数时每个实例调度时间不同，这正是补数能跑对的原因。
    """
    m = re.fullmatch(r"\$\[(.+)\]", expr.strip())
    if not m:
        raise ValueError(f"非法表达式: {expr}")
    body = m.group(1)

    m_fn = _FUNC_RE.fullmatch(body)
    if m_fn:
        fn, fmt, n = m_fn.group(1), m_fn.group(2), int(m_fn.group(3))
        base = _add_months(schedule, n) if fn == "months" else _add_years(schedule, n)
        return base.strftime(_java_fmt(fmt))

    base = schedule
    m_off = _OFFSET_RE.search(body)
    if m_off:
        off = m_off.group(1)
        body = body[: -len(off)]
        if off.endswith("/24"):
            base += timedelta(hours=int(off[:-3]))
        elif off.endswith("/(24*60)"):
            base += timedelta(minutes=int(off[: -len("/(24*60)")]))
        else:
            base += timedelta(days=int(off))
    return base.strftime(_java_fmt(body))


def demo_time_vars() -> None:
    print("--- A. 内置时间变量速查（调度时间 2026-11-01 02:00:00） ---")
    schedule = datetime(2026, 11, 1, 2, 0, 0)
    exprs = [
        ("$[yyyy-MM-dd]", "当天"),
        ("$[yyyyMMdd]", "当天（紧凑格式）"),
        ("$[yyyy-MM-dd HH:mm:ss]", "精确到秒"),
        ("$[yyyy-MM-dd-1]", "前一天（T+1 日批的业务日期）"),
        ("$[yyyyMMdd-1]", "前一天紧凑格式"),
        ("$[yyyy-MM-01]", "本月 1 号"),
        ("$[add_months(yyyy-MM-dd,-1)]", "上个月同日"),
        ("$[yyyy-MM-dd HH:mm:ss-2/24]", "前 2 小时"),
        ("$[yyyy-MM-dd HH:mm:ss-1/(24*60)]", "前 1 分钟"),
    ]
    for expr, meaning in exprs:
        print(f"  {expr:38} {meaning:24} → {eval_time_var(expr, schedule)}")
    print("  易混：MM=月 mm=分；HH=24 时制 hh=12 时制。写错不报语法错，只会拿错值。\n")


def demo_backfill_dates() -> None:
    print("--- B. 补数为什么必须用内置变量 ---")
    print("  补数 2026-10 整月：系统生成 31 个实例，调度时间 10-02 ~ 11-01 的 02:00")
    rows = []
    for day in range(1, 32):
        schedule = datetime(2026, 10, 1, 2, 0) + timedelta(days=day)
        biz = eval_time_var("$[yyyy-MM-dd-1]", schedule)
        rows.append((schedule.strftime("%m-%d %H:%M"), biz))
    for sched, biz in rows[:3]:
        print(f"    实例调度时间 {sched} → $[yyyy-MM-dd-1]={biz}")
    print("    …")
    for sched, biz in rows[-1:]:
        print(f"    实例调度时间 {sched} → $[yyyy-MM-dd-1]={biz}")
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"  反例：脚本里 date -d yesterday → 31 个实例全部算成 {today} 的前一天，")
    print("        补数全跑到同一天，且互相覆盖。执行时刻 ≠ 调度时间！\n")


def demo_priority() -> None:
    print("--- C. 同名参数优先级：本地 > 上游传递 > 全局 ---")
    global_params = {"env": "prod", "owner": "dw"}
    upstream_out = {"env": "staging", "max_dt": "2026-10-31"}
    local_params = {"env": "dev", "table": "dwd_trade"}

    def resolve(name: str) -> Optional[str]:
        if name in local_params:
            return f"{local_params[name]}  (← 本地参数)"
        if name in upstream_out:
            return f"{upstream_out[name]}  (← 上游出参)"
        if name in global_params:
            return f"{global_params[name]}  (← 全局参数)"
        return None

    for key in ("env", "max_dt", "owner", "table"):
        print(f"  ${{{key}}} = {resolve(key)}")
    print("  建议：关键参数名全局唯一，别依赖覆盖行为。\n")


def demo_out_in() -> None:
    print("--- D. 任务间传参：OUT → IN ---")
    print("  任务A detect_partition（Shell）:")
    print("    脚本输出: echo '${setValue(max_dt=2026-10-31)}'")
    print("    自定义参数: max_dt 方向=OUT")
    out_params: Dict[str, str] = {"max_dt": "2026-10-31"}

    print("  任务B sync_data:")
    declared_in = ["max_dt"]
    script_b = "bash sync.sh --partition ${max_dt}"
    for key in declared_in:
        script_b = script_b.replace(f"${{{key}}}", out_params[key])
    print(f"    声明 IN: {declared_in} → 渲染后脚本: {script_b}")

    print("  反例：任务B 未声明 IN 就用 ${max_dt}")
    print("    → 渲染时拿不到值，原样保留或为空（以版本行为为准）——下游必须声明接收！")
    print("  出参只传小数据（字符串/数字），别当数据管道。\n")


def run() -> None:
    print("=== 06 参数传递与内置时间变量 ===\n")
    demo_time_vars()
    demo_backfill_dates()
    demo_priority()
    demo_out_in()
