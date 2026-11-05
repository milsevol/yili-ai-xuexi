"""内置模拟行情数据。

完全离线、确定性生成：同一标的每次运行得到同一条价格路径，便于复现回测。
数据是"像 A 股"的模拟日线（含涨跌停约束、成交量），不对应任何真实证券。
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from functools import lru_cache

START_DATE = date(2018, 1, 2)

# price: 起始价格；drift: 年化漂移；vol: 年化波动；cap: 相对市值权重
STOCKS = [
    {"code": "000001.XSHE", "name": "平安银行", "sector": "银行", "price": 9.2, "drift": 0.02, "vol": 0.28, "cap": 180.0},
    {"code": "600036.XSHG", "name": "招商银行", "sector": "银行", "price": 28.0, "drift": 0.06, "vol": 0.26, "cap": 220.0},
    {"code": "600519.XSHG", "name": "贵州茅台", "sector": "食品饮料", "price": 590.0, "drift": 0.10, "vol": 0.28, "cap": 300.0},
    {"code": "000858.XSHE", "name": "五粮液", "sector": "食品饮料", "price": 62.0, "drift": 0.08, "vol": 0.33, "cap": 150.0},
    {"code": "601318.XSHG", "name": "中国平安", "sector": "非银金融", "price": 48.0, "drift": 0.02, "vol": 0.30, "cap": 200.0},
    {"code": "300750.XSHE", "name": "宁德时代", "sector": "电力设备", "price": 72.0, "drift": 0.16, "vol": 0.46, "cap": 160.0},
    {"code": "002594.XSHE", "name": "比亚迪", "sector": "汽车", "price": 46.0, "drift": 0.13, "vol": 0.42, "cap": 140.0},
    {"code": "000333.XSHE", "name": "美的集团", "sector": "家用电器", "price": 38.0, "drift": 0.07, "vol": 0.28, "cap": 120.0},
    {"code": "600276.XSHG", "name": "恒瑞医药", "sector": "医药生物", "price": 43.0, "drift": 0.04, "vol": 0.32, "cap": 110.0},
    {"code": "601899.XSHG", "name": "紫金矿业", "sector": "有色金属", "price": 3.8, "drift": 0.11, "vol": 0.36, "cap": 100.0},
    {"code": "600900.XSHG", "name": "长江电力", "sector": "公用事业", "price": 15.5, "drift": 0.05, "vol": 0.18, "cap": 130.0},
    {"code": "002415.XSHE", "name": "海康威视", "sector": "电子", "price": 26.0, "drift": 0.03, "vol": 0.33, "cap": 90.0},
]

BENCHMARK_DEFS = [
    {
        "code": "000300.XSHG",
        "name": "沪深300",
        "base": 3500.0,
        "members": [
            "600519.XSHG", "600036.XSHG", "601318.XSHG", "000333.XSHE",
            "000858.XSHE", "600276.XSHG", "600900.XSHG", "000001.XSHE",
        ],
    },
    {
        "code": "000905.XSHG",
        "name": "中证500",
        "base": 5600.0,
        "members": [
            "002415.XSHE", "601899.XSHG", "000858.XSHE", "002594.XSHE",
            "000001.XSHE", "600276.XSHG", "000333.XSHE",
        ],
    },
    {
        "code": "399006.XSHE",
        "name": "创业板指",
        "base": 1800.0,
        "members": ["300750.XSHE", "002594.XSHE", "002415.XSHE", "000333.XSHE"],
    },
]

STOCK_BY_CODE = {s["code"]: s for s in STOCKS}
BENCHMARK_BY_CODE = {b["code"]: b for b in BENCHMARK_DEFS}


def _trading_days(start: date, end: date) -> list[str]:
    """按工作日近似交易日（内置模拟数据不剔除法定节假日）。"""
    days: list[str] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def _round_bar(open_p: float, high: float, low: float, close: float, prev_close: float) -> tuple[float, float, float, float]:
    limit_up = round(prev_close * 1.1, 2)
    limit_down = round(prev_close * 0.9, 2)
    close = min(max(close, limit_down), limit_up)
    open_p = min(max(open_p, limit_down), limit_up)
    high = min(max(max(high, open_p, close), limit_down), limit_up)
    low = min(max(min(low, open_p, close), limit_down), limit_up)
    return round(open_p, 2), round(high, 2), round(low, 2), round(close, 2)


def _gen_stock_bars(spec: dict, days: list[str]) -> list[dict]:
    rng = random.Random(f"quantlab|{spec['code']}")
    daily_vol = spec["vol"] / math.sqrt(252)
    prev_close = spec["price"]
    regime = 0.0
    bars: list[dict] = []

    for idx, day in enumerate(days):
        regime = regime * 0.90 + rng.gauss(0.0, 0.00055)
        ret = spec["drift"] / 252 + regime + rng.gauss(0.0, daily_vol)
        if rng.random() < 0.002:
            ret += rng.choice((-1.0, 1.0)) * rng.uniform(0.02, 0.04)
        ret = max(-0.095, min(0.095, ret))

        gap = max(-0.03, min(0.03, rng.gauss(0.0, daily_vol * 0.35)))
        open_p = prev_close * (1.0 + gap)
        close_p = prev_close * (1.0 + ret)
        high = max(open_p, close_p) * (1.0 + abs(rng.gauss(0.0, 0.006)))
        low = min(open_p, close_p) * (1.0 - abs(rng.gauss(0.0, 0.006)))

        volume = int(18_000_000 * (0.55 + 1.9 * abs(ret) / max(daily_vol, 1e-9) * 0.25 + rng.random() * 0.7))
        open_p, high, low, close_p = _round_bar(open_p, high, low, close_p, prev_close)
        bars.append(
            {
                "date": day,
                "open": open_p,
                "high": high,
                "low": low,
                "close": close_p,
                "volume": max(volume, 100_000),
            }
        )
        prev_close = close_p
    return bars


def _gen_index_bars(defn: dict, stock_bars: dict[str, list[dict]], days: list[str]) -> list[dict]:
    members = [code for code in defn["members"] if code in stock_bars]
    weights = {code: STOCK_BY_CODE[code]["cap"] for code in members}
    total_weight = sum(weights.values()) or 1.0
    rng = random.Random(f"quantlab|index|{defn['code']}")
    close = defn["base"]
    bars: list[dict] = []

    for idx, day in enumerate(days):
        ret = 0.0
        for code in members:
            bars_c = stock_bars[code]
            prev = bars_c[idx - 1]["close"] if idx > 0 else bars_c[idx]["open"]
            ret += weights[code] / total_weight * (bars_c[idx]["close"] / prev - 1.0)
        ret = max(-0.095, min(0.095, ret + rng.gauss(0.0, 0.0012)))
        prev_close = close
        close = max(1.0, prev_close * (1.0 + ret))
        gap = rng.gauss(0.0, 0.0012)
        open_p = prev_close * (1.0 + gap)
        high = max(open_p, close) * (1.0 + abs(rng.gauss(0.0, 0.0025)))
        low = min(open_p, close) * (1.0 - abs(rng.gauss(0.0, 0.0025)))
        open_p, high, low, close = _round_bar(open_p, high, low, close, prev_close)
        bars.append(
            {
                "date": day,
                "open": open_p,
                "high": high,
                "low": low,
                "close": close,
                "volume": 0,
            }
        )
    return bars


class MarketData:
    def __init__(self) -> None:
        today = date.today()
        end = today - timedelta(days=1)
        while end.weekday() >= 5:
            end -= timedelta(days=1)
        self.start_date = START_DATE.isoformat()
        self.end_date = end.isoformat()
        self.calendar = _trading_days(START_DATE, end)
        self.index_of = {day: i for i, day in enumerate(self.calendar)}

        self.stocks: dict[str, list[dict]] = {}
        for spec in STOCKS:
            self.stocks[spec["code"]] = _gen_stock_bars(spec, self.calendar)
        self.benchmarks: dict[str, list[dict]] = {}
        for defn in BENCHMARK_DEFS:
            self.benchmarks[defn["code"]] = _gen_index_bars(defn, self.stocks, self.calendar)

    def range_to_index(self, start: str | None, end: str | None) -> tuple[int, int]:
        first = self.index_of.get(start or self.start_date, 0)
        last = self.index_of.get(end or self.end_date, len(self.calendar) - 1)
        if first > last:
            raise ValueError("开始日期不能晚于结束日期")
        return first, last

    def universe(self) -> list[dict]:
        return [{"code": s["code"], "name": s["name"], "sector": s["sector"]} for s in STOCKS]

    def benchmark_list(self) -> list[dict]:
        return [{"code": b["code"], "name": b["name"]} for b in BENCHMARK_DEFS]

    def security_name(self, code: str) -> str:
        if code in STOCK_BY_CODE:
            return STOCK_BY_CODE[code]["name"]
        if code in BENCHMARK_BY_CODE:
            return BENCHMARK_BY_CODE[code]["name"]
        return code

    def default_start(self) -> str:
        # 默认回测最近三年
        cutoff = date.today() - timedelta(days=365 * 3)
        for day in self.calendar:
            if day >= cutoff.isoformat():
                return day
        return self.start_date


@lru_cache(maxsize=1)
def get_market() -> MarketData:
    return MarketData()
