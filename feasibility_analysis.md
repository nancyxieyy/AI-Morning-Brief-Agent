# NancysDaily · 网页版内测方案

> 最后更新：2026-04-02  
> 目标：在不动现有早报引擎的前提下，搭一个动态网页版，可查当天及历史简报，可部署到公网供内测用户访问。

---

## 一、技术选型

| 项目 | 选择 | 原因 |
|---|---|---|
| 后端框架 | FastAPI | 拥抱大长微服务生态，天生支持高并发、自带接口文档，为后续前后端完全分离（如小程序）打好 API 底座 |
| 模板引擎 | Jinja2Templates | 兼容服务端首屏渲染（SSR），但也同时提供输出 JSON 的接口能力 |
| 数据来源 | 直接读 `Daily/YYYY-MM-DD/` 目录 | 零数据库，零搬迁成本 |
| 部署平台 | Railway（首选）或 Render | 免费档，连 GitHub 自动开服，绝佳的内测机 |
| 域名 | 先用平台提供的子域名 | 内测阶段够用，后续可绑自定义域名 |

---

## 二、功能范围（内测 MVP）

**首页 `/`**
- 按日期倒序列出所有已生成的简报
- 每条显示：日期、当天摘要第一句话（预览）
- 区分早报 / 晚报（如果当天有两份）

**详情页 `/brief/<date>`**  
- 显示指定日期的完整简报
- 复用 `html_renderer.py` 的渲染逻辑，不重复造轮子
- 顶部加导航：← 前一天 / 今天 / 后一天 →

**设计原则**
- 不做登录系统，内测靠 URL 不公开传播控制
- 不做订阅管理，那是第二阶段的事
- 移动端可读（html_renderer 本身已有响应式 table 布局）

---

## 三、微服务边界隔离结构（架构重构）

本展示层仅归属于 `morning_brief` 限界上下文逻辑范围，隔离且坚决不污染其他 Agent 服务：

```
agents/morning_brief/web/
  main.py              ← FastAPI 主应用级入口
  api/
    routes.py          ← (预留设计) 抽离出的纯 JSON REST 接口层
  templates/
    index.html         ← 首页：历史倒序列表
    brief.html         ← 详情页：包裹简报 HTML 的外壳壳子
  static/
    style.css          ← 契合极客氛围的极简样式
  requirements.txt     ← fastapi, uvicorn, jinja2
Procfile               ← Railway 启动点（web: uvicorn agents.morning_brief.web.main:app --host 0.0.0.0 --port $PORT）
```

---

## 四、三阶段实施计划

### 阶段一：本地跑通（1-2 小时）
1. 书写 `agents/morning_brief/web/main.py`：构建 FastAPI 路由（提供 HTML 页面及预留 JSON）。
2. 写两个模板：首页列表大盘 + 单日内嵌呈现详情页。
3. 本地 `uvicorn agents.morning_brief.web.main:app --reload` 启动沙盒验证，历史简报必须全数展示通畅。
4. **绝不可侵入现有早报的每天生成流程！**

### 阶段二：部署到公网（30 分钟）
1. 在 Railway 或 Render 新建项目，连接 GitHub repo
2. 设置环境变量（`DAILY_DIR` 路径，或直接用相对路径）
3. 添加 `Procfile` 启动命令
4. 拿到公网 URL，发给 Nancy / Violetta / QaoDarkShit 内测

### 阶段三：内测反馈迭代（按需）
- 根据内测反馈决定是否加：搜索、RSS 订阅按钮、夜间模式等
- 订阅者管理页面（目前硬编码在 run.py，可迁移到此处）

---

## 五、部署注意事项

**Daily/ 目录同步问题**  
Railway/Render 每次部署时会拉最新代码，但 `Daily/` 里的文件是运行时生成的，**不在 git 仓库里**（应该在 `.gitignore`）。解决方案二选一：

- **方案 A（推荐，简单）**：把 `Daily/` 加入 git 追踪，每天早报跑完后 `git push`，部署平台自动更新。缺点：repo 会越来越大。
- **方案 B（稳健）**：把生成的简报存到云存储（如 Cloudflare R2 免费档），Web 应用从云存储读取。稍复杂，但与 git 解耦。

内测阶段先用**方案 A**，简单直接。

---

## 六、保留备用：内容扩展方向（未来）

以下是中长期可考虑的方向，内测验证有受众后再做：

- **RSSHub 接入**：解决微信公众号等无 RSS 平台的抓取问题，[docs.rsshub.app](https://docs.rsshub.app/)。需自建或租用稳定节点。
- **多板块订阅**：Violetta 只看 AI，Nancy 看全量，可通过配置文件实现，不需要数据库。
- **HITL 文学板块**：手动维护一个名言/散文库（Notion/飞书表格均可），脚本每天随机取一段放邮件/网页末尾。大模型审美不可靠，这块必须人工把关。
- **付费订阅**：内测有稳定读者后，再评估 Premium 档可行性。版权边界参考：AI 重写事实性内容 + 注明原文链接 = 目前相对安全，但国内法律环境持续关注。

---

## 七、不做的事（防止过度设计）

- ❌ 现阶段不接微信公众号（运营成本高，调性难控制）
- ❌ 现阶段不做用户注册/登录（内测靠 URL 够了）
- ❌ 现阶段不做评论功能
- ❌ 不重写 html_renderer，直接复用
