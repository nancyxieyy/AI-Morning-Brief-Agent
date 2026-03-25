# AI Morning Brief Workflow Agent 🤖🗞️

一个自动化的轻量级 Python 脚本库，每天定时拉取关注的科技/AI RSS 订阅源，通过 **大语言模型 (Claude CLI / Ollama)** 对海量信息进行降噪抓取并分类，最终为你生成一封**具有极高颜值与结构化布局 (基于嵌套 Table)** 的跨平台自适应 HTML 早报邮件。不仅如此，它还会将每一天的新闻归档在本地作为 Markdown 文件记录。

---

## 🌟 核心特性 (Features)

1. **去噪与精练筛选**：支持将几十个 RSS 聚合源交由模型理解和提炼，通过特制的 `JSON` 数据结构引导模型，剔除与关键主题无关的噪声新闻。
2. **极美跨平台邮件布局**：放弃了对邮件软件不够友好的 CSS Flex / Grid 标准，使用纯 `<Table>` 嵌套设计以及 Inline Style 控制背景与间隔。内置一套 Claude 系“大理石调”配色、进度条 UI 和彩色文章分类标签。它适配了各种老旧的 Outlook 等企业邮箱客户端。
3. **安全稳定的推送网关**：内置依赖命令行的 `curl + SMTP` 推送层，有效避开 `macOS launchd` 环境下常出现的本地 Python SSL 环境丢失报错问题。
4. **灵活双驱动架构**：默认调用命令行下强大且智能的 `Claude Code (-p)` 作为主脑。如果网络离线或调用失败，自动回退（Fallback）至本地跑的 `Ollama (qwen3.5:9b)` 服务来进行总结。

---

## 🛠️ 安装清单 (Installation)

本项目核心只依赖 `feedparser` 以解析 RSS 文件，其余均使用标准库构建，非常纯粹。

```bash
# 1. 克隆 / 下载本文件夹
# 2. 安装 Python 依赖 
pip install -r requirements.txt
```

推荐配合前置支持：
- **Claude Code CLI工具**（或自己写调用其他模型 API 的逻辑）。
- 如果要使用离线备援机制，请确保已下载并运行 Ollama 并在后台拉取了对应的模型（默认为 `ollama run qwen3.5:9b`）。

---

## 🔧 配置指南 (Configuration)

在实际投入你的自动工作流（Cron/Launchd）之前，你需要进入 `run.py` 内部修改以下配置区的信息。**我在代码中用 `xxxxx` 作为站位符标记了需要填入的敏感隐私：**

1. 修改 **`run.py` 第23行起的邮件配置**：
```python
# 邮件配置
GMAIL_USER     = "xxxxx@gmail.com"           # 你的 Gmail 发件人地址
GMAIL_APP_PWD  = "xxxxxxxxxxxxxxxx"          # 这里不是登录密码！需要去 Google 账号生成独立的 APP Password (16位)
EMAIL_TO       = "xxxxx@example.com"         # 接收简报的目标地址
```

2. 修改 **模型调用路径配置** (视乎你这台机子里 CLI 所在位置)：
```python
CLAUDE_BIN = "claude" # 如果无法被环境遍历检测到，请换为绝对地址如: "/Users/xxx/.local/bin/claude"
```

3. **定制订阅源 (原生支持 OPML 导入)**：
考虑到硬编码在 Python 代码中过于鸡肋，我在仓库内附带了 `data/hn-popular-blogs-2025.opml` 作为默认的精选启动包。主脚本的 `get_feeds()` 方法能够自动解析 OPML 并将所有的订阅树抓取进内存。
你可以自由替换这套 OPML（比如从 Inoreader/Feedly 导出自己的关注源覆盖它）。如果 OPML 缺失，则会退化为使用写死在 `run.py` 里的备份名单。

---

## 🚀 启动与使用 (Usage)

执行一遍即可直接发信：
```bash
python run.py
```

### 自动化运行 (Automating)
建议在 Mac 下结合 `launchd` 或者 Linux 下配置 `crontab` 实现每天清晨定时触发：

**Crontab 例子 (每天早晨 8:00 执行)：**
```bash
0 8 * * * cd /path/to/AI_Morning_Brief_Agent && python run.py >> /tmp/morning_brief.log 2>&1
```

*生成的 Markdown 存档新闻会保存在运行目录同级的 `Daily/` 文件夹下。*

---

## 🧭 未来演进方向 (Roadmap & Improvements)

这套 Agent 虽然已经具备了极高的工作流价值，但如果你想继续深耕，可以考虑往这些硬核开发方向迭代：

- [ ] **高并发多线程改造 (Async / ThreadPool)**
  目前 `run.py` 遍历十几个乃至上百个 RSS 源时是串行的，全卡在网络等待上。引入 `asyncio + aiohttp` 或者 `ThreadPoolExecutor` 并行抓取，能把耗时从几分钟压缩到几秒钟。
- [ ] **引入长文全文抓取扩充 (Deep Scraping)**
  很多知名博客（比如 HackerNews 高赞文章）在 RSS 中只留了一行 `summary`，导致模型总结信息量不足。后续可以引入诸如 `Jina Reader API` 或配合 `BeautifulSoup` 的爬虫脚本补全全文内容，再交给模型总结。
- [ ] **已读去重墙防抖 (Deduplication)**
  当前是基于时间戳暴力拉取最近 48 小时的文章。未来可以加入一个只有几十行的自带 `SQLite` 甚至就是一个简单的 `seen_urls.json` 用于记录推送过的文章 URL，避免大模型“车轱辘话反复说”。
- [ ] **拥抱工程化环境变量隔离 (`.env`)**
  目前通过在源码里留 `xxxxx` 占位符的做法并不“极客”。下一步应该引入 `python-dotenv`，让大家把隐私密钥存在不上传 Git 的隐藏本地文件中，使代码完全解耦。
- [ ] **超长上下文分片策略 (Chunking & Map-Reduce)**
  如果 OPML 内容过度爆炸，几十万字的 JSON 直接塞给模型可能导致注意力丢失（Lost in the middle）或是直接 Token 溢出。这会涉及基于向量和提示词流切割的进阶改写。

---

> _Automated by Claude Code / Designed by Antigravity_
