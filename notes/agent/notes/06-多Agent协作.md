# 06 多Agent协作

## 一句话

**多 Agent（Multi-Agent）= 多个有角色分工的 Agent 通过消息或共享状态协作完成任务**，核心价值是分工带来的上下文隔离与专业化，代价是协调复杂度和成本翻倍。经验法则：**单 Agent 能做好的绝不上多 Agent**；只有当任务天然分角色、上下文互相污染、或需要并行时才值得拆分。

## 何时需要多 Agent

### 该拆的信号

| 信号 | 说明 | 例子 |
| --- | --- | --- |
| 角色天然分离 | 任务本身是流水线式分工 | 研究员搜集 → 分析师建模 → 写手成稿 → 审稿人把关 |
| 上下文污染 | 单一 Agent 的上下文被无关信息撑爆 | 搜索 Agent 看了 50 个网页，但写报告的只需要结论 |
| 并行加速 | 多个子任务互相独立 | 同时查 5 家竞对的财报 |
| 能力异构 | 不同子任务适合不同模型/工具 | 检索用小模型省钱，最终综合用旗舰模型 |

### 不该拆的信号

- 任务线性且短（< 5 步）——拆分的协调开销 > 收益
- 步骤间强依赖、需要全程共享上下文——拆开会丢信息
- 预算紧张——多 Agent token 成本通常是单 Agent 的 3-10 倍

**反模式警告**：把「一个 prompt 写得不好的单 Agent」拆成多 Agent，往往只是把问题扩散了。先优化单 Agent，再考虑拆分。

## 四种协作模式

### 1. 主管-工人（Supervisor / Orchestrator-Worker）

```
        ┌───────────┐
        │ Supervisor │  分派任务、汇总结果
        └─────┬─────┘
     ┌────────┼────────┐
     ▼        ▼        ▼
  Worker1  Worker2  Worker3
  (搜索)   (计算)    (写作)
```

- 主管 LLM 决定「下一步派给谁」，工人干完活把结果交还主管
- 最通用，LangGraph 官方推荐的主模式
- 风险：主管成为单点瓶颈和单点故障

### 2. 流水线（Pipeline / Sequential）

```
Researcher → Analyst → Writer → Reviewer → END
```

- 流程固定，每个 Agent 只跟上下游交接
- 本质是「每个环节用 LLM 的 Workflow」，可控性最强
- 适合步骤明确的内容生产类任务

### 3. 辩论（Debate）

```
     ┌─ Agent A（正方）─┐
问 ──┤                 ├──→ Judge（裁判）→ 结论
     └─ Agent B（反方）─┘
        ↑ 多轮互相反驳 ↑
```

- 多个 Agent 持不同立场互相质询，裁判收敛
- 用于提高答案质量（事实核查、红队测试）
- 成本最高，慎用于生产

### 4. 群体自主（Swarm / Network）

- 无中心，Agent 间自由互相移交任务（handoff）
- 最灵活也最不可控，OpenAI Swarm 走这个路线
- 适合探索性任务，不适合强 SLA 场景

| 模式 | 可控性 | 成本 | 适用 |
| --- | --- | --- | --- |
| 流水线 | ★★★ | ★ | 步骤固定的生产任务 |
| 主管-工人 | ★★ | ★★ | 通用复杂任务 |
| 辩论 | ★★ | ★★★ | 质量优先的评审任务 |
| 群体自主 | ★ | ★★★ | 探索性任务 |

## 框架对比：AutoGen vs CrewAI vs LangGraph

| 维度 | AutoGen（微软） | CrewAI | LangGraph |
| --- | --- | --- | --- |
| 抽象 | 会话式 Agent（对话驱动） | 角色 + 任务 + 流程 | 状态图（最底层） |
| 上手难度 | 中 | **低（最像业务语言）** | 中高 |
| 可控性 | 中 | 中 | **高** |
| 人工审批 | 支持 | 支持 | 原生 interrupt |
| 适用 | 研究、对话式协作 | 业务流水线快速搭建 | 生产级定制编排 |
| 心智模型 | 「几个 Agent 在群里聊天」 | 「一个团队接项目」 | 「一台状态机」 |

**选型建议**：
- 快速验证「角色分工是否有效」→ CrewAI（几十行搞定）
- 生产环境、要审批/恢复/观测 → LangGraph
- 学术实验、多 Agent 对话研究 → AutoGen

```python
# CrewAI 风格：用业务语言描述协作
researcher = Agent(role="行业研究员", goal="搜集目标公司信息", tools=[search])
writer = Agent(role="分析师", goal="输出研报", tools=[calculator])

task1 = Task(description="调研 {company} 的业务与财报", agent=researcher)
task2 = Task(description="基于调研写 500 字研报", agent=writer)

crew = Crew(agents=[researcher, writer], tasks=[task1, task2],
            process=Process.sequential)
crew.kickoff(inputs={"company": "宁德时代"})
```

## 通信与共享状态

多 Agent 系统的核心工程问题：**信息怎么流动**。

### 三种通信方式

| 方式 | 实现 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 消息传递 | Agent 间互发消息（对话历史） | 直观、可审计 | 消息膨胀、噪音多 |
| 共享状态 | 公共黑板/State 对象读写 | 结构化、可控 | 需设计 Schema |
| 工具移交 | handoff：把整个会话转给下一个 Agent | 简单 | 上下文全量转移，无隔离 |

### 上下文隔离的最佳实践

**工人只看任务说明，不看你和用户的全部历史**：

```python
def supervisor_node(state):
    # 主管给工人发的是「干净的任务说明」，不是全部对话历史
    task = {"instruction": "搜索宁德时代2025年营收", "context": state["goal"]}
    result = worker.invoke({"messages": [("user", json.dumps(task))]})
    # 工人只返回「结论摘要」，不是它的全部中间过程
    return {"findings": state["findings"] + [result["summary"]]}
```

两条铁律：
1. **下发要窄**：只给工人它需要的信息
2. **回收要薄**：工人只交回结论，中间过程（几十轮搜索细节）就地丢弃或归档

## 成本与延迟控制

多 Agent 的成本公式：`总 token ≈ Σ(每个 Agent 的轮数 × 每轮上下文)`，而上下文随协作轮次累积——成本超线性增长。

| 手段 | 效果 |
| --- | --- |
| 分层用模型 | 主管/综合用旗舰模型，工人用 Haiku/mini 级小模型，省 50-80% |
| 并行执行 | 独立工人并行跑，墙钟时间 ≈ 最慢的一个而非总和 |
| 轮数预算 | 每个 Agent 独立 max_iter；全局总步数也设上限 |
| 上下文裁剪 | 交接时摘要压缩（见第 07 章） |
| 缓存 | 相同子任务（如同一股票查询）结果缓存复用 |

延迟估算：串行 3 个 Agent × 各 4 轮 × 每轮 2s ≈ 24s；并行独立部分后可能压到 10s 内。**面向用户的 Agent，总延迟预算建议 < 30s**，超出就要砍协作轮次或改异步。

## 常见问题

**Q：多 Agent 真的比单 Agent 效果好？**
A：分场景。Cognition（Devin 团队）公开反思过：多 Agent 在需要**强一致上下文**的任务上反而更差，因为信息在交接中丢失。收益明确的场景是并行探索（广度搜索）和上下文隔离（脏活外包）。先问「拆了之后每个 Agent 的上下文是不是更干净了」，是才拆。

**Q：主管-工人里工人之间能直接通信吗？**
A：可以但不推荐。网状通信会让调试地狱化——你再也说不清某个错误结论是谁污染了谁。生产系统保持星型：一切经过主管。

**Q：如何评估多 Agent 系统？**
A：三层评估：① 端到端任务成功率；② 每个 Agent 的单元测试（固定输入测输出）；③ 轨迹审计（trace 每步 token 消耗和决策质量）。缺了②，端到端失败时你定位不到是谁的锅。

## 自测

1. 列举四个「该拆成多 Agent」的信号和对应的反模式。
2. 主管-工人和流水线模式的本质区别？
3. 「下发要窄、回收要薄」具体指什么？违反会怎样？
4. 多 Agent 成本为什么超线性增长？给出两种控制手段。

## 参考与官方链接

- [AutoGen（微软）](https://github.com/microsoft/autogen)
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [LangGraph Multi-Agent 模式](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [Cognition: Don't Build Multi-Agents](https://cognition.ai/blog/dont-build-multi-agents)
- [OpenAI Swarm](https://github.com/openai/swarm)
