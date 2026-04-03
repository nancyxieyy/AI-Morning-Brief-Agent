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
import shutil
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
# 配置区 —— 支持从外部 admin_settings.json 动态加载
# ============================================================
BASE_DIR       = Path(__file__).parent.parent.parent
DAILY_DIR      = BASE_DIR / "Daily"
LOG_DIR        = BASE_DIR / "logs"
CONFIG_PATH    = BASE_DIR / "configs" / "admin_settings.json"

def load_settings():
    """从解耦的配置文件中动态加载运行参数"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 无法加载配置文件: {e}，将使用内置兜底配置。")
        return {
            "subscribers": [
                {"name": "Nancy", "email": "nancysdaily.cc@outlook.com", "timezone": "Asia/Shanghai"},
                {"name": "QaoDarkShit", "email": "572162170@qq.com", "timezone": "Asia/Shanghai"},
                {"name": "Violetta", "email": "violettaweng@gmail.com", "timezone": "Europe/London"}
            ],
            "claude_model": "claude-3-5-sonnet-20241022",
            "ollama_model": "qwen3.5:9b"
        }

SETTINGS = load_settings()

HOURS_LOOKBACK_MORNING = 24                  # 早报：回看24小时
HOURS_LOOKBACK_EVENING = 12                  # 晚报：回看12小时（覆盖下午到晚上）
GITHUB_REPO_DIR = BASE_DIR / "AI-Morning-Brief-Agent"  # Railway 部署用 repo

# 引擎与模型配置
CLAUDE_MODEL   = SETTINGS.get("claude_model", "claude-3-5-sonnet-20241022")
OLLAMA_MODEL   = SETTINGS.get("ollama_model", "qwen3.5:9b")
OLLAMA_API     = "http://localhost:11434/api/generate"

# 邮件配置
GMAIL_USER     = os.environ.get("GMAIL_USER", "eclipsener@gmail.com")
GMAIL_APP_PWD  = os.environ.get("GMAIL_APP_PWD", "")

# 订阅者列表 (动态拉取)
SUBSCRIBERS = SETTINGS.get("subscribers", [])
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


def get_sections() -> list[dict]:
    """从配置中获取版块定义与 RSS 源"""
    return SETTINGS.get("sections", [
        {
            "id": "ai",
            "name": "AI 探索者",
            "is_default_email": True,
            "feeds": [
                {"title": "Simon Willison", "url": "https://simonwillison.net/atom/everything/"},
                {"title": "TechCrunch",     "url": "https://techcrunch.com/feed/"}, # 兜底逻辑
            ]
        }
    ])


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


def build_prompt(articles: list[dict], date_str: str, section_name: str = "AI") -> str:
    articles_json = json.dumps(articles, ensure_ascii=False, indent=2)
    categories = "、".join(["技术突破", "社区热议", "工具推荐", "政策动态", "模型发布", "趋势观察"])
    return f"""你是 Nancy 的私人专属情报官。今天是 {date_str}。
你正在负责【{section_name}】版块的资讯编撰。

以下是从该领域 RSS 订阅源刚抓取的原文信息（JSON）：

{articles_json}

请完成以下任务：
1. 筛选与【{section_name}】高度相关且最具深度的文章
2. 只输出一个标准的 JSON 对象，不要有任何 Markdown 代码块包裹，格式严格如下：

{{
  "summary": "2-3 句话概括该版块今天的全局动态",
  "articles": [
    {{
      "title": "文章标题（中文翻译）",
      "source": "来源名称",
      "published": "发布时间",
      "one_liner": "一句话神总结（中文，15-30字）",
      "link": "原文 URL",
      "category": "从以下标签选一个最贴切的：{categories}"
    }}
  ]
}}

articles 包含 5 篇，按行业权重排序。"""


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


def summarize(articles: list[dict], date_str: str, section_name: str = "AI") -> tuple[str, str]:
    """支持多板块生成的摘要函数"""
    prompt = build_prompt(articles, date_str, section_name)
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

    date_str = datetime.now().strftime("%Y-%m-%d")

    hours_lookback = HOURS_LOOKBACK_EVENING if is_evening else HOURS_LOOKBACK_MORNING
    greeting_emoji = "🌙" if is_evening else "🌅"
    greeting_word  = "晚上好" if is_evening else "早安"
    brief_title    = "今晚 AI 简报" if is_evening else "今日 AI 简报"
    brief_filename = "今晚AI简报.md" if is_evening else "今日AI新闻.md"
    audit_suffix   = "_evening" if is_evening else ""
    LOG_DIR.mkdir(exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  {greeting_emoji} {greeting_word}！生成 {date_str} {brief_title}")
    print(f"{'='*50}\n")

    print("📖 [1/4] 读取 RSS 板块配置...")
    sections = get_sections()
    print(f"       共 {len(sections)} 个内容板块\n")

    all_briefs_data = {} # 存储所有板块的生成结果

    # 循环处理每个板块
    for sec in sections:
        sec_id = sec["id"]
        sec_name = sec["name"]
        print(f"📂 处理板块: 【{sec_name}】...")
        
        # 2/4 抓取
        articles, fetch_stats = fetch_recent_articles(sec["feeds"], hours_lookback)
        total_in = sum(s["included"] for s in fetch_stats)
        
        if total_in == 0:
            print(f"       ⚠️ 板块 {sec_name} 无新内容，跳过。")
            continue
            
        # 3/4 生成
        brief, model_used = summarize(articles, date_str, sec_name)
        all_briefs_data[sec_id] = brief
        
        # 4/4 保存（中文命名，可读性更好）
        _names = {
            "ai":   ("今日AI新闻.md",   "今晚AI简报.md"),
            "tech": ("今日科技热点.md", "今晚科技热点.md"),
            "econ": ("今日经济简报.md", "今晚经济简报.md"),
        }
        filename = _names.get(sec_id, (f"{sec_id}.md", f"{sec_id}_Evening.md"))[1 if is_evening else 0]
        _, md_content, parse_path = parse_markdown_to_html(brief, date_str, "Nancy", args.mode)
        save_brief(md_content, date_str, filename)
        
        # 如果是默认推送板块（AI），则执行邮件发送
        if sec.get("is_default_email", False):
            print(f"📧 [Email] 正在推送默认板块 【{sec_name}】...")
            email_results = []
            for sub in SUBSCRIBERS:
                sub_greeting = greeting_for_timezone(sub.get("timezone", "Asia/Shanghai"))
                html_content, _, _ = parse_markdown_to_html(brief, date_str, sub["name"], args.mode, sub_greeting)
                result = send_email(html_content, date_str, sub["email"], f"【{sec_name}】{brief_title} {date_str}")
                result["name"]  = sub["name"]
                result["email"] = sub["email"]
                email_results.append(result)
            
            # 审计日志
            write_audit_log(date_str, fetch_stats, model_used, parse_path, len(articles), email_results,
                            hours_lookback, f"{audit_suffix}_{sec_id}")

    print(f"\n✨ 完成全板块分发与归档！\n")
    # 同步整个目录
    sync_all_to_github(date_str, args.mode)


def sync_all_to_github(date_str: str, mode: str) -> None:
    """同步整个当日文件夹到 GitHub"""
    if not GITHUB_REPO_DIR.exists(): return
    
    src_folder = DAILY_DIR / date_str
    dst_folder = GITHUB_REPO_DIR / "Daily" / date_str
    if dst_folder.exists(): shutil.rmtree(dst_folder)
    shutil.copytree(src_folder, dst_folder)
    
    brief_label = "多板块更新"
    commit_msg = f"brief: {date_str} {brief_label}"
    
    try:
        subprocess.run(["git", "add", "."], cwd=GITHUB_REPO_DIR, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=GITHUB_REPO_DIR, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=GITHUB_REPO_DIR, capture_output=True, timeout=30)
        print("  ✅ GitHub 全量同步完成")
    except Exception as e:
        print(f"  ⚠️ GitHub 同步失败: {e}")


def sync_to_github(date_str: str, filename: str, mode: str) -> None:
    """把当日简报同步到 GitHub repo，触发 Railway 自动更新网页版"""
    if not GITHUB_REPO_DIR.exists():
        print("  ⚠️  AI-Morning-Brief-Agent 目录不存在，跳过 GitHub 同步")
        return

    # 复制简报文件到 GitHub repo 的 Daily/ 目录
    src = DAILY_DIR / date_str / filename
    dst_dir = GITHUB_REPO_DIR / "Daily" / date_str
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / filename)

    brief_label = "晚报" if mode == "evening" else "早报"
    commit_msg = f"brief: {date_str} {brief_label}"

    print(f"  🚀 同步到 GitHub ({brief_label})...")
    try:
        subprocess.run(
            ["git", "add", f"Daily/{date_str}/"],
            cwd=GITHUB_REPO_DIR, check=True, capture_output=True
        )
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=GITHUB_REPO_DIR, capture_output=True
        )
        if result.returncode == 0:
            print("  ℹ️  无新内容，跳过 commit")
            return
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=GITHUB_REPO_DIR, check=True, capture_output=True
        )
        push = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=GITHUB_REPO_DIR, capture_output=True, text=True, timeout=30
        )
        if push.returncode == 0:
            print("  ✅ GitHub 同步成功，Railway 将自动刷新")
        else:
            print(f"  ⚠️  push 失败（不影响邮件）: {push.stderr[:120]}")
    except Exception as e:
        print(f"  ⚠️  GitHub 同步失败（不影响邮件）: {e}")


if __name__ == "__main__":
    main()
