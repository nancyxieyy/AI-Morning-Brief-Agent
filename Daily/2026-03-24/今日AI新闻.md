# 🤖 早安，Nancy！今日 AI 简报 · 2026-03-24

## 📌 今日摘要
今天最值得关注的是"流式专家"技术的进展——一种让超大 MoE 模型在显存不足的硬件上运行的新思路，正在重塑本地推理的边界。与此同时，Simon Willison 持续用 Claude Skills 探索开发者工作流，LLM 从零训练系列也更新了权重衰减实验。AI 输出质量（"slop"）的社区讨论也在发酵，值得关注。

---

## 🔥 重点文章（7 篇）

### Streaming Experts：让大模型在显存不够的硬件上跑起来
- **来源**：simonwillison.net　**时间**：2026-03-24 05:09
- **一句话**：通过从 SSD 按需流式加载 MoE 模型的专家权重，可在显存不足的设备上运行超大模型，是本地推理的重要突破方向。
- 🔗 https://simonwillison.net/2026/Mar/24/streaming-experts/#atom-everything

### 用 Claude Skills 探索 Starlette 1.0
- **来源**：simonwillison.net　**时间**：2026-03-22 23:57
- **一句话**：Starlette 1.0 正式发布，Simon 借助 Claude Skills 快速上手这个 FastAPI 底层框架，展示了 AI 辅助学习新技术的实际效果。
- 🔗 https://simonwillison.net/2026/Mar/22/starlette/#atom-everything

### 从零写 LLM 第 32f 章：权重衰减干预实验
- **来源**：gilesthomas.com　**时间**：2026-03-23 23:55
- **一句话**：作者基于 Sebastian Raschka 的书，持续优化从零训练的 GPT-2 Small，本期深入拆解权重衰减对测试损失的影响。
- 🔗 https://www.gilesthomas.com/2026/03/llm-from-scratch-32f-interventions-weight-decay

### "Slop"的本质：消费比生产更费力的内容
- **来源**：simonwillison.net　**时间**：2026-03-23 23:31
- **一句话**：一句话击中要害——"Slop 是消耗读者时间比生成它所花时间更多的内容"，直接点出 AI 滥用对协作文化的伤害。
- 🔗 https://simonwillison.net/2026/Mar/23/neurotica/#atom-everything

### JavaScript 沙箱研究：Claude Code 探索 Node.js Worker Threads
- **来源**：simonwillison.net　**时间**：2026-03-22 19:53
- **一句话**：Simon 让 Claude Code 研究 Node.js Worker Threads 能否用于 JavaScript 沙箱执行，是 AI 辅助安全研究的典型示范。
- 🔗 https://simonwillison.net/2026/Mar/22/javascript-sandboxing-research/#atom-everything

### The Illusionist and the Conjurer：AI 魔术师的哲学
- **来源**：worksonmymachine.substack.com　**时间**：2026-03-24 13:16
- **一句话**：以 Penn & Teller 的魔术哲学为引，探讨 AI 系统中"透明表演"与"真实能力"之间的张力，是一篇值得细读的思辨文章。
- 🔗 https://worksonmymachine.ai/p/the-illusionist-and-the-conjurer

### Troy Hunt 周报 496：OpenClaw 与 Agentic AI 的早期飞行时刻
- **来源**：troyhunt.com　**时间**：2026-03-24 04:17
- **一句话**：Troy Hunt 将 Agentic AI 的现状比作莱特兄弟的第一次飞行——粗糙、胶带拼凑，但潜力肉眼可见。
- 🔗 https://www.troyhunt.com/weekly-update-496/

---

## 🗂️ 其他相关文章

- **Quoting David Abram：机器没有夺走你的手艺** · simonwillison.net · https://simonwillison.net/2026/Mar/23/david-abram/#atom-everything
- **Starlette 1.0 Skill 研究文档** · simonwillison.net · https://simonwillison.net/2026/Mar/23/starlette-1-skill/#atom-everything
- **npx workos：Claude 驱动的 Auth 集成 AI Agent（赞助）** · daringfireball.net · https://workos.com/docs/authkit/cli-installer?utm_source=daringfireball&utm_medium=newsletter&utm_campaign=q12026