# NancysDaily · TODO & 路线图

> 最后更新：2026-04-02
> 用途：记录项目未来方向和个人成长目标，Claude 和 Nancy 都可随时来查阅。

---

## 一、早安 AI 简报 · 未来发展

### 📦 产品扩展（内容层）

- [ ] 增加更多 RSS 源，覆盖经济、时尚、艺术等板块（目前只有 AI/科技）
- [ ] 文学板块单独设计：AI 无法替代主观品味，需人工选篇 + AI 排版/摘要
- [ ] 简报支持多板块分区，读者可按板块订阅（不是全量接收）

### 📬 分发矩阵（渠道层）

- [ ] **邮件**（当前）→ 做到极致后再考虑其他渠道
- [ ] **网页版（进行中）**：FastAPI 微服务架构，可查当天及历史简报，为前后端分离打好底座，部署到 Railway/Render，详见 `feasibility_analysis.md`
  - [x] 阶段一：本地跑通（`agents/morning_brief/web/main.py` 提供纯净 API 与页面渲染）
  - [ ] 阶段二：部署公网，发给内测用户
  - [ ] 阶段三：根据反馈增加专属的 Dashboard 面板功能，深度迭代接口
- [ ] **微信公众号**：公域引流，有稳定受众后再考虑（容易损耗调性，排最后）
- [ ] 动态板块（科技/经济）开放评论；静态板块（文学/艺术）保持私密感

### 🔧 系统稳定性（工程层）

- [ ] 订阅者管理独立出来（目前硬编码在 `run.py`，改为配置文件或小型数据库）
- [ ] 邮件发送失败自动告警（目前只打 log，应有主动通知机制）
- [ ] 多 RSS 源支持健康检查：某源连续 N 天无更新 → 自动告警
- [ ] HTML 模板支持移动端自适应测试（用 webapp-testing skill）

### 💰 商业化方向（远期）

- [ ] 邮件简报 → 付费订阅（Premium 档，无广告 + 更深度内容）
- [ ] 简历量化表述：
  - "日均处理 N+ 资讯源的自动化聚合系统"
  - "通过分层架构降低 X% API 调用成本"

---

## 二、成为真正懂 Harness 的人 · 个人成长路线

> 目标：从"能跑的脚本"进化为"能自我报告、自我修复、可量化评估"的 Agent 系统

### ✅ Level 1 · 把日志做好（已完成）

- [x] 在 `run.py` 补充过程日志，不只记结果，要记过程：
  - 每篇文章是否被筛选、原因
  - JSON 解析走了哪条路径（成功 / fallback / repair）
  - 每封邮件耗时、重试次数
- [x] 建立"审计视角"习惯：每日审计日志写入 `logs/audit_YYYY-MM-DD.md`

### ✅ Level 2 · 加评估指标（已完成）

- [x] 定义可量化的简报质量指标：
  - 每日筛出 AI 相关文章数（audit log 已记录）
  - JSON 解析成功率（parse_path 字段已追踪）
  - 邮件送达率（每位订阅者，audit log 已记录）
- [x] Token 消耗监控：`agents/utils/telemetry.py`，记录 input/output token、耗时、虚拟 API 成本，落盘至 `logs/telemetry_usage.jsonl`
- [ ] 每周生成一份简单的"系统健康报告"（可以就是一个 `.md` 文件）
- [ ] 目标：能用数据证明"优化成本后，简报质量没有下降"（telemetry 数据已具备，待写分析脚本）

### 🏗️ Level 3 · 分层架构重构（再之后）

- [ ] 把 `run.py` 拆成三层：
  - **抓取层**：只拿原始数据，不调 AI（0 Token）
  - **筛选层**：AI 只看标题/来源，产出今日大纲
  - **生成层**：只对大纲选中的 3-5 篇调用完整生成
- [ ] 每一层可独立测试和替换（小模型做路由，大模型做核心）
- [ ] 学习 MCP（Model Context Protocol）官方文档：理解"协议"而非追工具

### ✅ Level 4 · 自愈能力（核心已完成，部分待做）

- [ ] RSS 源连续 N 天无更新 → 自动检测 + 告警
- [x] AI 输出 JSON 格式错误 → `_repair_json` 前瞻法自动修复，parse_path 记录路径
- [x] 用例管理自动化闭环 (Data Flywheel)：
  - [x] `save_case.py`：一键捕获最近一次 RSS 原料，打包规则封入 `badcases.json`
  - [x] `run_evals.py`：规则拦截 + Ollama 异构裁判评分，结果落盘 `logs/eval_history.jsonl`
  - [x] datasets 三库就绪：`golden.json` / `regression.json` / `badcases.json`（待填充用例）
- [ ] 用户反馈闭环（简化版 RLHF）：
  - 收到"太长了"的反馈 → 记录偏好 → 下次自动调整摘要长度
- [x] 建立自动化 Benchmark：`run_evals.py` 已可手动触发，`sys.exit(1)` 与 CI/CD 天然接轨

---

## 三、当前已完成

- [x] 早安简报 Agent 跑通（RSS 抓取 → Claude 生成 → Gmail 发送）
- [x] launchd 定时任务，每天 8:00 自动运行
- [x] 修复 JSON 引号 bug（`_repair_json` 前瞻法）
- [x] 邮件发送加入重试逻辑（最多 3 次，间隔 5 秒）
- [x] 多订阅者支持（Nancy / QaoDarkShit / Violetta）
- [x] 安装 skills：find-skills / webapp-testing / gws-docs
- [x] 晚报支持：`--mode evening`，每天 20:00 自动运行（launchd 已注册）
- [x] 时区个性化问候语：按订阅者本地时间显示早上好 / 下午好 / 晚上好 / 深夜好
- [x] Token 监控：`telemetry.py`，追踪 token 消耗与虚拟成本
- [x] LLMOps 评测基础设施：`run_evals.py` + `save_case.py` + 三库数据集
