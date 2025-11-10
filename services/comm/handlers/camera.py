# -*- coding: utf-8 -*-

import os
from datetime import datetime
from typing import Optional

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext

import cv2  # type: ignore
import numpy as np  # type: ignore


def handle_get_image(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    logger = getattr(ctx, "logger", None)
    try:
        cam = ctx.camera
        if not cam or not getattr(cam, "healthy", False):
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_not_ready",
                data={},
            )

        sftp = ctx.sftp
        if not sftp:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="sftp_not_ready",
                data={},
            )

        try:
            frame = cam.get_frame(convert_to_mm=True)
        except Exception as capture_err:
            if logger:
                try:
                    logger.error(f"camera.get_frame failed: {capture_err}")
                except Exception:
                    pass
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_capture_failed",
                data={},
            )

        if not frame:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_frame",
                data={},
            )

        img = frame_to_image(frame)
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_image",
                data={},
            )

        jpg = encode_jpg(img)
        if jpg is None:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="encode_failed",
                data={},
            )

        upload_info = sftp_upload_bytes(sftp, jpg, ctx.project_root, prefix="camera_image")
        if not upload_info:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="upload_failed",
                data={},
            )

        remote_path = upload_info.get("remote_path")
        filename = upload_info.get("filename")
        remote_rel_path = upload_info.get("remote_rel_path")
        sftp_cfg = {}
        try:
            if isinstance(ctx.config, dict):
                sftp_cfg = ctx.config.get("sftp") or {}
        except Exception:
            sftp_cfg = {}
        prefix = str(sftp_cfg.get("prefix", "")) if isinstance(sftp_cfg, dict) else ""
        remote_full_path = None
        if remote_rel_path:
            rel = str(remote_rel_path)
            if prefix:
                base = str(prefix)
                joiner = "" if base.endswith("/") else "/"
                remote_full_path = f"{base}{joiner}{rel.lstrip('/')}"
            else:
                remote_full_path = rel
        payload = {
            "has_frame": True,
            "filename": filename,
            "remote_path": remote_path,
            "remote_rel_path": upload_info.get("remote_rel_path"),
            "remote_file": upload_info.get("remote_file"),
            "file_size": upload_info.get("file_size"),
            "image_shape": list(img.shape) if hasattr(img, "shape") else None,
            "image_remote": upload_info,
            "remote_full_path": remote_full_path,
        }

        if logger and filename:
            try:
                logger.info(
                    "camera image captured",
                    extra={"filename": filename, "remote_path": remote_path},
                )
            except Exception:
                try:
                    logger.info(f"camera image captured: {filename} -> {remote_path}")
                except Exception:
                    pass

        return MQTTResponse(
            command=VisionCoreCommands.GET_IMAGE.value,
            component="sftp",
            messageType=MessageType.SUCCESS,
            message="ok",
            data=payload,
        )
    except Exception as e:
        if logger:
            try:
                logger.error(f"handle_get_image unexpected error: {e}")
            except Exception:
                pass
        return MQTTResponse(
            command=VisionCoreCommands.GET_IMAGE.value,
            component="camera",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )


def frame_to_image(frame) -> Optional["np.ndarray"]:
    try:
        if frame is None:
            return None
        dm = frame.get("depthmap") if isinstance(frame, dict) else None
        params = frame.get("cameraParams") if isinstance(frame, dict) else None
        if dm is not None and params is not None:
            width = int(getattr(params, "width", 0) or getattr(params, "Width", 0) or 0)
            height = int(getattr(params, "height", 0) or getattr(params, "Height", 0) or 0)
            intensity = getattr(dm, "intensity", None)
            if hasattr(intensity, "__iter__") and width > 0 and height > 0:
                arr = np.array(list(intensity), dtype=np.float32).reshape((height, width))
                img = cv2.convertScaleAbs(arr, alpha=0.05, beta=1)
                return img
        return None
    except Exception:
        return None


def encode_jpg(img) -> Optional[bytes]:
    try:
        if cv2 is None:
            return None
        ok, buf = cv2.imencode(".jpg", img)
        if not ok:
            return None
        return bytes(buf)
    except Exception:
        return None


def sftp_upload_bytes(sftp, data: bytes, project_root: str, prefix: str = "image") -> Optional[dict]:
    try:
        if not sftp or data is None:
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{prefix}_{ts}.jpg"
        remote_rel = os.path.join("images", filename).replace("\\", "/")
        ok = sftp.upload_bytes(data, remote_rel)
        if ok:
            remote_dir = os.path.dirname(remote_rel).replace("\\", "/")
            if not remote_dir.startswith("/"):
                remote_dir = f"/{remote_dir}" if remote_dir else "/"
            if not remote_dir.endswith("/"):
                remote_dir = f"{remote_dir}/"
            remote_file = f"{remote_dir.rstrip('/')}/{filename}"
            return {
                "filename": filename,
                "remote_path": remote_dir,
                "remote_rel_path": remote_rel,
                "remote_file": remote_file,
                "file_size": len(data),
            }
        return None
    except Exception:
        return None


# get_calibrat_image 命令已迁移到 handlers/calibration.py
# 使用新的黑块检测算法代替 ArUco/棋盘格检测
# 参见: handle_get_calibrat_image() in handlers/calibration.py
