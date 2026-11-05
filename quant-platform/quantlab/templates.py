"""内置示例策略：新建策略库时作为初始内容，也可在前端随时载入。"""

from __future__ import annotations

DUAL_MA = '''# 双均线趋势策略：短均线上穿长均线买入，下穿清仓
# 回测口径：当日收盘出信号，下一交易日开盘成交

def initialize(context):
    g.security = '600519.XSHG'
    g.short = 5
    g.long = 20
    g.position = 0.95          # 目标仓位占总资产比例
    set_commission(rate=0.0003, min_commission=5, stamp_duty=0.0005)
    set_slippage(0.0005)


def handle_data(context, data):
    closes = attribute_history(g.security, g.long + 1)['close']
    if len(closes) < g.long + 1:
        return

    short_ma = sum(closes[-g.short:]) / g.short
    long_ma = sum(closes[-g.long:]) / g.long
    pos = context.portfolio.positions.get(g.security)
    holding = pos.amount if pos else 0

    if short_ma > long_ma and holding == 0:
        order_target_percent(g.security, g.position)
        log.info(f'金叉：买入 {g.security}，目标仓位 {g.position:.0%}')
    elif short_ma < long_ma and holding > 0:
        order_target(g.security, 0)
        log.info(f'死叉：清仓 {g.security}')
'''

MOMENTUM = '''# 动量轮动：每 5 个交易日按过去 20 日涨幅排序，持有最强的 2 只
# 等权分配仓位，落选标的清仓

def initialize(context):
    g.stocks = [
        '600519.XSHG', '000858.XSHE', '300750.XSHE',
        '002594.XSHE', '600036.XSHG', '601899.XSHG',
    ]
    g.lookback = 20
    g.hold_num = 2
    g.rebalance_days = 5
    g.counter = 0
    g.position = 0.95
    set_commission(rate=0.0003, min_commission=5, stamp_duty=0.0005)
    set_slippage(0.0005)


def handle_data(context, data):
    g.counter += 1
    if g.counter % g.rebalance_days != 0:
        return

    scores = []
    for code in g.stocks:
        closes = attribute_history(code, g.lookback + 1)['close']
        if len(closes) < g.lookback + 1:
            continue
        scores.append((closes[-1] / closes[0] - 1, code))

    if not scores:
        return

    scores.sort(reverse=True)
    targets = [code for _, code in scores[:g.hold_num]]

    for code in g.stocks:
        if code not in targets:
            order_target(code, 0)

    weight = g.position / len(targets)
    for code in targets:
        order_target_percent(code, weight)

    log.info('调仓：' + '，'.join(targets))
'''

MEAN_REVERSION = '''# 布林带均值回归：跌破下轨买入，回到中轨上方卖出
# 适合震荡市；单边下跌时容易连续补仓失效，注意参数与止损

def initialize(context):
    g.security = '000001.XSHE'
    g.window = 20
    g.dev = 2.0
    g.position = 0.95
    g.stop_loss = 0.08         # 相对成本价止损
    set_commission(rate=0.0003, min_commission=5, stamp_duty=0.0005)
    set_slippage(0.0005)


def handle_data(context, data):
    closes = attribute_history(g.security, g.window + 1)['close']
    if len(closes) < g.window + 1:
        return

    window = closes[1:]
    mean = sum(window) / len(window)
    var = sum((x - mean) ** 2 for x in window) / len(window)
    std = var ** 0.5

    price = data.current(g.security, 'close')
    pos = context.portfolio.positions.get(g.security)
    holding = pos.amount if pos else 0

    if holding > 0 and price < pos.avg_cost * (1 - g.stop_loss):
        order_target(g.security, 0)
        log.warn(f'触发止损：{g.security} 成本 {pos.avg_cost:.2f}，现价 {price:.2f}')
        return

    if holding == 0 and price < mean - g.dev * std:
        order_target_percent(g.security, g.position)
        log.info(f'跌破下轨买入：{price:.2f} < {mean - g.dev * std:.2f}')
    elif holding > 0 and price > mean:
        order_target(g.security, 0)
        log.info(f'回归中轨卖出：{price:.2f} > {mean:.2f}')
'''

BLANK = '''# 在这里编写策略：实现 initialize(context) 与 handle_data(context, data)
# 点击右上角「API 速查」查看可用函数

def initialize(context):
    g.security = '600519.XSHG'
    set_commission(rate=0.0003, min_commission=5, stamp_duty=0.0005)
    set_slippage(0.0005)


def handle_data(context, data):
    pass
'''

TEMPLATES = [
    {
        "id": "dual-ma",
        "name": "双均线趋势",
        "description": "短均线上穿买入、下穿清仓，最经典的趋势跟踪入门策略。",
        "code": DUAL_MA,
    },
    {
        "id": "momentum",
        "name": "动量轮动",
        "description": "每 5 日按 20 日涨幅排序，持有最强的 2 只标的，等权分配。",
        "code": MOMENTUM,
    },
    {
        "id": "mean-reversion",
        "name": "布林带均值回归",
        "description": "跌破布林下轨买入、回到中轨卖出，带 8% 成本止损。",
        "code": MEAN_REVERSION,
    },
    {
        "id": "blank",
        "name": "空白策略",
        "description": "只包含 initialize 与 handle_data 骨架，从零开始写。",
        "code": BLANK,
    },
]

SEED_STRATEGIES = TEMPLATES[:3]
