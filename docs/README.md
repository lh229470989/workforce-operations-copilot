# 架构文档导航

这组文档用于解释 Workforce Operations Copilot 当前代码的结构和设计取舍。
它描述的是本仓库已经实现的演示系统，不是生产环境部署手册。

## 推荐阅读顺序

1. [系统总览](system-overview.md)：先了解三个服务如何协作，以及数据流向。
2. [Agent 运行时](agent-runtime.md)：了解 LLM、LangGraph、工具执行和回答生成。
3. [权限、安全与上下文](security-and-context.md)：了解服务端权限、确认机制和记忆边界。
4. [架构边界规范](architecture.md)：查看精简的英文约束和设计边界。
5. [可观测性](observability.md)：查看日志、指标和隐私约束。
6. [评估方法](evaluation.md)：查看回归用例与 Agent 行为评估。
7. [本地运行与调试](local-development.md)：查看 Docker、热更新和日志调试方式。
8. [SMB AI 自动化作品集路线图](portfolio-roadmap.md)：查看后续作品集、真实集成和交付能力建设计划。
9. [作品集演示材料](portfolio-demo.md)：查看 60–90 秒视频脚本、截图清单和 Upwork 文案。
10. [SMB Calendar → Copilot → Slack 集成设计](smb-integration-design.md)：评审第二阶段 Schema、n8n、签名、幂等、重试、mock 与凭据边界。
11. [n8n 模板设置与恢复](../integrations/n8n/README.md)：导入两个 credential-free 模板，配置私有测试环境并处理失败。

## 快速定位

| 想了解的问题 | 文档 |
| --- | --- |
| 浏览器、AI API、Core API 分别负责什么？ | [系统总览](system-overview.md) |
| 一句话如何变成一次安全的工具调用？ | [Agent 运行时](agent-runtime.md) |
| LLM 能不能直接访问数据库或确认写操作？ | [权限、安全与上下文](security-and-context.md) |
| 多轮追问继承哪些字段？ | [权限、安全与上下文](security-and-context.md#上下文分层) |
| 没有模型密钥时发生什么？ | [Agent 运行时](agent-runtime.md#llm-模式与本地降级) |
| 当前系统距离生产环境还缺什么？ | [系统总览](system-overview.md#当前限制) |
| 高级 RAG 和安全 SQL 为什么这样设计？ | [高级 RAG 与安全 SQL 分析](advanced-rag-and-safe-sql.md) |
| 如何在 Docker 与本地热更新之间切换？ | [本地运行与调试](local-development.md) |
| 下一阶段为什么转向 SMB AI 自动化，准备如何执行？ | [SMB AI 自动化作品集路线图](portfolio-roadmap.md) |

## 代码入口

| 层 | 主要入口 |
| --- | --- |
| Web | `apps/web/components/ChatWorkspace.tsx` |
| Web 服务端代理 | `apps/web/app/api/` |
| AI API | `services/ai-api/app/main.py` |
| Agent 图 | `services/ai-api/app/agent.py` |
| 规划器 | `services/ai-api/app/planner.py` |
| 回答生成器 | `services/ai-api/app/composer.py` |
| 上下文解析 | `services/ai-api/app/conversation_context.py` |
| Core API | `services/demo-core-api/app/main.py` |
| Core 权限规则 | `services/demo-core-api/app/auth.py` |
