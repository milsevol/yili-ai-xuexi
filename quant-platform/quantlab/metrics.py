"""回测绩效指标计算（纯标准库实现）。"""

from __future__ import annotations

import math
import statistics


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


def _daily_returns(nav: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(nav)):
        prev = nav[i - 1]
        out.append(nav[i] / prev - 1.0 if prev else 0.0)
    return out


def _max_drawdown(nav: list[float]) -> tuple[float, int | None, int | None]:
    peak = nav[0] if nav else 0.0
    peak_idx = 0
    mdd = 0.0
    mdd_start = mdd_end = None
    for i, value in enumerate(nav):
        if value > peak:
            peak = value
            peak_idx = i
        dd = value / peak - 1.0 if peak else 0.0
        if dd < mdd:
            mdd, mdd_start, mdd_end = dd, peak_idx, i
    return mdd, mdd_start, mdd_end


def compute_metrics(
    dates: list[str],
    nav: list[float],
    benchmark_nav: list[float],
    initial_cash: float,
    traded_value: float,
) -> dict:
    if len(nav) < 2:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "calmar": 0.0,
            "win_rate": 0.0,
            "turnover": 0.0,
            "alpha": 0.0,
            "beta": 0.0,
            "benchmark_return": 0.0,
            "excess_return": 0.0,
            "final_value": nav[-1] * initial_cash if nav else initial_cash,
            "trading_days": len(nav),
            "drawdown_start": None,
            "drawdown_end": None,
        }

    days = len(nav)
    years = days / 252.0
    total_return = nav[-1] / nav[0] - 1.0
    annual_return = (nav[-1] / nav[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    rets = _daily_returns(nav)
    bench_rets = _daily_returns(benchmark_nav)
    vol = statistics.pstdev(rets) * math.sqrt(252) if len(rets) > 1 else 0.0
    mean_daily = statistics.fmean(rets) if rets else 0.0
    sharpe = _safe_div(mean_daily * 252, vol)

    mdd, mdd_start, mdd_end = _max_drawdown(nav)
    calmar = _safe_div(annual_return, abs(mdd))

    win_rate = sum(1 for r in rets if r > 0) / len(rets) if rets else 0.0
    avg_value = statistics.fmean(nav[:-1]) * initial_cash if len(nav) > 1 else initial_cash
    turnover = _safe_div(traded_value, avg_value) / years if years > 0 else 0.0

    beta = 0.0
    alpha = 0.0
    if len(rets) > 2 and len(bench_rets) == len(rets):
        bench_var = statistics.pvariance(bench_rets)
        if bench_var > 0:
            mean_b = statistics.fmean(bench_rets)
            cov = sum((r - mean_daily) * (b - mean_b) for r, b in zip(rets, bench_rets)) / len(rets)
            beta = cov / bench_var
            alpha = (mean_daily - beta * mean_b) * 252

    benchmark_return = benchmark_nav[-1] / benchmark_nav[0] - 1.0

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "calmar": calmar,
        "win_rate": win_rate,
        "turnover": turnover,
        "alpha": alpha,
        "beta": beta,
        "benchmark_return": benchmark_return,
        "excess_return": total_return - benchmark_return,
        "final_value": nav[-1] * initial_cash,
        "trading_days": days,
        "drawdown_start": dates[mdd_start] if mdd_start is not None else None,
        "drawdown_end": dates[mdd_end] if mdd_end is not None else None,
    }
