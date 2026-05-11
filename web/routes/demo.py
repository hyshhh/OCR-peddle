"""演示路由 — 视频源枚举 + WebSocket 帧推送"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from config import load_config
from web.services.video_service import VideoDemoService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])

_video_svc: VideoDemoService | None = None


def get_video_service() -> VideoDemoService:
    global _video_svc
    if _video_svc is None:
        _video_svc = VideoDemoService()
    return _video_svc


# ── REST: 列出可用视频源 ──

@router.get("/sources")
async def list_sources(svc: VideoDemoService = Depends(get_video_service)):
    """返回可用摄像头和视频文件列表"""
    return svc.list_sources()


@router.get("/config")
async def demo_config():
    """返回 web_demo 配置（前端用来判断是否显示演示入口）"""
    cfg = load_config().get("web_demo", {})
    return {"enabled": cfg.get("enabled", False)}


# ── WebSocket: 实时帧推送 ──

@router.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    """
    客户端连接后发送 JSON 启动消息：
    {
        "source_type": "camera" | "file",
        "source_value": 0 | "/path/to/video.mp4",
        "fps": 15            // 可选
    }
    服务端持续推送：
    {"type": "frame",  "frame": "<base64>", "index": N}
    {"type": "meta",   "width": W, "height": H, ...}
    {"type": "ended",  "frames": N}
    {"type": "error",  "message": "..."}
    """
    await websocket.accept()
    svc = get_video_service()

    try:
        # 等待客户端发送启动配置
        config = await websocket.receive_json()
        source_type = config.get("source_type", "camera")
        source_value = config.get("source_value", 0)
        fps = config.get("fps")

        logger.info("演示流启动: type=%s value=%s fps=%s", source_type, source_value, fps)

        await svc.stream(
            websocket=websocket,
            source_type=source_type,
            source_value=source_value,
            fps=fps,
        )

    except WebSocketDisconnect:
        logger.info("演示客户端断开")
    except Exception as e:
        logger.error("演示 WebSocket 异常: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
