# prompt-engineering · 提示词工程

个人学习知识库的 AI 主题笔记：不训练模型、只改输入的那一层优化方法与安全边界。

## 章节

| 章节 | 内容 |
| --- | --- |
| 01 概述与定位 | 能力边界、与微调/RAG 的分工判断 |
| 02 Prompt 结构与 Few-shot | 四要素结构、示例选择与顺序效应 |
| 03 思维链 CoT 与推理增强 | CoT、Self-Consistency、ToT、失效场景 |
| 04 结构化输出与 Function Calling | JSON 约束、Schema 设计、调用流程与校验 |
| 05 评估迭代与安全防护 | 评估方法、A/B 迭代、Prompt 注入与四层防护 |
| 06 实战模板与 FAQ | 5 套业务模板 + 面试 FAQ |

## 启动演示

```bash
./start.sh          # 启动本地服务并打开交互页
./start.sh 03       # 直达 CoT 真实对比演示
./start.sh --port 9000  # 指定本地服务端口
./start.sh --cli    # 终端摘要版
```

第 02/03/05 章的「真实运行」会调用 DeepSeek，Key 通过环境变量 `DEEPSEEK_API_KEY` 提供；未配置时页面仍可离线浏览。

也可在仓库根目录：`python3 main.py prompt-engineering`。
