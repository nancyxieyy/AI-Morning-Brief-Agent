#!/usr/bin/env python3
"""
早安 AI 简报 Agent
- 主力：claude -p（使用 Pro 订阅，免费）
- 备用：Ollama qwen3.5:9b（本地，离线可用）
- 推送：Gmail SMTP → 订阅者列表
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import feedparser
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from html_renderer import parse_markdown_to_html

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
try:
    from agents.utils.telemetry import TokenMonitor
except ImportError:
    TokenMonitor = None

# ============================================================
# 配置区 —— 只需修改这里
# ============================================================
BASE_DIR       = Path(__file__).parent.parent.parent
DAILY_DIR      = BASE_DIR / "Daily"
LOG_DIR        = BASE_DIR / "logs"

HOURS_LOOKBACK_MORNING = 24                  # 早报：回看24小时
HOURS_LOOKBACK_EVENING = 12                  # 晚报：回看12小时（覆盖下午到晚上）
OLLAMA_MODEL   = "qwen3.5:9b"               # 备用本地模型
OLLAMA_API     = "http://localhost:11434/api/generate"

# 邮件配置（从环境变量读取，本地用 launchd plist 注入）
GMAIL_USER     = os.environ.get("GMAIL_USER", "eclipsener@gmail.com")
GMAIL_APP_PWD  = os.environ.get("GMAIL_APP_PWD", "")

# 订阅者列表
SUBSCRIBERS = [
    {"name": "Nancy",       "email": "nancysdaily.cc@outlook.com", "timezone": "Asia/Shanghai"},
    {"name": "QaoDarkShit", "email": "572162170@qq.com",           "timezone": "Asia/Shanghai"},
    {"name": "Violetta",    "email": "violettaweng@gmail.com",     "timezone": "Europe/London"},
]
# ============================================================


def greeting_for_timezone(tz_name: str) -> str:
    """根据订阅者所在时区的当前本地时间，返回合适的问候语。"""
    hour = datetime.now(ZoneInfo(tz_name)).hour
    if 6 <= hour < 12:
        return "☀️ 早上好"
    elif 12 <= hour < 18:
        return "🌤️ 下午好"
    elif 18 <= hour < 23:
        return "🌙 晚上好"
    else:
        return "🌃 深夜好"


def get_feeds() -> list[dict]:
    """返回指定的 RSS 订阅源列表"""
    return [
        {"title": "Simon Willison", "url": "https://simonwillison.net/atom/everything/"},
        {"title": "TechCrunch",     "url": "https://techcrunch.com/feed/"},
        {"title": "The Verge",      "url": "https://www.theverge.com/rss/index.xml"},
        {"title": "minimaxir",      "url": "https://minimaxir.com/index.xml"},
    ]


def fetch_recent_articles(feeds: list[dict], hours: int) -> tuple[list[dict], list[dict]]:
    """
    抓取所有 Feed，返回 (articles, fetch_stats)
    fetch_stats: 每个源的 {source, fetched, filtered_old, included, error}
    """
    cutoff   = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []
    fetch_stats = []

    for feed_info in feeds:
        stat = {
            "source":       feed_info["title"],
            "fetched":      0,
            "filtered_old": 0,
            "included":     0,
            "error":        None,
        }
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:10]:
                stat["fetched"] += 1
                pub = None
                for attr in ("published_parsed", "updated_parsed"):
                    t = getattr(entry, attr, None)
                    if t:
                        pub = datetime(*t[:6], tzinfo=timezone.utc)
                        break

                if pub and pub < cutoff:
                    stat["filtered_old"] += 1
                    continue

                stat["included"] += 1
                articles.append({
                    "source":    feed_info["title"],
                    "title":     entry.get("title", "").strip(),
                    "link":      entry.get("link", ""),
                    "summary":   entry.get("summary", "")[:400],
                    "published": pub.strftime("%Y-%m-%d %H:%M") if pub else "unknown",
                })
        except Exception as e:
            stat["error"] = str(e)
            print(f"  ⚠️  抓取失败: {feed_info['title']} — {e}")

        fetch_stats.append(stat)

    return articles, fetch_stats


def build_prompt(articles: list[dict], date_str: str) -> str:
    articles_json = json.dumps(articles, ensure_ascii=False, indent=2)
    categories = "、".join(["技术突破", "社区热议", "工具推荐", "政策动态", "模型发布"])
    return f"""你是 Nancy 的私人 AI 新闻编辑。今天是 {date_str}。

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


CLAUDE_BIN = "/Users/nancyxie/.local/bin/claude"   # claude CLI 完整路径


def summarize_with_claude_cli(prompt: str) -> str:
    """方案①：调用 claude -p，使用 Pro 订阅"""
    print("  🤖 使用 Claude Code CLI（Pro 订阅）...")
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


def summarize(articles: list[dict], date_str: str) -> tuple[str, str]:
    """
    先尝试 Claude CLI，失败则回退到 Ollama。
    返回 (brief_text, model_used)，model_used: "claude_cli" | "ollama"
    """
    prompt = build_prompt(articles, date_str)
    t0 = time.time()
    monitor = TokenMonitor(LOG_DIR) if TokenMonitor else None
    
    try:
        text = summarize_with_claude_cli(prompt)
        duration = time.time() - t0
        if monitor:
            monitor.record_usage("morning_brief", "claude_cli", prompt, text, duration)
        return text, "claude_cli"
    except Exception as e:
        duration = time.time() - t0
        if monitor:
             monitor.record_usage("morning_brief", "claude_cli", prompt, "", duration, error=str(e))
        print(f"  ⚠️  Claude CLI 失败（{e}），切换到 Ollama...")
        
        t1 = time.time()
        try:
            text = summarize_with_ollama(prompt)
            duration2 = time.time() - t1
            if monitor:
                monitor.record_usage("morning_brief", "ollama", prompt, text, duration2)
            return text, "ollama"
        except Exception as e2:
            duration2 = time.time() - t1
            if monitor:
                monitor.record_usage("morning_brief", "ollama", prompt, "", duration2, error=str(e2))
            raise e2


def save_brief(content: str, date_str: str, filename: str = "今日AI新闻.md") -> Path:
    """创建 Daily/YYYY-MM-DD/ 并写入简报文件"""
    folder   = DAILY_DIR / date_str
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"  ✅ 简报已保存: {filepath}")
    return filepath


def send_email(html_content: str, date_str: str, to_email: str, subject: str = None) -> dict:
    """
    通过 curl + Gmail SMTP 发送 HTML 邮件。
    返回 {"success": bool, "elapsed": float, "retries": int, "error": str|None}
    """
    if not GMAIL_APP_PWD:
        print("  ⚠️  Gmail 应用密码未配置，跳过邮件发送")
        return {"success": False, "elapsed": 0.0, "retries": 0, "error": "未配置密码"}

    t_start = time.time()
    retries = 0

    subject_b64 = base64.b64encode((subject or f'今日 AI 简报 {date_str}').encode()).decode()
    body_b64    = base64.b64encode(html_content.encode('utf-8')).decode()

    email_body = (
        f"From: {GMAIL_USER}\r\n"
        f"To: {to_email}\r\n"
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

    with tempfile.NamedTemporaryFile(mode='w', suffix='.netrc',
                                     delete=False, encoding='ascii') as f:
        f.write(f"machine smtp.gmail.com\nlogin {GMAIL_USER}\npassword {GMAIL_APP_PWD}\n")
        tmp_netrc = f.name

    cmd = [
        "/usr/bin/curl", "-s",
        "--url",         "smtps://smtp.gmail.com:465",
        "--ssl-reqd",
        "--netrc-file",  tmp_netrc,
        "--mail-from",   GMAIL_USER,
        "--mail-rcpt",   to_email,
        "--upload-file", tmp_eml,
    ]

    last_error = None
    try:
        for attempt in range(1, 4):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    elapsed = time.time() - t_start
                    print(f"  ✅ 邮件已发送至 {to_email}（{elapsed:.1f}s）")
                    return {"success": True, "elapsed": elapsed, "retries": retries, "error": None}
                else:
                    retries += 1
                    last_error = result.stderr.strip() or result.stdout.strip()
                    if attempt < 3:
                        print(f"  ⚠️  第 {attempt} 次失败 (code={result.returncode})，5秒后重试...")
                        time.sleep(5)
                    else:
                        print(f"  ❌ 邮件发送失败 (code={result.returncode}): {last_error}")
            except Exception as e:
                retries += 1
                last_error = str(e)
                if attempt < 3:
                    print(f"  ⚠️  第 {attempt} 次失败 ({e})，5秒后重试...")
                    time.sleep(5)
                else:
                    print(f"  ❌ 邮件发送失败: {e}")
    finally:
        Path(tmp_eml).unlink(missing_ok=True)
        Path(tmp_netrc).unlink(missing_ok=True)

    return {"success": False, "elapsed": time.time() - t_start, "retries": retries, "error": last_error}


def send_alert(subject: str, body: str) -> None:
    """发送纯文本告警邮件给 Nancy（不发给其他订阅者）"""
    if not GMAIL_APP_PWD:
        return
    owner_email = SUBSCRIBERS[0]["email"]
    subject_b64 = base64.b64encode(f'[NancysDaily 告警] {subject}'.encode()).decode()
    body_b64    = base64.b64encode(body.encode('utf-8')).decode()
    email_body = (
        f"From: {GMAIL_USER}\r\n"
        f"To: {owner_email}\r\n"
        f"Subject: =?utf-8?b?{subject_b64}?=\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Transfer-Encoding: base64\r\n"
        f"\r\n"
        f"{body_b64}\r\n"
    )
    with tempfile.NamedTemporaryFile(mode='w', suffix='.eml', delete=False, encoding='ascii') as f:
        f.write(email_body)
        tmp_eml = f.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.netrc', delete=False, encoding='ascii') as f:
        f.write(f"machine smtp.gmail.com\nlogin {GMAIL_USER}\npassword {GMAIL_APP_PWD}\n")
        tmp_netrc = f.name
    try:
        subprocess.run([
            "/usr/bin/curl", "-s",
            "--url", "smtps://smtp.gmail.com:465", "--ssl-reqd",
            "--netrc-file", tmp_netrc,
            "--mail-from", GMAIL_USER, "--mail-rcpt", owner_email,
            "--upload-file", tmp_eml,
        ], capture_output=True, timeout=30)
        print(f"  📨 告警邮件已发送至 {owner_email}")
    except Exception as e:
        print(f"  ⚠️  告警邮件发送失败: {e}")
    finally:
        Path(tmp_eml).unlink(missing_ok=True)
        Path(tmp_netrc).unlink(missing_ok=True)


# ── 解析路径的可读标签 ──────────────────────────────────────
_PARSE_PATH_LABELS = {
    "json_direct":   "json_direct ✅  直接解析成功",
    "json_repaired": "json_repaired ⚠️  含非法引号，已自动修复",
    "fallback":      "fallback ❌  JSON解析失败，使用Markdown兜底",
}


def write_audit_log(date_str: str, fetch_stats: list, model_used: str,
                    parse_path: str, article_count: int, email_results: list,
                    hours_lookback: int = 24, audit_suffix: str = "") -> None:
    """每日运行后写一份审计日志到 logs/audit_YYYY-MM-DD[_evening].md"""

    total_fetched  = sum(s["fetched"]      for s in fetch_stats)
    total_filtered = sum(s["filtered_old"] for s in fetch_stats)
    total_included = sum(s["included"]     for s in fetch_stats)

    lines = [
        f"# 审计日志 · {date_str}{audit_suffix}",
        f"> 生成时间：{datetime.now().strftime('%H:%M:%S')}",
        "",
        "## [1] 抓取阶段",
    ]
    for s in fetch_stats:
        status = f"❌ 错误：{s['error']}" if s["error"] else "✅"
        lines.append(
            f"- {s['source']:<20} 抓取 {s['fetched']} 篇，"
            f"过滤 {s['filtered_old']} 篇（超过{hours_lookback}h），"
            f"入库 {s['included']} 篇  {status}"
        )
    lines.append(
        f"- **合计：入库 {total_included} 篇**"
        f"（共抓取 {total_fetched} 篇，过滤 {total_filtered} 篇）"
    )

    model_label = "Claude CLI ✅" if model_used == "claude_cli" else "Ollama ⚠️（Claude CLI 失败，已切换）"
    lines += [
        "",
        "## [2] 生成阶段",
        f"- 模型：{model_label}",
        f"- 解析路径：{_PARSE_PATH_LABELS.get(parse_path, parse_path)}",
        f"- 输出文章数：{article_count} 篇",
        "",
        "## [3] 分发阶段",
    ]
    for r in email_results:
        status    = "✅ 成功" if r["success"] else "❌ 失败"
        retry_str = f"重试 {r['retries']} 次" if r["retries"] > 0 else "无重试"
        error_str = f"  → {r['error']}" if r.get("error") else ""
        lines.append(
            f"- {r['name']:<12} | {r['email']:<36} | "
            f"{status} | 耗时 {r['elapsed']:.1f}s | {retry_str}{error_str}"
        )
    success_count = sum(1 for r in email_results if r["success"])
    lines.append(f"- **合计：{success_count}/{len(email_results)} 发送成功**")

    audit_path = LOG_DIR / f"audit_{date_str}{audit_suffix}.md"
    audit_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  📋 审计日志已保存: {audit_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["morning", "evening"], default="morning")
    args = parser.parse_args()
    is_evening = args.mode == "evening"

    hours_lookback = HOURS_LOOKBACK_EVENING if is_evening else HOURS_LOOKBACK_MORNING
    greeting_emoji = "🌙" if is_evening else "🌅"
    greeting_word  = "晚上好" if is_evening else "早安"
    brief_title    = "Evening Brief" if is_evening else "Daily Brief"
    brief_filename = f"Evening_Brief_{date_str}.md" if is_evening else f"Daily_Brief_{date_str}.md"
    audit_suffix   = "_evening" if is_evening else ""

    date_str = datetime.now().strftime("%Y-%m-%d")
    LOG_DIR.mkdir(exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  {greeting_emoji} {greeting_word}！生成 {date_str} {brief_title}")
    print(f"{'='*50}\n")

    print("📖 [1/4] 读取 RSS 订阅源...")
    feeds = get_feeds()
    print(f"       共 {len(feeds)} 个订阅源\n")

    print(f"📡 [2/4] 抓取最近 {hours_lookback}h 的文章...")
    articles, fetch_stats = fetch_recent_articles(feeds, hours_lookback)
    total_in = sum(s["included"] for s in fetch_stats)
    print(f"       共抓取 {sum(s['fetched'] for s in fetch_stats)} 篇，入库 {total_in} 篇\n")

    # 缓存本次输入载荷，供 save_case.py 半自动反思库调取
    with open(LOG_DIR / "last_run_articles.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    if total_in == 0:
        msg = (
            f"日期：{date_str}\n"
            f"所有 {len(feeds)} 个 RSS 源均未抓取到有效文章（可能是网络问题或源结构变化）。\n\n"
            + "\n".join(
                f"- {s['source']}: 抓取 {s['fetched']} 篇，过滤 {s['filtered_old']} 篇"
                + (f"，错误：{s['error']}" if s['error'] else "")
                for s in fetch_stats
            )
        )
        print(f"  ❌ 0 篇文章入库，终止生成，发送告警...\n")
        send_alert(f"{date_str} 抓取失败，0 篇文章", msg)
        audit_path = LOG_DIR / f"audit_{date_str}{audit_suffix}.md"
        audit_path.write_text(
            f"# 审计日志 · {date_str}{audit_suffix}\n> ❌ 抓取 0 篇，流程终止\n\n" + msg,
            encoding="utf-8"
        )
        sys.exit(1)

    print("🤖 [3/4] 生成简报...")
    brief, model_used = summarize(articles, date_str)
    print("       简报生成完毕\n")

    print("💾 [4/4] 保存 & 批量分发...")

    # 解析一次获取 md + parse_path；后续订阅者复用同一 brief
    _, md_content, parse_path = parse_markdown_to_html(brief, date_str, "Nancy", args.mode)
    save_brief(md_content, date_str, brief_filename)

    # 获取最终输出文章数
    try:
        start = brief.find('{')
        article_count = len(json.loads(brief[start:]).get("articles", [])) if start >= 0 else 0
    except Exception:
        article_count = md_content.count("### ")

    email_results = []
    for sub in SUBSCRIBERS:
        sub_greeting = greeting_for_timezone(sub.get("timezone", "Asia/Shanghai"))
        html_content, _, _ = parse_markdown_to_html(brief, date_str, sub["name"], args.mode, sub_greeting)
        result = send_email(html_content, date_str, sub["email"], f"{brief_title} {date_str}")
        result["name"]  = sub["name"]
        result["email"] = sub["email"]
        email_results.append(result)

    write_audit_log(date_str, fetch_stats, model_used, parse_path, article_count, email_results,
                    hours_lookback, audit_suffix)

    success_count = sum(1 for r in email_results if r["success"])
    print(f"\n✨ 完成分发 ({success_count}/{len(SUBSCRIBERS)} 发送成功)！\n")


if __name__ == "__main__":
    main()
