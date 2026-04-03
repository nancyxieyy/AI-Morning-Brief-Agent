import json
import re
import os
from datetime import datetime

# 分类标签样式映射（Claude 输出 category 字段时使用）
CATEGORY_STYLES = {
    "技术突破": {"bg": "#E8F0EA", "color": "#2D5D3B"},
    "社区热议": {"bg": "#FFF0E6", "color": "#A44200"},
    "工具推荐": {"bg": "#EAF2FA", "color": "#2C5E8A"},
    "政策动态": {"bg": "#F3EEFF", "color": "#5B2D8A"},
    "模型发布": {"bg": "#FFF5E0", "color": "#8A5A00"},
}
_DEFAULT_TAG = {"bg": "#E8F0EA", "color": "#2D5D3B", "text": "重点关注"}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>今日 AI 简报</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F7F5F2; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table width="100%" bgcolor="#F7F5F2" cellpadding="0" cellspacing="0" border="0" style="padding: 40px 10px;">
    <tr>
      <td align="center">
        <table align="center" width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #FFFFFF; max-width: 600px; width: 100%;">

          <!-- 头部：问候与摘要 -->
          <tr>
            <td style="padding: 30px 40px; background-color: #FFFFFF; border-bottom: 1px solid #E6E2DE;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-bottom: 10px;">
                    <h1 style="margin: 0; font-size: 24px; color: #2A2827; font-weight: 600;">{greeting_text}，{subscriber_name}</h1>
                  </td>
                </tr>
                <tr>
                  <td style="padding-bottom: 25px;">
                    <p style="margin: 0; font-size: 15px; color: #736B66; line-height: 1.6;">{summary_text}</p>
                  </td>
                </tr>
                <!-- 装饰进度条：表示今日简报已就绪 -->
                <tr>
                  <td>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="100%" style="background-color: #E6E2DE; height: 6px;">
                          <table width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr><td style="background-color: #D96D49; height: 6px;"></td></tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 文章流 -->
          <tr>
            <td style="padding: 20px 40px 30px 40px; background-color: #FDFCFB;">
              {articles_html}
            </td>
          </tr>

          {feedback_section}

          <!-- 页脚 -->
          <tr>
            <td style="padding: 24px 40px; background-color: #F7F5F2; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #A09893; line-height: 1.6;">Automated by Claude Code &middot; Designed by Antigravity</p>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #C0B8B3;">{date_str}</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

ARTICLE_TEMPLATE = """<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 20px;">
  <tr>
    <td style="padding-bottom: 10px;">
      <span style="display: inline-block; background-color: {tag_bg}; color: {tag_color}; font-size: 12px; font-weight: 600; padding: 4px 10px; margin-right: 8px;">{tag_text}</span>
      <span style="display: inline-block; color: #A09893; font-size: 12px;">{source_time}</span>
    </td>
  </tr>
  <tr>
    <td style="padding-bottom: 6px;">
      <a href="{link}" target="_blank" style="text-decoration: none; color: #2A2827; font-size: 18px; font-weight: 600; line-height: 1.4;">{title}</a>
    </td>
  </tr>
  <tr>
    <td style="padding-bottom: 16px; border-bottom: 1px dashed #E6E2DE;">
      <p style="margin: 0; font-size: 14px; color: #736B66; line-height: 1.6;">{desc}</p>
    </td>
  </tr>
</table>"""


def _render_from_dict(data: dict, date_str: str, subscriber_name: str, greeting_text: str) -> str:
    """从已解析的 JSON dict 渲染完整 HTML 邮件。"""
    summary = data.get("summary", "这是你的专属 AI 简报。").replace("\n", "<br/>")
    articles = data.get("articles", [])

    articles_html = ""
    for art in articles:
        category = art.get("category", "")
        style = CATEGORY_STYLES.get(category, _DEFAULT_TAG)
        tag_text = category if category in CATEGORY_STYLES else _DEFAULT_TAG["text"]

        source = art.get("source", "")
        published = art.get("published", "")
        source_time = f"{source} · {published}" if source and published else source or published

        articles_html += ARTICLE_TEMPLATE.format(
            tag_bg=style["bg"],
            tag_color=style["color"],
            tag_text=tag_text,
            source_time=source_time,
            title=art.get("title", ""),
            link=art.get("link", "#"),
            desc=art.get("one_liner", ""),
        )

    # 针对生产环境分发的动态注入
    base_url = os.environ.get("WEB_BASE_URL", "").rstrip("/")
    
    # 如果没有配置公网 URL，则隐藏反馈模块
    feedback_section_html = ""
    if base_url:
        feedback_section_html = f"""
          <!-- 用户反馈 (RLHF) -->
          <tr>
            <td style="padding: 30px 40px; background-color: #FFFFFF; border-top: 1px solid #E6E2DE; text-align: center;">
              <p style="margin: 0 0 15px 0; font-size: 14px; color: #726B66; font-weight: 500;">这份简报对你有帮助吗？(反馈将直接优化 AI 生成逻辑)</p>
              <table align="center" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right: 20px;">
                    <a href="{base_url}/feedback?id={date_str}_{datetime.now().strftime('%H%M%S')}&type=like" style="display: inline-block; padding: 10px 24px; background-color: #E8F0EA; color: #2D5D3B; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; border: 1px solid #D1E0D5;">👍 很有用</a>
                  </td>
                  <td>
                    <a href="{base_url}/feedback?id={date_str}_{datetime.now().strftime('%H%M%S')}&type=dislike" style="display: inline-block; padding: 10px 24px; background-color: #FFF0E6; color: #A44200; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; border: 1px solid #FADCC8;">👎 质量一般</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        """

    return HTML_TEMPLATE.format(
        summary_text=summary,
        articles_html=articles_html,
        date_str=date_str,
        subscriber_name=subscriber_name,
        greeting_text=greeting_text,
        feedback_section=feedback_section_html
    )


def _render_from_markdown(md_content: str, date_str: str, subscriber_name: str, greeting_text: str) -> str:
    """Fallback：用正则从 Markdown 解析，兜底用。"""
    summary_match = re.search(r'## 📌 今日摘要\n(.*?)\n##', md_content, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else "这是今日的专属工作流简报。"

    articles_section = re.search(
        r'## 🔥 重点文章.*?(\n### .*?)(?=\n## 🗂️|\Z)', md_content, re.DOTALL
    )
    articles_html = ""
    if articles_section:
        for block in articles_section.group(1).strip().split('### '):
            if not block.strip():
                continue
            lines = block.strip().split('\n')
            title, source_time, desc, link = lines[0].strip(), "", "", "#"
            for line in lines[1:]:
                if line.startswith('- **来源**'):
                    source_time = line.replace('- **来源**：', '').replace('**时间**：', '· ').strip()
                elif line.startswith('- **一句话**'):
                    desc = line.replace('- **一句话**：', '').strip()
                elif '🔗' in line:
                    m = re.search(r'(https?://\S+)', line)
                    if m:
                        link = m.group(1)
            articles_html += ARTICLE_TEMPLATE.format(
                tag_bg=_DEFAULT_TAG["bg"], tag_color=_DEFAULT_TAG["color"],
                tag_text=_DEFAULT_TAG["text"], source_time=source_time,
                title=title, link=link, desc=desc,
            )

    # 同样处理 Fallback 模式
    base_url = os.environ.get("WEB_BASE_URL", "").rstrip("/")
    feedback_section_html = ""
    if base_url:
        feedback_section_html = f"""
          <tr>
            <td style="padding: 30px 40px; background-color: #FFFFFF; border-top: 1px solid #E6E2DE; text-align: center;">
              <p style="margin: 0 0 15px 0; font-size: 14px; color: #726B66;">反馈此简报: 
                <a href="{base_url}/feedback?id={date_str}_fallback&type=like">👍</a> / 
                <a href="{base_url}/feedback?id={date_str}_fallback&type=dislike">👎</a>
              </p>
            </td>
          </tr>
        """

    return HTML_TEMPLATE.format(
        summary_text=summary, articles_html=articles_html, date_str=date_str,
        subscriber_name=subscriber_name, greeting_text=greeting_text,
        feedback_section=feedback_section_html
    )


def dict_to_markdown(data: dict, date_str: str, mode: str = "morning") -> str:
    """把解析后的 dict 渲染成可读的 Markdown，用于保存 .md 文件。"""
    if mode == "evening":
        title = f"# 🤖 晚上好，Nancy！今晚 AI 简报 · {date_str}"
    else:
        title = f"# 🤖 早安，Nancy！今日 AI 简报 · {date_str}"
    lines = [title, "", "## 📌 今日摘要", data.get("summary", ""), ""]
    articles = data.get("articles", [])
    if articles:
        lines.append("## 🔥 重点文章")
        for art in articles:
            lines += [
                f"### {art.get('title', '')}",
                f"- **来源**：{art.get('source', '')}  **时间**：{art.get('published', '')}",
                f"- **分类**：{art.get('category', '')}",
                f"- **一句话**：{art.get('one_liner', '')}",
                f"- 🔗 {art.get('link', '')}",
                "",
            ]
    return "\n".join(lines)


def _repair_json(raw: str) -> str:
    """
    修复 LLM 常见的 JSON 错误：字符串值中出现未转义的双引号。
    策略：逐字符扫描，遇到字符串内的 " 时，向后看第一个非空白字符：
      - 若为 JSON 结构符 (: , } ])  → 合法的字符串结束符，保留
      - 否则                        → 内容引号，替换为 \"
    """
    result = []
    i = 0
    n = len(raw)
    in_string = False

    while i < n:
        ch = raw[i]
        if in_string:
            if ch == '\\':
                result.append(ch)
                i += 1
                if i < n:
                    result.append(raw[i])
                    i += 1
                continue
            elif ch == '"':
                # 前瞻：跳过空白后的第一个字符
                j = i + 1
                while j < n and raw[j] in ' \t\n\r':
                    j += 1
                next_ch = raw[j] if j < n else ''
                if next_ch in ':,}]':
                    # 合法结束符
                    result.append('"')
                    in_string = False
                else:
                    # 内容中的引号，转义
                    result.append('\\"')
            else:
                result.append(ch)
        else:
            if ch == '"':
                result.append('"')
                in_string = True
            else:
                result.append(ch)
        i += 1

    return ''.join(result)


def _try_parse_json(content: str):
    """先直接解析，失败则尝试修复后再解析。返回 (data, parse_path)"""
    start = content.find('{')
    if start == -1:
        raise ValueError("No JSON object found")
    raw = content[start:]
    try:
        return json.loads(raw), "json_direct"
    except json.JSONDecodeError:
        pass
    # 用逐字符修复再试
    try:
        fixed = _repair_json(raw)
        return json.loads(fixed), "json_repaired"
    except json.JSONDecodeError:
        raise


def parse_markdown_to_html(content: str, date_str: str, subscriber_name: str = "Nancy",
                           mode: str = "morning", greeting_text: str = None) -> tuple[str, str, str]:
    """
    主入口。content 优先当 JSON 处理，失败则 fallback 到 Markdown 正则。
    返回 (html_str, markdown_str, parse_path)
    parse_path: "json_direct" | "json_repaired" | "fallback"
    greeting_text: 若传入则覆盖 mode 派生的默认问候语
    """
    if greeting_text is None:
        greeting_text = "🌙 晚上好" if mode == "evening" else "☀️ 早上好"
    try:
        data, parse_path = _try_parse_json(content)
        html = _render_from_dict(data, date_str, subscriber_name, greeting_text)
        md = dict_to_markdown(data, date_str, mode)
        return html, md, parse_path
    except (json.JSONDecodeError, ValueError):
        # Ollama 或格式不规范时的兜底
        html = _render_from_markdown(content, date_str, subscriber_name, greeting_text)
        return html, content, "fallback"
