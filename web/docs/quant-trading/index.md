# 量化交易

量化交易不是「用程序预测涨跌」，而是把投资变成一套**可验证、可复制、可规模化**的决策系统：数据进来，因子和信号算出来，组合与风控约束住，订单执行出去，最后把盈亏归因清楚。它不能保证赚钱，但能让每一次赚钱和亏钱都有解释。

本主题共 10 章，按「市场规则 → 数据与因子 → 策略与信号 → 回测 → 组合与风险 → 执行 → 实盘工程 → AI 与工具」递进。前 5 章解决「怎么研究」，后 5 章解决「怎么把它安全地跑起来」。所有示例用模拟数据，只依赖 `numpy` / `pandas`，重点章节配浏览器可视化交互演示。

> 说明：本主题是学习笔记，不构成投资建议。A 股规则（涨跌停、T+1、费用等）以交易所和券商最新规定为准；示例中的费率仅用于演示成本敏感性。

## 先决知识

- Python 基础，能读懂 pandas 的 DataFrame / groupby 操作
- 概率统计基础：均值、方差、相关系数、分位数
- 了解股票或期货的基本交易流程（下单、成交、持仓、结算）
- 机器学习不是前置条件；第 09 章会从零解释关键概念

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 决策链路、策略谱系、收益拆解、产业链、合规边界 |
| 2 | [02-市场微结构与交易规则](./notes/02-市场微结构与交易规则) | `./start.sh 02` | 订单簿与撮合、A 股/港股/美股规则、成本与流动性 |
| 3 | [03-数据与因子研究](./notes/03-数据与因子研究) | `./start.sh 03` | 复权与 PIT、因子构建、IC/RankIC、分组与中性化 |
| 4 | [04-策略体系与信号构建](./notes/04-策略体系与信号构建) | `./start.sh 04` | 趋势/回归/多因子/套利/CTA/事件驱动、信号映射 |
| 5 | [05-回测系统与绩效评估](./notes/05-回测系统与绩效评估) | `./start.sh 05` | 七大偏差、撮合假设、绩效指标、可信度清单 |
| 6 | [06-组合优化与风险管理](./notes/06-组合优化与风险管理) | `./start.sh 06` | 有效前沿、风险平价、Barra、VaR/CVaR、凯利 |
| 7 | [07-交易执行与算法下单](./notes/07-交易执行与算法下单) | `./start.sh 07` | 实现落差、TWAP/VWAP/POV/IS、OMS/EMS、订单状态机 |
| 8 | [08-工程架构与实盘落地](./notes/08-工程架构与实盘落地) | `./start.sh 08` | 六层架构、主循环、幂等、风控、对账、kill switch |
| 9 | [09-AI与量化投研](./notes/09-AI与量化投研) | `./start.sh 09` | 三重障碍、时序验证、多重检验、LLM 的正确用法 |
| 10 | [10-工具生态与FAQ](./notes/10-工具生态与FAQ) | `./start.sh 10` | 工具全景、项目结构、学习路线、常见坑、FAQ |

## 与其他主题的关系

```
量化交易（本主题）
   ├─ 数据存储与分析 → 大数据（ClickHouse / Spark / Flink / Kafka）
   ├─ 投研信息处理 → AI 技术（RAG / Agent / 大模型原理）
   └─ 业务场景 → 金融技术（投研平台、财富管理）
```

## 如何启动演示

```bash
cd notes/quant-trading
./start.sh          # 浏览器可视化交互
./start.sh 05       # 直达回测实验室
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py quant-trading` / `python3 main.py quant-trading 05`。演示为纯前端，无需安装依赖。

## 学习建议

1. **先跑再读**：第 05 章的代码可以完整复制运行，先看到「成本如何吃掉收益」，再回头理解指标定义。
2. **每章改一个假设**：把滑点从 5 bps 调到 30 bps、把 T+1 改成 T+0、把样本外挪一年，观察结论是否还成立。
3. **用清单代替自信**：上线前逐条走第 08 章的自查清单，比「我觉得没问题」可靠得多。

## 参考与官方文档

- [中国证监会](https://www.csrc.gov.cn/)
- [上海证券交易所规则](https://www.sse.com.cn/lawandrules/sserules/)
- [深圳证券交易所规则](https://www.szse.cn/lawrules/rule/)
- [Microsoft Qlib](https://qlib.readthedocs.io/)
- [Backtrader](https://www.backtrader.com/docu/)
- [VectorBT](https://vectorbt.dev/)
- [vn.py](https://www.vnpy.com/docs/)
- [Almgren & Chriss (2001), Optimal Execution of Portfolio Transactions](https://www.smallake.kr/wp-content/uploads/2016/03/optliq.pdf)
- [Lopez de Prado, Advances in Financial Machine Learning](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)
