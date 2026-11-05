# 量化交易 · quant-trading

个人知识库「金融技术」大类的第一个主题：把量化交易从「听过的概念」拆成一条能落地的链路——市场规则、数据与因子、策略与信号、回测、组合与风险、执行、实盘工程，最后补上 AI 与工具生态。

这个主题不承诺「教你赚钱」，而是回答三个更实际的问题：

1. 一个策略从想法到实盘，中间到底有多少环节、每个环节最容易错在哪；
2. 回测数字为什么不可信，怎么把它做得更可信一点；
3. 一个人/小团队在 A 股或期货市场，最小可运行的量化系统长什么样。

> 说明：示例代码只依赖 `numpy` / `pandas`，用模拟数据保证可复现；不构成任何投资建议。A 股规则以交易所最新规定为准。

## 章节

| 章节 | 内容 |
| --- | --- |
| 01 概述与定位 | 量化的定义与决策链路、策略谱系、收益拆解、产业链、能力模型、常见误解、合规边界 |
| 02 市场微结构与交易规则 | 订单簿与订单类型、撮合与集合竞价、A 股/港股/美股规则差异、显性与隐性成本、流动性指标 |
| 03 数据与因子研究 | 数据分类、复权与 PIT、七大因子家族、去极值/标准化/中性化、IC/RankIC/分组与拥挤度 |
| 04 策略体系与信号构建 | 趋势与动量、均值回归、多因子、统计套利、CTA、事件驱动、信号到仓位的映射、过拟合 |
| 05 回测系统与绩效评估 | 七大偏差、向量化 vs 事件驱动、撮合与成本假设、绩效指标公式、可信度检查清单 |
| 06 组合优化与风险管理 | 均值方差与有效前沿、协方差收缩、风险平价、Barra 风险模型、VaR/CVaR、凯利与降杠杆 |
| 07 交易执行与算法下单 | 实现落差、TWAP/VWAP/POV/IS、OMS/EMS 与 FIX、订单状态机与幂等、执行质量评估 |
| 08 工程架构与实盘落地 | 研究与实盘一致性、六层架构、技术栈、盘前/盘中/盘后主循环、三层风控、合规与 kill switch |
| 09 AI 与量化投研 | 标签设计与三重障碍、模型谱系、Purged K-Fold、多重检验与 DSR、LLM 的正确用法 |
| 10 工具生态与 FAQ | Python 工具全景、推荐项目结构、三阶段学习路线、常见坑、20 条 FAQ、术语表 |

建议顺序：01–02 建立市场与规则直觉；03–05 是研究与回测主战场；06–07 决定组合与执行质量；08 面向上线；09–10 用于扩展与选型。

## 启动演示

```bash
cd notes/quant-trading
./start.sh          # 打开浏览器可视化交互页
./start.sh 05       # 直达第 5 章「回测实验室」
./start.sh --cli    # 备用：终端文字摘要
```

也可在仓库根目录：`python3 main.py quant-trading`。

演示为纯 HTML/JS，无需安装依赖、无需联网、无需真实行情。包含：

- 订单簿市价单逐档吃单与滑点计算（02）
- 因子 IC 实验：预测力/噪声对 RankIC 的影响（03）
- 趋势与均值回归信号对比，含参数调节（04）
- 回测实验室：手续费与滑点对净值、夏普、回撤的影响（05）
- 两资产有效前沿、最小方差与最大夏普组合（06）
- TWAP / VWAP / POV 拆单与冲击成本对比（07）
- 实盘六层架构、故障模式与上线自查清单（08）
- 多重检验：试验次数如何虚高最优夏普（09）

## 先决知识

- Python 基础（函数、类、列表/字典），能读懂 pandas 的 DataFrame 操作
- 概率统计基础：均值、方差、相关系数、分位数
- 了解股票/期货的基本交易流程（开户、下单、成交、持仓）
- 不需要提前学完机器学习或随机微积分

## 参考与官方文档

- [中国证监会：证券市场程序化交易管理规定（试行）](https://www.csrc.gov.cn/)
- [上海证券交易所交易规则](https://www.sse.com.cn/lawandrules/sserules/)
- [深圳证券交易所交易规则](https://www.szse.cn/lawrules/rule/)
- [Fama & French, The Cross-Section of Expected Stock Returns (1992)](https://www.jstor.org/stable/2329112)
- [Jegadeesh & Titman, Returns to Buying Winners and Selling Losers (1993)](https://www.jstor.org/stable/2328882)
- [Almgren & Chriss, Optimal Execution of Portfolio Transactions (2001)](https://www.smallake.kr/wp-content/uploads/2016/03/optliq.pdf)
- [Markowitz, Portfolio Selection (1952)](https://www.jstor.org/stable/2975974)
- [Lopez de Prado, Advances in Financial Machine Learning](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)
- [Microsoft Qlib 官方文档](https://qlib.readthedocs.io/)
- [vn.py 官方文档](https://www.vnpy.com/docs/)
- [Backtrader 官方文档](https://www.backtrader.com/docu/)
- [VectorBT 官方文档](https://vectorbt.dev/)
