"""事件驱动日频回测引擎，提供接近聚宽风格的策略 API。

一个交易日内的处理顺序：
1. 集合竞价：以当日开盘价撮合上一交易日收盘后产生的委托（含滑点、手续费、T+1 约束）；
2. 收盘：按当日收盘价对持仓盯市，记录净值；
3. 调用 handle_data，策略基于当日收盘数据产生信号，委托排队到下一交易日开盘。
这样可以避免"用当日收盘价信号、按当日收盘价成交"的前视偏差。
"""

from __future__ import annotations

import builtins
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace

from .data import BENCHMARK_BY_CODE, MarketData
from .metrics import compute_metrics

VISIBLE_FIELDS = ("open", "high", "low", "close", "volume")


class StrategyError(Exception):
    def __init__(self, message: str, logs: list[dict] | None = None) -> None:
        super().__init__(message)
        self.logs = logs or []


@dataclass
class Position:
    security: str
    amount: int = 0
    available: int = 0
    avg_cost: float = 0.0
    price: float = 0.0

    @property
    def value(self) -> float:
        return self.amount * self.price


@dataclass
class Runtime:
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty: float = 0.0005
    slippage: float = 0.0005
    benchmark: str = "000300.XSHG"


class Portfolio:
    def __init__(self, engine: "BacktestEngine") -> None:
        self._engine = engine

    @property
    def total_value(self) -> float:
        return self._engine.total_value()

    @property
    def available_cash(self) -> float:
        return round(self._engine.cash, 2)

    @property
    def positions(self) -> dict[str, Position]:
        return self._engine.positions

    @property
    def starting_cash(self) -> float:
        return self._engine.initial_cash

    @property
    def returns(self) -> float:
        return self._engine.total_value() / self._engine.initial_cash - 1.0


class Context:
    def __init__(self, engine: "BacktestEngine") -> None:
        self._engine = engine
        self.portfolio = Portfolio(engine)
        self.current_dt = datetime(engine.start_date.year, engine.start_date.month, engine.start_date.day, 15, 0)
        self.previous_date = self.current_dt
        self.run_params = {
            "start_date": engine.feed.calendar[engine.start_idx],
            "end_date": engine.feed.calendar[engine.end_idx],
            "frequency": "day",
            "initial_cash": engine.initial_cash,
        }


class CurrentData:
    __slots__ = ("security", "name", "open", "high", "low", "close", "volume", "last_price", "paused", "limit_up", "limit_down")

    def __init__(self, security: str, bar: dict, prev_close: float, name: str) -> None:
        self.security = security
        self.name = name
        self.open = bar["open"]
        self.high = bar["high"]
        self.low = bar["low"]
        self.close = bar["close"]
        self.volume = bar["volume"]
        self.last_price = bar["close"]
        self.paused = bar["volume"] <= 0
        self.limit_up = round(prev_close * 1.1, 2)
        self.limit_down = round(prev_close * 0.9, 2)

    def __repr__(self) -> str:
        return f"<CurrentData {self.security} close={self.close}>"


class DataProxy:
    def __init__(self, engine: "BacktestEngine") -> None:
        self._engine = engine

    def current(self, security: str, field: str = "close"):
        bar = self._engine.bar(security, self._engine.idx)
        if field not in VISIBLE_FIELDS:
            raise StrategyError(f"data.current 不支持字段: {field}（可用: {', '.join(VISIBLE_FIELDS)}）", self._engine.logs)
        return bar[field]

    def __getitem__(self, security: str) -> CurrentData:
        return self._engine.current_data(security)

    def __contains__(self, security: str) -> bool:
        return security in self._engine.feed.stocks


@dataclass
class _OrderSpec:
    kind: str
    value: float


class BacktestEngine:
    def __init__(self, feed: MarketData, start_idx: int, end_idx: int, cash: float) -> None:
        self.feed = feed
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.start_date = date.fromisoformat(feed.calendar[start_idx])
        self.idx = start_idx
        self.initial_cash = float(cash)
        self.cash = float(cash)
        self.runtime = Runtime()
        self.positions: dict[str, Position] = {}
        self.pending: dict[str, _OrderSpec] = {}
        self.trades: list[dict] = []
        self.rejected: list[dict] = []
        self.logs: list[dict] = []
        self.nav: list[float] = []
        self.benchmark_nav: list[float] = []
        self.dates: list[str] = []
        self.traded_value = 0.0
        self.g = SimpleNamespace()

    # ---------- 基础访问 ----------

    def bar(self, security: str, idx: int) -> dict:
        bars = self.feed.stocks.get(security)
        if bars is None:
            raise StrategyError(f"未知标的: {security}（可用标的见左侧标的池）", self.logs)
        return bars[idx]

    def bench_bar(self, security: str, idx: int) -> dict:
        bars = self.feed.benchmarks.get(security)
        if bars is None:
            raise StrategyError(f"未知基准: {security}", self.logs)
        return bars[idx]

    def current_data(self, security: str) -> CurrentData:
        bars = self.feed.stocks.get(security)
        if bars is None:
            raise StrategyError(f"未知标的: {security}", self.logs)
        prev = bars[self.idx - 1]["close"] if self.idx > 0 else bars[self.idx]["open"]
        return CurrentData(security, bars[self.idx], prev, self.feed.security_name(security))

    def total_value(self, idx: int | None = None) -> float:
        i = self.idx if idx is None else idx
        total = self.cash
        for code, pos in self.positions.items():
            total += pos.amount * self.feed.stocks[code][i]["close"]
        return total

    def log(self, message: str, level: str = "info") -> None:
        if len(self.logs) >= 1200:
            return
        self.logs.append({"date": self.feed.calendar[self.idx], "level": level, "message": str(message)})

    # ---------- 委托 ----------

    def queue(self, security: str, kind: str, value: float) -> None:
        if security not in self.feed.stocks:
            raise StrategyError(f"无法下单：未知标的 {security}", self.logs)
        if self.idx >= self.end_idx:
            return
        self.pending[security] = _OrderSpec(kind, float(value))

    def _desired_delta(self, security: str, spec: _OrderSpec, price: float, open_total: float) -> int:
        pos = self.positions.get(security)
        held = pos.amount if pos else 0
        if spec.kind == "delta":
            return int(spec.value)
        if spec.kind == "value":
            return int(spec.value / price) if price else 0
        if spec.kind == "target":
            return int(spec.value) - held
        if spec.kind == "target_value":
            return int(spec.value / price) - held if price else 0
        if spec.kind == "target_percent":
            target_value = open_total * spec.value
            return int(target_value / price) - held if price else 0
        return 0

    def _record_reject(self, security: str, side: str, amount: int, reason: str) -> None:
        self.rejected.append(
            {
                "date": self.feed.calendar[self.idx],
                "security": security,
                "name": self.feed.security_name(security),
                "side": side,
                "amount": amount,
                "reason": reason,
            }
        )
        self.log(f"委托未成交 {security} {side} {amount} 股：{reason}", "warn")

    def _execute_pending(self) -> None:
        if not self.pending:
            return
        i = self.idx
        open_total = self.cash
        for code, pos in self.positions.items():
            open_total += pos.amount * self.feed.stocks[code][i]["open"]

        for security, spec in list(self.pending.items()):
            pos = self.positions.get(security)
            held = pos.amount if pos else 0
            bar = self.feed.stocks[security][i]
            open_price = bar["open"]
            if bar["volume"] <= 0 or open_price <= 0:
                self._record_reject(security, "买入" if self._desired_delta(security, spec, open_price, open_total) > 0 else "卖出", 0, "停牌")
                continue

            delta = self._desired_delta(security, spec, open_price, open_total)
            if delta == 0:
                continue
            side = "买入" if delta > 0 else "卖出"

            if delta > 0:
                price = round(open_price * (1.0 + self.runtime.slippage), 2)
                amount = (delta // 100) * 100
                if amount <= 0:
                    continue
                affordable = 0
                lots = amount // 100
                while lots > 0:
                    candidate = lots * 100
                    cost = candidate * price
                    fee = max(cost * self.runtime.commission_rate, self.runtime.min_commission)
                    if cost + fee <= self.cash:
                        affordable = candidate
                        break
                    lots -= 1
                if affordable <= 0:
                    self._record_reject(security, side, amount, "可用资金不足")
                    continue
                if affordable < amount:
                    self.log(f"资金不足，买入 {security} 数量由 {amount} 调整为 {affordable} 股", "warn")
                amount = affordable
                value = amount * price
                fee = max(value * self.runtime.commission_rate, self.runtime.min_commission)
                self.cash -= value + fee
                if pos is None:
                    pos = Position(security=security)
                    self.positions[security] = pos
                    old_cost = 0.0
                else:
                    old_cost = pos.avg_cost * pos.amount
                pos.amount += amount
                pos.avg_cost = (old_cost + value + fee) / pos.amount if pos.amount else 0.0
                pos.price = bar["close"]
                self._record_trade(security, side, amount, price, value, fee, 0.0)
            else:
                price = round(open_price * (1.0 - self.runtime.slippage), 2)
                if pos is None or pos.available <= 0:
                    self._record_reject(security, side, abs(delta), "无可卖持仓（T+1 当日买入不可卖）")
                    continue
                amount = min(abs(delta), pos.available)
                if amount < pos.available:
                    amount = (amount // 100) * 100
                if amount <= 0:
                    continue
                if abs(delta) > pos.available:
                    self.log(f"T+1 限制，卖出 {security} 数量由 {abs(delta)} 调整为 {amount} 股", "warn")
                value = amount * price
                fee = max(value * self.runtime.commission_rate, self.runtime.min_commission)
                stamp = value * self.runtime.stamp_duty
                self.cash += value - fee - stamp
                pos.amount -= amount
                pos.available -= amount
                pos.price = bar["close"]
                if pos.amount <= 0:
                    self.positions.pop(security, None)
                self._record_trade(security, side, amount, price, value, fee, stamp)

        self.pending.clear()

    def _record_trade(self, security: str, side: str, amount: int, price: float, value: float, fee: float, stamp: float) -> None:
        self.traded_value += value
        self.trades.append(
            {
                "date": self.feed.calendar[self.idx],
                "security": security,
                "name": self.feed.security_name(security),
                "side": side,
                "amount": amount,
                "price": round(price, 3),
                "value": round(value, 2),
                "fee": round(fee + stamp, 2),
                "cash": round(self.cash, 2),
            }
        )

    # ---------- 主循环 ----------

    def run(self) -> dict:
        started = time.perf_counter()
        self.log(
            f"回测开始：{self.feed.calendar[self.start_idx]} ~ {self.feed.calendar[self.end_idx]}，"
            f"初始资金 {self.initial_cash:,.0f} 元"
        )
        bench_first = None
        data_proxy = DataProxy(self)

        for i in range(self.start_idx, self.end_idx + 1):
            self.idx = i
            day = self.feed.calendar[i]
            previous_dt = self.context.current_dt
            self.context.current_dt = datetime.fromisoformat(day).replace(hour=15)
            self.context.previous_date = previous_dt

            if bench_first is None:
                bench_first = self.bench_bar(self.runtime.benchmark, i)["close"]

            for pos in self.positions.values():
                pos.available = pos.amount

            self._execute_pending()

            for code, pos in self.positions.items():
                pos.price = self.feed.stocks[code][i]["close"]

            total = self.total_value()
            self.nav.append(total / self.initial_cash)
            self.dates.append(day)
            bench_close = self.bench_bar(self.runtime.benchmark, i)["close"]
            self.benchmark_nav.append(bench_close / bench_first)

            try:
                self.handle_data(self.context, data_proxy)
            except StrategyError:
                raise
            except Exception as exc:  # noqa: BLE001 - 把策略异常带日期抛给前端
                raise StrategyError(f"{day} 策略执行出错：{exc}", self.logs) from exc

        if self.pending:
            self.log("最后一日的委托不会成交（回测已结束）", "warn")

        self.log(f"回测结束：期末资产 {self.cash + sum(p.amount * p.price for p in self.positions.values()):,.2f} 元")
        metrics = compute_metrics(
            self.dates, self.nav, self.benchmark_nav, self.initial_cash, self.traded_value
        )

        drawdown: list[float] = []
        peak = 0.0
        for value in self.nav:
            peak = max(peak, value)
            drawdown.append(value / peak - 1.0 if peak else 0.0)

        positions = []
        for code, pos in sorted(self.positions.items(), key=lambda kv: -kv[1].value):
            positions.append(
                {
                    "security": code,
                    "name": self.feed.security_name(code),
                    "amount": pos.amount,
                    "available": pos.available,
                    "avg_cost": round(pos.avg_cost, 3),
                    "price": round(pos.price, 3),
                    "value": round(pos.value, 2),
                    "pnl": round((pos.price - pos.avg_cost) * pos.amount, 2),
                }
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "meta": {
                "start": self.feed.calendar[self.start_idx],
                "end": self.feed.calendar[self.end_idx],
                "trading_days": len(self.dates),
                "initial_cash": self.initial_cash,
                "benchmark": self.runtime.benchmark,
                "benchmark_name": self.feed.security_name(self.runtime.benchmark),
                "elapsed_ms": elapsed_ms,
                "trade_count": len(self.trades),
                "rejected_count": len(self.rejected),
            },
            "metrics": metrics,
            "equity": {
                "dates": self.dates,
                "strategy": [round(v, 6) for v in self.nav],
                "benchmark": [round(v, 6) for v in self.benchmark_nav],
                "drawdown": [round(v, 6) for v in drawdown],
            },
            "monthly": _monthly(self.dates, self.nav),
            "trades": self.trades,
            "positions": positions,
            "logs": self.logs,
            "rejected": self.rejected,
        }

    # ---------- 策略 API ----------

    def handle_data(self, context: Context, data: DataProxy) -> None:
        self._handle_data(context, data)

    def attach_strategy(self, namespace: dict) -> None:
        if "initialize" not in namespace or not callable(namespace["initialize"]):
            raise StrategyError("策略缺少 initialize(context) 函数", self.logs)
        if "handle_data" not in namespace or not callable(namespace["handle_data"]):
            raise StrategyError("策略缺少 handle_data(context, data) 函数", self.logs)
        self._handle_data = namespace["handle_data"]
        self.context = Context(self)
        try:
            namespace["initialize"](self.context)
        except StrategyError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StrategyError(f"initialize 执行出错：{exc}", self.logs) from exc

    def build_namespace(self) -> dict:
        engine = self

        def set_benchmark(security: str) -> None:
            if security not in BENCHMARK_BY_CODE:
                raise StrategyError(f"未知基准 {security}，可用：{', '.join(BENCHMARK_BY_CODE)}", engine.logs)
            engine.runtime.benchmark = security

        def set_commission(rate: float = 0.0003, min_commission: float = 5.0, stamp_duty: float = 0.0005) -> None:
            engine.runtime.commission_rate = max(0.0, float(rate))
            engine.runtime.min_commission = max(0.0, float(min_commission))
            engine.runtime.stamp_duty = max(0.0, float(stamp_duty))

        def set_slippage(slippage: float = 0.0005) -> None:
            engine.runtime.slippage = max(0.0, float(slippage))

        def order(security: str, amount: int) -> None:
            engine.queue(security, "delta", amount)

        def order_value(security: str, value: float) -> None:
            engine.queue(security, "value", value)

        def order_target(security: str, amount: int) -> None:
            engine.queue(security, "target", amount)

        def order_target_value(security: str, value: float) -> None:
            engine.queue(security, "target_value", value)

        def order_target_percent(security: str, percent: float) -> None:
            engine.queue(security, "target_percent", percent)

        def get_position(security: str) -> Position | None:
            return engine.positions.get(security)

        def attribute_history(security: str, count: int = 20, unit: str = "1d", fields=None, skip_paused: bool = True) -> dict:
            if unit not in ("1d", "daily"):
                raise StrategyError(f"目前仅支持日线，收到 unit={unit}", engine.logs)
            bars = engine.feed.stocks.get(security)
            if bars is None:
                raise StrategyError(f"未知标的: {security}", engine.logs)
            count = max(1, int(count))
            start = max(0, engine.idx - count + 1)
            cols = list(fields or ("open", "close", "high", "low", "volume"))
            for col in cols:
                if col not in VISIBLE_FIELDS:
                    raise StrategyError(f"不支持的字段: {col}", engine.logs)
            return {col: [bars[j][col] for j in range(start, engine.idx + 1)] for col in cols}

        def history(security: str, count: int = 20, field: str = "close", unit: str = "1d") -> list:
            return attribute_history(security, count, unit, [field])[field]

        def get_current_data() -> dict[str, CurrentData]:
            return {code: engine.current_data(code) for code in engine.feed.stocks}

        def get_date() -> date:
            return engine.context.current_dt.date()

        class _Log:
            def info(self, message) -> None:
                engine.log(message, "info")

            def warn(self, message) -> None:
                engine.log(message, "warn")

            warning = warn

            def error(self, message) -> None:
                engine.log(message, "error")

        return {
            "__builtins__": builtins,
            "__name__": "quantlab_strategy",
            "g": self.g,
            "log": _Log(),
            "order": order,
            "order_value": order_value,
            "order_target": order_target,
            "order_target_value": order_target_value,
            "order_target_percent": order_target_percent,
            "get_position": get_position,
            "attribute_history": attribute_history,
            "history": history,
            "get_current_data": get_current_data,
            "get_date": get_date,
            "set_benchmark": set_benchmark,
            "set_commission": set_commission,
            "set_slippage": set_slippage,
        }

    def _handle_data(self, context: Context, data: DataProxy) -> None:  # 由 attach_strategy 覆盖
        raise StrategyError("策略未加载", self.logs)


def _monthly(dates: list[str], nav: list[float]) -> list[dict]:
    if not dates:
        return []
    last_of_month: dict[tuple[int, int], float] = {}
    for day, value in zip(dates, nav):
        key = (int(day[:4]), int(day[5:7]))
        last_of_month[key] = value
    out: list[dict] = []
    prev = nav[0]
    for key in sorted(last_of_month):
        close = last_of_month[key]
        out.append({"year": key[0], "month": key[1], "ret": close / prev - 1.0 if prev else 0.0})
        prev = close
    return out


def run_backtest(
    code: str,
    feed: MarketData,
    start: str | None = None,
    end: str | None = None,
    cash: float = 1_000_000.0,
    benchmark: str = "000300.XSHG",
) -> dict:
    if not code or not code.strip():
        raise StrategyError("策略代码为空")
    start_idx, end_idx = feed.range_to_index(start, end)
    if cash <= 0:
        raise StrategyError("初始资金必须大于 0")
    if benchmark not in BENCHMARK_BY_CODE:
        raise StrategyError(f"未知基准 {benchmark}")

    engine = BacktestEngine(feed, start_idx, end_idx, cash)
    engine.runtime.benchmark = benchmark
    namespace = engine.build_namespace()
    try:
        compiled = compile(code, "<strategy>", "exec")
        exec(compiled, namespace)  # noqa: S102 - 本地可信策略代码
    except SyntaxError as exc:
        raise StrategyError(f"语法错误：第 {exc.lineno} 行 {exc.msg}", engine.logs) from exc
    except StrategyError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise StrategyError(f"策略加载失败：{exc}", engine.logs) from exc

    engine.attach_strategy(namespace)
    try:
        return engine.run()
    except StrategyError:
        raise
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        raise StrategyError(f"回测执行失败：{exc}", engine.logs) from exc
