# SMB AI 自动化作品集路线图

## 1. 定位与目标

本项目的下一阶段定位是：

> 面向中小企业和成长型团队，展示可审计、可确认、可集成的 AI 业务自动化能力。

目标不是把演示项目扩展成一个包罗万象的企业平台，而是让潜在客户在较短时间内确认以下能力：

- 能把自然语言请求转换为可靠的业务流程；
- 能连接 API、Webhook 和常见业务工具；
- 能在写操作前提供预览、权限检查和人工确认；
- 能交付可测试、可部署、可移交的完整解决方案；
- 能根据业务结果解释自动化价值，而不只展示框架和 Prompt。

主要目标岗位包括 AI Automation Engineer、AI Agent Developer、API Integration Developer 和 Full-stack AI Developer。现有的 LangGraph、FastAPI、Next.js、MCP、权限边界、评估与审计能力作为差异化技术基础，而不是首页叙事的主体。

## 2. 执行原则

- 按阶段推进；前一阶段达到验收标准后再扩大范围。
- 每个阶段拆成可独立验证的小批次，尽量通过独立分支和 Pull Request 交付。
- 优先提高客户理解和信任，再增加新的 Agent 能力。
- 第三方写操作继续遵守 dry-run、显式确认、服务端重新鉴权和审计边界。
- 演示数据、截图、日志和 Git 历史不得包含原项目、客户或雇主的非公开信息。
- 新增集成必须有失败处理、幂等策略、配置说明和最小可重复演示。
- 路线图记录的是当前决策，不把未来设想描述为已实现能力。

## 3. 阶段总览

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 第一阶段 | 让当前项目达到可直接用于 Upwork 投递的展示质量 | 已完成：PR CI、合并、干净环境录制和公开视频 URL 均已闭环 |
| 第二阶段 | 增加一个贴近中小企业场景的真实自动化纵向案例 | 实现中：公共代码、两个 n8n 模板与 mock 证据已完成；仅余私有账号验证与录像 |
| 第三阶段 | 补齐常见交付能力和 Upwork 需求关键词 | 待开始 |
| 第四阶段 | 根据真实投递与客户反馈选择专业化方向 | 待开始 |

## 4. 第一阶段：作品集成交准备

### 目标

让不了解代码库的潜在客户在 60 秒内理解产品价值，并能通过截图、视频或在线演示快速验证主要能力。

### 工作范围

#### 4.1 修复可见体验问题

- [x] 空对话首次加载时不自动滚动，确保常见桌面视口能完整看到欢迎区域。
- [x] 为模型回答提供受限、安全的富文本呈现。
- [x] 允许段落、列表、粗体、斜体、行内代码和代码块。
- [x] 不渲染模型提供的原始 HTML；模型生成的链接不作为可信业务操作入口。
- [x] 为 `1280 × 720` 桌面视口和 `390 × 844` 移动视口增加回归验证。

#### 4.2 重构 README 的作品集叙事

- [x] 首屏说明业务问题、目标用户和可量化、可验证的交付证据。
- [x] 增加产品截图和 60–90 秒演示脚本入口；在线 Demo 和公开视频在真实可用前不设置占位链接。
- [x] 增加三条推荐演示路径：政策问答、越权拒绝、写操作预览与确认。
- [x] 将权限、审批、审计、评估和 CI 汇总为易理解的差异化能力。
- [x] 明确作者承担的设计和实现范围。
- [x] 保留架构、运行方式、安全边界与已知限制，但降低其首屏权重。
- [x] 录制、上传演示视频，并将真实可访问的 URL 加入 README。

#### 4.3 准备演示材料

- [x] 制作 6 张不含敏感信息的产品截图。
- [x] 编写 60–90 秒演示视频脚本。
- [x] 脚本覆盖一次读操作、一次拒绝或权限差异、一次 dry-run 与确认。
- [x] 准备适合 Upwork Portfolio 的短版项目描述、问题、方案和结果说明。

#### 4.4 完善仓库展示信息

- [x] 设置 GitHub repository description。
- [x] 添加与实际能力相符的 topics。
- [x] 在线演示可用后再设置 homepage URL；当前明确保持为空。
- [x] 当前默认分支 `verify` CI 为绿色；README 不展示占位视频、失效在线 Demo 或未实现承诺。
- [x] 第一阶段主批次通过 Pull Request #2 的完整 CI 后合并到默认分支。

### 验收标准

- 首次打开桌面和移动页面时，主要标题与演示入口正常可见。
- 模型回答不会暴露 Markdown 控制字符或执行任意 HTML。
- README 首屏包含业务定位、视觉证据和明确的演示路径。
- 所有现有测试、生产构建、安全扫描和浏览器 E2E 通过。
- 仓库 metadata 完整；没有把计划中的能力表述为已实现。

### 第一阶段实施证据（2026-08-13）

- 客户问题：原首屏在 `1280 × 720` 下无法完整看到 5 条演示路径；模型回答以纯文本显示 Markdown；README 先讲技术栈，缺少销售路径和视觉证据。
- 范围：只改进展示层、回归验证、作品集叙事和仓库 metadata；不新增 Agent intent，不增加第三方写能力，不发布公共 LLM Demo。
- 代码证据：`apps/web/components/ChatWorkspace.tsx` 使用受限 Markdown 元素集合并禁止原始 HTML；空对话不触发自动滚动；`apps/web/e2e/copilot.spec.ts` 固定验证两个目标视口。
- 视觉证据：`docs/assets/portfolio/` 保存 6 张从本地真实服务捕获的截图；`docs/portfolio-demo.md` 保存录制脚本、Upwork 文案和发布检查表。
- 自动验证：Demo Core API `29 passed`，AI API `104 passed`，MCP `4 passed`，Web `14 passed`，Playwright `5 passed`；TypeScript、Next.js production build 和 publication security scan 通过。
- 外部状态：GitHub description 和 8 个真实能力 topics 已设置；homepage 保持为空；第一阶段主批次 Pull Request #2 的 8 个 CI job 全部通过并 squash 合并为 `344508a`。
- 视频证据：从合并后的干净 `main` 和全新虚构数据卷录制 `80.72s`、`1280 × 720` WebM；视频经关键场景抽帧复核后上传为 `portfolio-demo-v1` release asset，SHA-256 为 `3a2cf393fba54d4d9353ddb2592f3fa1b43d6f79f27bbc96b5e1577a5212190e`。

### 第一阶段闭环记录

1. [x] 创建 `agent/portfolio-phase-1` 并提交 Pull Request #2。
2. [x] 等待 8 个 CI job 全部通过，squash 合并到 `main`。
3. [x] 从合并后的干净 `main` 删除并重建两个虚构数据卷及四服务环境。
4. [x] 录制、抽帧复核并上传 80 秒演示视频。
5. [x] 通过小型后续 Pull Request 添加真实视频 URL。
6. [x] 将第一阶段标记为完成；第二阶段仅从独立设计分支开始。

## 5. 第二阶段：中小企业自动化纵向案例

### 目标

证明当前 Copilot 不只是操作虚构数据库，还能接入中小企业常见的外部工作流，并在真实集成中保持审批、安全和可恢复性。

### 推荐案例

```text
Calendar 或标准 Webhook 事件
        ↓
提取并验证可填报工作
        ↓
生成结构化工时建议
        ↓
用户预览并显式确认
        ↓
写入工时系统
        ↓
向 Slack 或 Email 发送结果通知
```

### 初始实现边界

- 提供一个稳定、版本化的 Webhook 输入契约。
- 提供一个可导入的 n8n workflow，展示触发、转换、调用和错误分支。
- 选择一个输入平台和一个通知平台完成真实 sandbox 集成。
- 默认建议优先评估 Google Calendar 作为输入、Slack 作为通知。
- 外部平台密钥仅通过环境变量或 secret store 注入，不进入仓库、截图或日志。
- 外部事件只能生成建议或 dry-run，不能绕过现有确认流程直接写入。
- 为重复事件定义幂等键，为限流、超时和临时错误定义重试策略。
- 提供断开第三方服务时仍可运行的本地 mock 演示路径。

### 阶段开始前的决策节点

在编码前确认以下事项：

1. 第一组真实平台选择；
2. 使用托管 n8n、self-hosted n8n，还是只发布可导入模板；
3. 在线 Demo 是否允许真实第三方调用；
4. 演示账户、配额、数据清理和密钥轮换策略。

### 已确认方案（2026-08-13）

| 决策项 | 确认方案 |
| --- | --- |
| 输入平台 | Google Calendar，只读 |
| 通知平台 | Slack，只发送确认结果 |
| n8n 形态 | 发布两个可导入模板，不托管公共 n8n |
| 在线 Demo | 只运行 mock，不连接真实账号，并明确标记 `simulated integration` |
| 真实集成 | 仅在私有测试环境和录制视频中展示 |
| 测试账户 | 独立 Google 测试账号、test-only Cloud 项目、OAuth consent 配置、专用 Calendar；Slack 优先 Developer Sandbox，不满足条件时使用独立免费测试 workspace 和专用频道 |
| 数据 | 全部使用虚构日程、人员、项目和通知 |
| 配额 | 主动设置低配额、低频率、有限重试；Google 使用独立 test-only project 验证配额错误处理 |
| 凭据 | 不进入仓库、截图、日志、CI 或 n8n 模板 JSON |

Google Calendar 不是普通意义上的 sandbox。本阶段只申请
`https://www.googleapis.com/auth/calendar.readonly`，项目不修改日历；测试
环境使用独立账号、独立 Cloud project、独立 OAuth consent 配置、专用
Calendar 和虚构事件。Slack 第一版只使用 Incoming Webhook，不读取历史
消息；Webhook URL 视为 secret。若收到 `429`，按 `Retry-After` 等待，且
通知发送速率不超过每秒一条。

第二阶段在编码前先通过独立分支交付 `docs/smb-integration-design.md`，固定
接口 Schema、两个 n8n workflow、HMAC 签名、幂等、重试、mock、审计与
凭据边界；文档评审通过后再实现。

推荐拆成两个模板，避免 n8n 执行实例长时间等待人工确认：

```text
Workflow A：Google Calendar（只读）
  → 筛选虚构目标事件
  → 转换成受限 WorkEvent Schema
  → HMAC 签名调用 Copilot ingest API
  → 只创建建议 / dry-run

Web：查看建议 → 显式确认 → Core API 重新鉴权并写入
  → 生成可信 confirmed event

Workflow B：confirmed event / webhook
  → 读取可信结构化结果
  → Slack Incoming Webhook
  → 发送成功或失败通知
```

固定安全边界：Calendar payload 不直接进入模型；Calendar 事件不能直接
触发业务写入；幂等键由 calendar ID、event ID 和更新时间生成；同一事件
重复触发不能产生重复记录；Slack 只通知确认成功后的可信结果；真实凭据不
参加 CI，CI 只使用 fixtures、mock server 和 contract tests。

### n8n 模板实施证据（2026-08-21）

- 两个禁用状态、无凭据的公开模板保存在 `integrations/n8n/`，分别负责只读
  Calendar → suggestion 与 confirmed event → Slack delivery；
- Workflow A 只映射显式 private marker 与四个允许字段，不携带原 Calendar
  payload，也不包含人工等待或确认节点；
- Workflow B 在 Slack 节点前强制 raw-body HMAC 校验和持久 delivery claim，
  固定消息字段，并以一秒 gate 限速；
- `scripts/scan_n8n_templates.py` 在 CI 中检查节点顺序、无凭据导出、runtime-only
  secret、受限字段与禁止值；全仓 publication security scan 同时覆盖模板；
- 两份 JSON 已在全新 `n8nio/n8n:2.34.6` 容器中通过 CLI 导入，结果为
  `Successfully imported 2 workflows`；真实 Google/Slack 执行只在后续私有录制
  环境中完成，不作为公共 Demo 或 CI 的前置条件。

### Public mock 实施证据（2026-08-21）

- Jamie persona 可以从 Web 显式加载一个固定的虚构 Calendar 事件；页面同时声明
  没有连接 Google 账号，后端不会发外网请求；
- mock 复用正式的 suggestion、prepare、actor-bound confirmation、source link 和
  confirmed outbox 边界，而不是直接插入工时或伪造 Slack 成功；
- 同一 fixture 在确认前只返回同一 suggestion，确认后再次加载返回 `409`，不能
  创建第二条工时；
- public mode 启动时如果发现 ingest 或 notification secret 会直接拒绝启动；私有
  真实测试必须显式关闭 public mock；
- 新增 Core API、React 和 Playwright 回归；干净虚构数据卷中的浏览器链路已验证
  Calendar suggestion → dry-run → confirm → simulated Slack preview → duplicate denied。

### Upwork 包装状态（2026-08-21）

- [x] 创建可直接复制的 Project Catalog 标题、摘要、三档范围、客户 requirements、
  steps、FAQ、proposal opener 和范围排除；
- [x] 按当前 Upwork 官方规格准备独立的 55 秒英文视频脚本和 gallery 顺序；
- [x] 明确现有 80 秒 WebM 不能直接作为 Project Catalog 视频；
- [x] 固定真实与 simulated evidence 的措辞边界；
- [ ] 生成并上传 `1000 × 750`、4:3 gallery 文件；
- [ ] 在私有账号环境验证 Google readonly → n8n → Copilot → Slack；
- [ ] 录制不超过 60 秒、100 MB 的 MP4，并在 Upwork 账号中创建与提交 listing。

完整可复制内容和最终人工清单见 `docs/upwork-project-package.md`。

设计依据：[Google Calendar API 配额与 test-only project](https://developers.google.com/workspace/calendar/api/guides/quota)、
[Google Calendar OAuth scopes](https://developers.google.com/workspace/calendar/api/auth)、
[Slack Incoming Webhooks](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)、
[Slack rate limits](https://docs.slack.dev/apis/web-api/rate-limits/) 和
[Slack Developer Sandboxes](https://docs.slack.dev/tools/developer-sandboxes/)。

### 验收标准

- 从外部事件到建议、确认和通知可以完成一次端到端演示。
- 重复事件不会重复创建业务记录。
- 失效凭据、平台超时和无效 payload 有可理解的错误与审计信息。
- n8n workflow、环境变量、sandbox 设置和故障恢复有完整文档。
- CI 可在无真实第三方凭据时通过 mock 或 contract tests 验证集成逻辑。

## 6. 第三阶段：可交付的自动化工程能力

### 目标

补齐中小企业客户在交付、上线和维护阶段常见的要求，使项目能够支撑 API Integration、n8n Automation 和 AI Workflow 类岗位。

### 工作候选项

- OAuth 2.0 或 API token 的安全配置与刷新示例；
- Webhook 签名验证、重放保护和 payload 版本管理；
- 后台任务、超时、重试、失败队列和通知；
- 幂等写入和可重复执行策略；
- 部署、备份、恢复、监控和客户交接清单；
- 真实模型评测报告，包括分类通过率、错误确认、p50/p95 延迟和估算成本；
- 将超大 Web、AI API 和 Core API 文件按职责拆分；
- 增加有意义的覆盖率报告和关键故障路径测试。

### 排序原则

不要求一次实现全部候选项。第二阶段暴露出的真实交付风险优先；其次选择 Upwork 目标岗位中重复出现、且能被本项目客观证明的能力。

### 验收标准

- 至少一个集成具备认证、重试、幂等、监控和恢复说明。
- 可以通过文档将项目交给另一名开发者部署和维护。
- 有一次版本化、可重复执行的真实模型评测结果。
- 核心模块职责比当前结构更清晰，重构不改变权限与确认边界。

## 7. 第四阶段：由市场反馈决定专业化方向

### 目标

根据真实投递、面试和客户需求选择下一项高投入能力，避免凭想象持续扩大仓库。

### 反馈指标

- 各类岗位的投递数、回复数、面试数和成交数；
- 客户重复询问但当前无法证明的能力；
- 哪类演示路径最容易引发具体项目讨论；
- 预估工作量、预算和实际成交价格的差异；
- 客户更需要低代码交付、自定义后端，还是企业基础设施。

### 可选方向

#### RAG 与知识系统

当 RAG 岗位反馈最强时，再增加 embeddings、向量检索、reranking、检索评测和知识更新流程。

#### CRM 与销售自动化

当 HubSpot、Pipedrive、GoHighLevel 或线索处理需求最多时，增加一个正式 CRM adapter 和可复用 onboarding 模板。

#### 内部工具与企业能力

当客户开始要求更完整的内部平台时，优先增加 PostgreSQL、数据库迁移、OIDC/SSO、多租户隔离和 OpenTelemetry。

#### n8n 自动化产品化

当 n8n 项目形成稳定来源时，将通用 workflow、配置校验和交接材料整理成独立模板或独立案例仓库，而不是让本仓库无限膨胀。

## 8. 当前明确不做

- 不在第一阶段继续增加新的 Agent intent 或业务功能。
- 不开放无限制、无预算保护的公共 LLM Demo。
- 不为了关键词声称使用尚未实现的向量数据库、生产认证或多租户能力。
- 不在没有真实需求验证前加入语音 Agent、支付、医疗或金融合规流程。
- 不把 n8n、Make 或 Zapier 当作唯一交付能力；复杂权限和业务规则继续由受测试的应用代码承担。
- 不追求没有业务意义的 100% 测试覆盖率。

## 9. 执行与状态更新方式

每个工作批次开始前记录：

- 要解决的客户或工程问题；
- 明确范围与非目标；
- 验收命令和人工验证路径；
- 是否涉及外部账户、费用、凭据或公开部署。

每个工作批次完成后：

- 更新本路线图对应条目的状态；
- 记录测试、截图或评测证据；
- 更新 README 中受影响的已实现能力和已知限制；
- 通过独立 Pull Request 合并，保持默认分支可演示。

## 10. 决策记录

| 日期 | 决策 | 原因 |
| --- | --- | --- |
| 2026-08-13 | 主要市场定位从宽泛的企业 Copilot 展示收敛为 SMB AI 自动化与内部工具 | 新 Upwork 账号更容易通过范围明确、周期较短的业务自动化项目建立评价；现有安全工程能力可以形成差异化 |
| 2026-08-13 | 先完成作品集包装和体验修复，再增加第三方集成 | 当前功能已经充分，首要短板是客户理解、视觉证据和真实交付证明 |
| 2026-08-13 | 第一个新案例采用“外部事件 → 建议 → 人工确认 → 通知”的纵向结构 | 该结构复用现有 dry-run/confirmation 优势，也贴合中小企业常见工作流 |
| 2026-08-13 | 第二阶段采用 Google Calendar 只读输入、Slack Incoming Webhook 确认后通知和两个独立 n8n 模板 | 最小权限、避免长时间等待的 n8n 执行、阻止外部事件绕过人工确认，并便于 SMB 客户理解和复用 |
| 2026-08-17 | 第二阶段设计评审通过，n8n 验证基线锁定为 `2.34.6`，先实现 Contracts 批次 | 先冻结机器合同和跨系统签名测试向量，降低后续持久化、UI 与 workflow 模板之间的返工风险 |
| 2026-08-19 | 第二阶段设计合并，Contracts 批次完成 | 用无凭据 JSON Schema、Pydantic、固定 HMAC/幂等向量和虚构 fixtures 锁定跨系统边界；nonce 与数据库幂等进入 persistence 批次 |
| 2026-08-21 | Ingest persistence 批次完成 | 签名入口只创建建议；runtime secret、nonce 重放、映射、修订历史与 source 唯一约束均由服务端控制，下一批接入 Web review |
| 2026-08-21 | Web review 批次完成 | 外部建议由 actor 单独查看、编辑和 prepare；确认时重新校验并原子写入工时与唯一 source link，n8n 与模型均拿不到 confirmation token |
| 2026-08-21 | Outbox notification 批次完成 | 确认事务写入最小 confirmed event；持久 claim/complete ledger 阻止重复发送与未知结果自动重试，public UI 只展示 simulated preview |
