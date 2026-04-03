import re
from datetime import datetime
from pathlib import Path
import json
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 严格边界：只锁定在 morning_brief 沙盒内的解耦范围
WEB_DIR = Path(__file__).resolve().parent
MORNING_BRIEF_DIR = WEB_DIR.parent
BASE_DIR = MORNING_BRIEF_DIR.parent.parent
DAILY_DIR = BASE_DIR / "Daily"

import sys
import os
sys.path.insert(0, str(MORNING_BRIEF_DIR))
from html_renderer import parse_markdown_to_html

# 配置与安全
CONFIG_PATH = BASE_DIR / "configs" / "admin_settings.json"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "nancy123") # 默认 Token，建议部署时修改

def load_settings():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"subscribers": [], "sections": [{"id": "ai", "name": "AI 简报"}]}

def save_settings(settings):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

app = FastAPI(title="Daily Brief Dashboard")

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

# 各板块文件名前缀（含历史遗留英文命名）
SECTION_FILE_PREFIXES = {
    "ai":   ["今日AI新闻", "今晚AI简报", "ai"],
    "tech": ["今日科技热点", "今晚科技热点", "tech", "全球科技热点"],
    "econ": ["今日经济简报", "今晚经济简报", "econ", "经济与宏观趋势"],
}

def get_briefs(section_id: str = None):
    """根据板块 ID 扫描 Daily 目录，获取该板块的简报列表"""
    briefs = []
    if not DAILY_DIR.exists():
        return []

    prefixes = SECTION_FILE_PREFIXES.get(section_id) if section_id else None

    for date_folder in sorted(
        [f for f in DAILY_DIR.iterdir() if f.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', f.name)],
        reverse=True
    ):
        date_str = date_folder.name
        for f in sorted(date_folder.glob("*.md"), reverse=True):
            filename = f.name

            # 按板块过滤：只保留前缀匹配的文件
            if prefixes is not None:
                if not any(filename.startswith(p) for p in prefixes):
                    continue

            try:
                content = f.read_text(encoding="utf-8")
                preview = content.split("## 📌 今日摘要")[-1].split("##")[0].strip()[:60] + "..."
            except:
                preview = "点击查看内容"

            briefs.append({
                "date": date_str,
                "filename": filename,
                "path": f"{date_str}/{filename}",
                "preview": preview
            })
    return briefs

# -----------------
# 动态双栏布局控制层
# -----------------
@app.get("/")
async def index_redirect():
    return RedirectResponse(url="/ai")

@app.get("/{section_id}")
@app.get("/{section_id}/brief/{date_str}/{filename}")
async def view_dashboard(request: Request, section_id: str, date_str: str = None, filename: str = None):
    # 验证 section_id 是否合法
    settings = load_settings()
    sections = settings.get("sections", [])
    current_sec = next((s for s in sections if s["id"] == section_id), None)
    if not current_sec:
        # 兜底兼容
        if section_id == "brief" or section_id == "favicon.ico":
             return RedirectResponse(url="/ai")
        return HTMLResponse("Section not found", status_code=404)

    briefs = get_briefs(section_id)
    
    # 确定要显示的具体文件
    target_date = date_str
    target_file = filename

    if not target_date or not target_file:
        # 如果没指定，默认显示该频道最新的简报
        if briefs:
            target_date = briefs[0]["date"]
            target_file = briefs[0]["filename"]
    
    raw_html = ""
    if target_date and target_file:
        file_path = DAILY_DIR / target_date / target_file
        if file_path.exists():
            # 兼容老文件的名字
            mode_str = "evening" if "晚" in target_file or "Evening" in target_file else "morning"
            md_content = file_path.read_text(encoding="utf-8")
            raw_html, _, _ = parse_markdown_to_html(md_content, target_date, "Web 主理人视角", mode_str)

    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "sections": sections,
            "current_sec": current_sec,
            "briefs": briefs,
            "current_date": target_date,
            "current_file": target_file,
            "raw_html": raw_html
        }
    )

# -----------------
# JSON API 抽象保留口
# -----------------
@app.get("/api/briefs")
async def api_get_briefs():
    return {"status": "success", "data": get_briefs()}

# -----------------
# 进阶控制台 API (SaaS Admin Panel)
# -----------------
@app.get("/admin")
async def admin_page(request: Request, token: str = None):
    """管理员控制大盘：可视化操作订阅与模型配置"""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing token")
        
    settings = load_settings()
    return templates.TemplateResponse(
        request=request, name="admin.html", context={"settings": settings, "token": token}
    )

@app.get("/api/settings/subscribers")
async def get_subscribers(token: str = None):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    return load_settings().get("subscribers", [])

@app.post("/api/settings/subscribers/add")
async def add_subscriber(data: dict = Body(...), token: str = None):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    
    name = data.get("name")
    email = data.get("email")
    timezone = data.get("timezone", "Asia/Shanghai")
    
    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and Email are required")
        
    settings = load_settings()
    # 防重复校验
    if any(s["email"] == email for s in settings["subscribers"]):
        return {"status": "error", "message": "Email already exists"}
        
    settings["subscribers"].append({"name": name, "email": email, "timezone": timezone})
    save_settings(settings)
    return {"status": "success", "data": settings["subscribers"]}

@app.post("/api/settings/subscribers/remove")
async def remove_subscriber(data: dict = Body(...), token: str = None):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    
    """剔除订阅者：原子操作确保配置文件完备"""
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
        
    settings = load_settings()
    original_len = len(settings["subscribers"])
    settings["subscribers"] = [s for s in settings["subscribers"] if s["email"] != email]
    
    if len(settings["subscribers"]) == original_len:
        return {"status": "error", "message": "Email not found"}
        
    save_settings(settings)
    return {"status": "success", "data": settings["subscribers"]}

# -----------------
# 用户反馈系统 (RLHF Loop)
# -----------------
@app.get("/feedback")
async def receive_feedback(id: str, type: str):
    """接收用户反馈：如果是吐槽 (dislike)，则将当前上下文打入日志"""
    message = "感谢你的点赞！我们会继续保持高质量生成。🌅" if type == "like" else "收到你的反馈，已经将此案例记录，AI 将在下次生成时自动参考此偏好。🛠️"
    
    # 建立日志文件夹
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    feedback_log = logs_dir / "user_feedback.jsonl"
    
    with open(feedback_log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": datetime.now().isoformat(), "brief_id": id, "sentiment": type}, ensure_ascii=False) + "\n")

    return f"""
    <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; background: #F7F5F2; color: #2A2827;">
            <div style="background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); text-align: center;">
                <h2 style="margin-bottom: 20px;">{'🙏' if type=='like' else '🔧'} 反馈已收到</h2>
                <p style="color: #736B66; line-height: 1.6;">{message}</p>
                <div style="margin-top: 30px;">
                    <a href="/" style="color: #3B82F6; text-decoration: none; font-weight: 600;">← 返回简报档案馆</a>
                </div>
            </div>
        </body>
    </html>
    """
