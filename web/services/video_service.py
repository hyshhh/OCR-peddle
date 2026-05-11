"""视频演示服务 — 采集摄像头/视频文件帧，通过 WebSocket 推送到前端"""

from __future__ import annotations

import asyncio
import base64
import logging
import platform
import time
from pathlib import Path
from typing import Any

import cv2

from config import load_config

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".ts"}


class VideoDemoService:
    """管理视频采集会话，提供摄像头/文件枚举和帧推送"""

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or load_config()
        demo_cfg = cfg.get("web_demo", {})
        self._fps = demo_cfg.get("default_fps", 15)
        self._quality = demo_cfg.get("jpeg_quality", 70)
        self._max_width = demo_cfg.get("max_width", 960)
        self._camera_index = demo_cfg.get("camera_index", 0)
        self._video_dir = Path(demo_cfg.get("video_dir", "./data"))

    # ── 枚举可用视频源 ──

    def list_cameras(self) -> list[dict]:
        """探测可用摄像头（尝试 index 0-9）"""
        cameras: list[dict] = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append({"index": i, "name": self._camera_name(i)})
                cap.release()
        return cameras

    def list_videos(self) -> list[dict]:
        """扫描配置目录下的视频文件"""
        videos: list[dict] = []
        if not self._video_dir.exists():
            return videos
        for f in sorted(self._video_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                videos.append({"name": f.name, "path": str(f.resolve())})
        return videos

    def list_sources(self) -> dict:
        return {
            "cameras": self.list_cameras(),
            "videos": self.list_videos(),
            "default_fps": self._fps,
        }

    # ── WebSocket 帧推送 ──

    async def stream(
        self,
        websocket,
        source_type: str,
        source_value: str | int,
        fps: int | None = None,
        on_frame=None,
    ):
        """
        从 source 读取帧 → 编码 JPEG → base64 → 通过 websocket 发送。

        source_type: "camera" | "file"
        source_value: 摄像头编号(int) 或 文件路径(str)
        on_frame: 可选回调 on_frame(frame) -> annotated_frame，用于叠加检测结果
        """
        effective_fps = fps or self._fps
        interval = 1.0 / effective_fps

        if source_type == "camera":
            cap = cv2.VideoCapture(int(source_value))
        else:
            cap = cv2.VideoCapture(str(source_value))

        if not cap.isOpened():
            await websocket.send_json({"type": "error", "message": f"无法打开视频源: {source_value}"})
            return

        # 发送视频元信息
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30

        await websocket.send_json({
            "type": "meta",
            "width": width,
            "height": height,
            "total_frames": total_frames,
            "fps": orig_fps,
            "source_type": source_type,
            "source_value": str(source_value),
        })

        frame_count = 0
        try:
            while True:
                t0 = time.monotonic()
                ret, frame = cap.read()
                if not ret:
                    # 视频文件播放完毕
                    await websocket.send_json({"type": "ended", "frames": frame_count})
                    break

                frame_count += 1

                # 等比缩放
                if self._max_width and frame.shape[1] > self._max_width:
                    scale = self._max_width / frame.shape[1]
                    frame = cv2.resize(frame, None, fx=scale, fy=scale)

                # 可选：叠加检测结果
                if on_frame is not None:
                    try:
                        frame = on_frame(frame)
                    except Exception as e:
                        logger.warning("on_frame 回调异常: %s", e)

                # 编码
                encode_param = [cv2.IMWRITE_JPEG_QUALITY, self._quality]
                _, buffer = cv2.imencode(".jpg", frame, encode_param)
                b64 = base64.b64encode(buffer).decode("ascii")

                await websocket.send_json({
                    "type": "frame",
                    "frame": b64,
                    "index": frame_count,
                })

                # 帧率控制
                elapsed = time.monotonic() - t0
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("视频流被取消")
        except Exception as e:
            logger.error("视频流异常: %s", e, exc_info=True)
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            cap.release()

    # ── 工具 ──

    @staticmethod
    def _camera_name(index: int) -> str:
        if platform.system() == "Darwin":
            return f"FaceTime Camera ({index})"
        elif platform.system() == "Windows":
            return f"摄像头 {index}"
        else:
            return f"/dev/video{index}"
