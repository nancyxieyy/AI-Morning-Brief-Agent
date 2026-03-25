import json
import re

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
                    <h1 style="margin: 0; font-size: 24px; color: #2A2827; font-weight: 600;">&#9728;&#65039; 早安！今日 AI 工作流简报</h1>
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


def _render_from_dict(data: dict, date_str: str) -> str:
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
        source_time = f"{source} &middot; {published}" if source and published else source or published

        articles_html += ARTICLE_TEMPLATE.format(
            tag_bg=style["bg"],
            tag_color=style["color"],
            tag_text=tag_text,
            source_time=source_time,
            title=art.get("title", ""),
            link=art.get("link", "#"),
            desc=art.get("one_liner", ""),
        )

    return HTML_TEMPLATE.format(
        summary_text=summary,
        articles_html=articles_html,
        date_str=date_str,
    )


def _render_from_markdown(md_content: str, date_str: str) -> str:
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
                    source_time = line.replace('- **来源**：', '').replace('**时间**：', '&middot; ').strip()
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

    return HTML_TEMPLATE.format(
        summary_text=summary, articles_html=articles_html, date_str=date_str
    )


def dict_to_markdown(data: dict, date_str: str) -> str:
    """把解析后的 dict 渲染成可读的 Markdown，用于保存 .md 文件。"""
    lines = [f"# 🤖 早安！今日 AI 简报 · {date_str}", "", "## 📌 今日摘要", data.get("summary", ""), ""]
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


def parse_markdown_to_html(content: str, date_str: str) -> tuple[str, str]:
    """
    主入口。content 优先当 JSON 处理，失败则 fallback 到 Markdown 正则。
    返回 (html_str, markdown_str) 供调用方分别用于发邮件和保存文件。
    """
    try:
        # 找到第一个 { 交给 json.loads 自己定边界，天然处理嵌套且不被尾部杂文干扰
        start = content.find('{')
        if start == -1:
            raise ValueError("No JSON object found")
        data = json.loads(content[start:])
        html = _render_from_dict(data, date_str)
        md = dict_to_markdown(data, date_str)
        return html, md
    except (json.JSONDecodeError, ValueError):
        # Ollama 或格式不规范时的兜底
        html = _render_from_markdown(content, date_str)
        return html, content
