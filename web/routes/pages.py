"""页面路由 — 返回 Jinja2 渲染的 HTML 页面"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

from config import load_config

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter(tags=["pages"])


@router.get("/")
async def index(request: Request):
    """主页 — 船只管理界面"""
    cfg = load_config()
    demo_enabled = cfg.get("web_demo", {}).get("enabled", False)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "demo_enabled": demo_enabled,
    })


@router.get("/demo")
async def demo(request: Request):
    """实时演示页面"""
    cfg = load_config()
    demo_enabled = cfg.get("web_demo", {}).get("enabled", False)
    if not demo_enabled:
        return templates.TemplateResponse("demo.html", {
            "request": request,
            "demo_enabled": False,
            "error": "演示功能未开启，请在 config.yaml 中设置 web_demo.enabled: true",
        })
    return templates.TemplateResponse("demo.html", {
        "request": request,
        "demo_enabled": True,
    })
