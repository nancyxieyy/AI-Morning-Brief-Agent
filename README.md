# Daily Brief Agent & LLMOps Engine 🤖🗞️

从最初的一个“简单的自动化 Python 脚本”，本作已经横跨进化为一个具备 **LLMOps 评测体系**、**Token 透明追踪引擎** 以及 **FastAPI 微服务展现大盘** 的高级人工智能工作流架构。
系统依靠极低的人工干预，每天能定时拉取关注的科技/AI RSS 订阅源，不仅通过 **大语言模型 (Claude CLI / Ollama)** 对海量的噪声信息进行降维打击和结构化提取，最后还会为你生成包含高颜值排版设计的跨平台专属早晚报。

---

## 🌟 核心新特性 (State-of-the-Art)

1. **LLMOps 全链路评测沙盒 (Evals Runner)**：系统内部集成了 `Golden Set`、`Regression Set` 与 `Badcases` 弹药库。针对每一次指令、微调或是模型的颠覆，沙箱不仅能在第一层配置了极速规则墙拦截，还挂载了 **LLM-as-a-Judge** 异构模型进行裁决，以确保生成物的美感与内容质量能被量化跟踪，再不退化！
2. **Telemetry 透明资产监控黑匣子**：所有的大模型生成耗时、Input/Output Tokens 实物吞吐量、甚至预估的虚拟算力美金花费 (USD)，均通过无侵入式的监听器精确记录落盘进 `logs/telemetry_usage.jsonl`，且你能随时调用 Pandas 高维分析工具包将其一键渲染出资金与时效的高清大盘走势图。
3. **极美跨平台原生邮件大盘与 Web 深层档案馆**：
   - **邮件端**：原生纯粹的 `<Table>` 嵌套模型加上 Inline 极硬约束，完美穿透了各式各样繁杂的老旧 Outlook 等邮箱客户端，呈现出具有高度呼吸感的阅读体验。
   - **Web 服务器**：独立抽出的一套 `FastAPI` 响应式双核本地微服务引擎。电脑端自动开启超 800px 视野的宏大双栏阅读器；手机端侧边栏抽屉更是打通了沉浸阅读体验！
4. **精练筛选与双核退避架构**：主节点无缝对接最前沿的 `Claude Code (Sonnet)` CLI，只要网络不慎崩塌，便会光速级切回本地局域网私有化模型 `Ollama (qwen3.5:9b)` 中，全自动自愈接管。

---

## 🛠️ 全局环境配置包 (Installation)

除了底层抓取必备的 `feedparser` 外，为了支撑上方的图表统计与微型展现服，你需要：

```bash
# 1. 拷贝克隆本套件
# 2. 部署核心所需依赖
pip install -r requirements.txt
pip install fastapi "uvicorn[standard]" jinja2 pandas matplotlib
```

---

## � 触发与驱动 (Usage)

### 1. 强制干预投递
```bash
# 人工生成发送早安版简报
python3 agents/morning_brief/run.py --mode morning

# 人工生成发送暗黑晚间版简报
python3 agents/morning_brief/run.py --mode evening
```
*所有简报运行完毕都将自动以 `Daily_Brief_2026-X.md` 极其强迫症友好的日期目录落回本地磁盘仓库内。*

### 2. 启动本地时光机仪表盘 (Web Dashboard)
如果你想把往昔积攒的历史战报以最高级别的交互方式去查阅，启动以下微型基站：
```bash
python3 -m uvicorn agents.morning_brief.web.main:app --host 127.0.0.1 --port 8000
```
然后直接在任何宿主机访问 `http://127.0.0.1:8000` 进入绝美档案馆！

---

## 🔧 给 Geek 玩家的疑难排解方案 (Troubleshooting)

如果此时的你身处中国大陆并处于长期 TUN (增强模式接管全域网络) 的状态下，务必避开这几个网络毒区：

1. **SMTP 发送 465 SSL 阻断错误 (Curl Error 35)**：
   别冤枉你的 Python 环境！由于 99% 的梯子虚拟服务商（AWS、搬瓦工机房等）底层为了防垃圾营销，他们是在硬件层**物理写死了封杀往返的 `25/465` 邮箱协议端口的**。遇到这种问题，极其建议：改用 国内邮箱账号 (如 QQ 邮箱或者网易)。之后再往你的 Clash 里丢入强制规则 `DOMAIN,smtp.qq.com,DIRECT` 做绝对隔离直连，一秒实现神级避坑！
2. **Git 大规模同步到 GitHub 无故超时 (Push Failed)**：
   切记不要再用 HTTPS 通道输入所谓的 Access Token 密码了，尽早换上 SSH。但在代理劫持的环境里，SSH 自带的端口 22 也会遭到污染！解法也很简单，进入你的 `~/.ssh/config`，手动通过内修方案迫使 Github 走 `443` 通道：
   ```text
   Host github.com
       Hostname ssh.github.com
       Port 443
       User git
   ```

---

> _Automated workflows powered by cutting-edge LLMs / Engineered & Designed by Antigravity_
