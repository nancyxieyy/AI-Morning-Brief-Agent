import re
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 严格边界：只锁定在 morning_brief 沙盒内的解耦范围
WEB_DIR = Path(__file__).resolve().parent
MORNING_BRIEF_DIR = WEB_DIR.parent
BASE_DIR = MORNING_BRIEF_DIR.parent.parent
DAILY_DIR = BASE_DIR / "Daily"

import sys
sys.path.insert(0, str(MORNING_BRIEF_DIR))
from html_renderer import parse_markdown_to_html

app = FastAPI(title="Daily Brief Dashboard")

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

def get_briefs():
    """扫描项目落盘归档，返回倒序侧边栏列表"""
    briefs = []
    if not DAILY_DIR.exists():
        return briefs
        
    for date_folder in sorted([f for f in DAILY_DIR.iterdir() if f.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', f.name)], reverse=True):
        date_str = date_folder.name
        
        for md_file in sorted(date_folder.glob("*.md"), reverse=True):
            preview = "内容生成中 / 无文本抓取"
            lines = md_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if line.startswith("#") or line.startswith(">") or len(line.strip()) < 10: 
                    continue
                preview = line.strip()[:60] + "..."
                break
            
            briefs.append({
                "date": date_str,
                "filename": md_file.name,
                "preview": preview,
                "path": f"{date_str}/{md_file.name}"
            })
    return briefs

# -----------------
# 动态双栏布局控制层
# -----------------
@app.get("/")
@app.get("/brief/{date_str}/{filename}")
async def view_dashboard(request: Request, date_str: str = None, filename: str = None):
    briefs = get_briefs()
    
    if not briefs:
        return templates.TemplateResponse(
            request=request, name="index.html", context={"briefs": [], "raw_html": None}
        )
        
    # 如果是根目录 `/` 挂载，默认将列表里最新产出的一份记录激活！
    if not date_str or not filename:
        latest = briefs[0]
        date_str = latest["date"]
        filename = latest["filename"]
        
    target_file = DAILY_DIR / date_str / filename
    if not target_file.exists():
        raise HTTPException(status_code=404, detail="Brief not found")
        
    raw_md = target_file.read_text(encoding="utf-8")

    # 兼容老文件的名字与新文件名的中英模式匹配
    mode_str = "evening" if "晚" in filename or "Evening" in filename else "morning"
    html_content, _, _ = parse_markdown_to_html(raw_md, date_str, "Web 主理人视角", mode_str, "😎 欢迎登入专属 Daily Brief 档案馆")
    
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "briefs": briefs,
            "current_date": date_str,
            "current_file": filename,
            "raw_html": html_content
        }
    )

# -----------------
# JSON API 抽象保留口
# -----------------
@app.get("/api/briefs")
async def api_get_briefs():
    return {"status": "success", "data": get_briefs()}
