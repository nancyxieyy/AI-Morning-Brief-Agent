#!/usr/bin/env python3
"""
早安 AI 简报 Agent
- 主力：Claude 命令行调用（例如基于 Claude Code/CLI）
- 备用：Ollama qwen3.5:9b（本地，离线可用）
- 推送：Gmail HTML 美化邮件直推
"""

import json
import subprocess
import sys
import urllib.request
import feedparser
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 确保直接调用时也能找到同目录的 html_renderer
sys.path.insert(0, str(Path(__file__).parent))
from html_renderer import parse_markdown_to_html

# ============================================================
# 配置区 —— 只需修改这里
# ============================================================
BASE_DIR       = Path(__file__).parent
DAILY_DIR      = BASE_DIR / "Daily"
LOG_DIR        = BASE_DIR / "logs"

HOURS_LOOKBACK = 48                          # 抓取多少小时内的文章
OLLAMA_MODEL   = "qwen3.5:9b"                # 备用本地模型
OLLAMA_API     = "http://localhost:11434/api/generate"

# 邮件配置
GMAIL_USER     = "xxxxx@gmail.com"           # 你的 Gmail 地址
GMAIL_APP_PWD  = "xxxxxxxxxxxxxxxx"          # Gmail 应用专用密码 (16位)
EMAIL_TO       = "xxxxx@example.com"         # 接收简报的目标邮箱
# ============================================================


def get_feeds() -> list[dict]:
    """返回 RSS 订阅源列表（优先读取 data/ 下的 OPML 导入文件，否则使用备用名单）"""
    import xml.etree.ElementTree as ET
    feeds = []
    
    opml_path = BASE_DIR / "data" / "hn-popular-blogs-2025.opml"
    if opml_path.exists():
        try:
            tree = ET.parse(opml_path)
            for outline in tree.iter("outline"):
                xml_url = outline.get("xmlUrl")
                if xml_url:
                    feeds.append({
                        "title": outline.get("title") or outline.get("text", "Unknown Blog"), 
                        "url": xml_url
                    })
            if feeds:
                return feeds
        except Exception as e:
            print(f"  ⚠️  解析 OPML 列表文件失败: {e}，即将使用备用数据源...")

    # 备用默认聚合列表
    return [
        {"title": "Simon Willison", "url": "https://simonwillison.net/atom/everything/"},
        {"title": "TechCrunch",     "url": "https://techcrunch.com/feed/"},
        {"title": "The Verge",      "url": "https://www.theverge.com/rss/index.xml"},
        {"title": "minimaxir",      "url": "https://minimaxir.com/index.xml"},
    ]


def fetch_recent_articles(feeds: list[dict], hours: int) -> list[dict]:
    """抓取所有 Feed，返回最近 N 小时的文章"""
    cutoff   = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for feed_info in feeds:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:10]:
                pub = None
                for attr in ("published_parsed", "updated_parsed"):
                    t = getattr(entry, attr, None)
                    if t:
                        pub = datetime(*t[:6], tzinfo=timezone.utc)
                        break

                if pub and pub < cutoff:
                    continue

                articles.append({
                    "source":    feed_info["title"],
                    "title":     entry.get("title", "").strip(),
                    "link":      entry.get("link", ""),
                    "summary":   entry.get("summary", "")[:400],
                    "published": pub.strftime("%Y-%m-%d %H:%M") if pub else "unknown",
                })
        except Exception as e:
            print(f"  ⚠️  抓取失败: {feed_info['title']} — {e}")

    return articles


def build_prompt(articles: list[dict], date_str: str) -> str:
    articles_json = json.dumps(articles, ensure_ascii=False, indent=2)
    categories = "、".join(["技术突破", "社区热议", "工具推荐", "政策动态", "模型发布"])
    return f"""你是我的私人 AI 新闻编辑。今天是 {date_str}。

以下是从 RSS 订阅源刚抓取的文章（JSON）：

{articles_json}

请完成以下任务：
1. 筛选与 AI、LLM、机器学习、AI 工具/产品/政策 相关的文章
2. 若 AI 文章不足 5 篇，可补充有价值的技术/科技文章
3. 只输出一个 JSON 对象，不要有任何其他文字、标题或代码块标记，格式严格如下：

{{
  "summary": "2-3 句话概括今天最值得关注的动态",
  "articles": [
    {{
      "title": "文章标题（中文翻译或原标题）",
      "source": "来源名称",
      "published": "发布时间，如 2024-01-01 08:00",
      "one_liner": "一句话摘要（中文，15-30字）",
      "link": "原文 URL",
      "category": "从以下选一个：{categories}"
    }}
  ]
}}

articles 包含 5-8 篇，按重要性排序。"""


CLAUDE_BIN = "claude"   # 例如通过 claude code 调用。不在环境变量时应写全路径如 "/Users/xxx/.local/bin/claude"


def summarize_with_claude_cli(prompt: str) -> str:
    """方案①：调用本地部署的 claude cli 核心引擎"""
    print("  🤖 调用 Claude CLI (Pro订阅引擎)...")
    result = subprocess.run(
        [CLAUDE_BIN, "-p", "--dangerously-skip-permissions"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI 错误: {result.stderr[:200]}")
    return result.stdout.strip()


def summarize_with_ollama(prompt: str) -> str:
    """方案②：调用本地 Ollama（备用，需要 Ollama 服务运行中）"""
    print(f"  🦙 使用 Ollama {OLLAMA_MODEL}（本地备用）...")

    # 先检查 Ollama 是否在运行
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=3)
    except Exception:
        raise RuntimeError("Ollama 服务未运行，无法使用备用方案")

    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_API,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())
    return result.get("response", "").strip()


def summarize(articles: list[dict], date_str: str) -> str:
    """先尝试 Claude CLI，失败则回退到 Ollama"""
    prompt = build_prompt(articles, date_str)
    try:
        return summarize_with_claude_cli(prompt)
    except Exception as e:
        print(f"  ⚠️  Claude CLI 失败（{e}），切换到 Ollama...")
        return summarize_with_ollama(prompt)


def save_brief(content: str, date_str: str) -> Path:
    """创建 Daily/YYYY-MM-DD/ 并写入 今日AI新闻.md"""
    folder   = DAILY_DIR / date_str
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / "今日AI新闻.md"
    filepath.write_text(content, encoding="utf-8")
    print(f"  ✅ 简报已保存: {filepath}")
    return filepath


def send_email(html_content: str, date_str: str) -> None:
    """通过 curl + Gmail SMTP 发送高度兼容的 HTML 排版邮件"""
    if not GMAIL_APP_PWD or GMAIL_APP_PWD == "xxxxxxxxxxxxxxxx":
        print("  ⚠️  Gmail 应用密码未配置，跳过邮件发送")
        return

    import tempfile
    import base64
    subject_b64 = base64.b64encode(f'今日 AI 简报 {date_str}'.encode()).decode()
    body_b64 = base64.b64encode(html_content.encode('utf-8')).decode()

    # 构建标准 RFC 2822 的 base64-encoded body
    email_body = (
        f"From: {GMAIL_USER}\r\n"
        f"To: {EMAIL_TO}\r\n"
        f"Subject: =?utf-8?b?{subject_b64}?=\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Transfer-Encoding: base64\r\n"
        f"\r\n"
        f"{body_b64}\r\n"
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.eml',
                                     delete=False, encoding='ascii') as f:
        f.write(email_body)
        tmp_eml = f.name

    # 用 .netrc 文件传密码，避免命令行参数被记录
    with tempfile.NamedTemporaryFile(mode='w', suffix='.netrc',
                                     delete=False, encoding='ascii') as f:
        f.write(f"machine smtp.gmail.com\nlogin {GMAIL_USER}\npassword {GMAIL_APP_PWD}\n")
        tmp_netrc = f.name

    try:
        result = subprocess.run([
            "curl", "-s",
            "--url",         "smtps://smtp.gmail.com:465",
            "--ssl-reqd",
            "--netrc-file",  tmp_netrc,
            "--mail-from",   GMAIL_USER,
            "--mail-rcpt",   EMAIL_TO,
            "--upload-file", tmp_eml,
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print(f"  ✅ 邮件已发送至 {EMAIL_TO}")
        else:
            print(f"  ❌ 邮件发送失败 (code={result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    except Exception as e:
        print(f"  ❌ 邮件发送失败: {e}")
    finally:
        Path(tmp_eml).unlink(missing_ok=True)
        Path(tmp_netrc).unlink(missing_ok=True)


def main() -> None:
    date_str = datetime.now().strftime("%Y-%m-%d")
    LOG_DIR.mkdir(exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  🌅 早安！生成 {date_str} AI 简报")
    print(f"{'='*50}\n")

    print("📖 [1/4] 读取 RSS 订阅源...")
    feeds = get_feeds()
    print(f"       共 {len(feeds)} 个订阅源\n")

    print(f"📡 [2/4] 抓取最近 {HOURS_LOOKBACK}h 的文章...")
    articles = fetch_recent_articles(feeds, HOURS_LOOKBACK)
    print(f"       共抓取 {len(articles)} 篇文章\n")

    print("🤖 [3/4] 生成简报...")
    brief = summarize(articles, date_str)
    print("       简报生成完毕\n")

    print("💾 [4/4] 注入模板 & 发送邮件...")
    # 使用 html_renderer 自动解析模型输出的 JSON 格式
    html_content, md_content = parse_markdown_to_html(brief, date_str)
    
    # 存为 markdown 和 发送 高颜值 HTML
    save_brief(md_content, date_str)
    send_email(html_content, date_str)

    print(f"\n✨ 完成！\n")


if __name__ == "__main__":
    main()
