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


def handle_get_calibrat_image(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    try:
        cam = ctx.camera
        if not cam or not getattr(cam, "healthy", False):
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_not_ready",
                data={},
            )
        frame = cam.get_frame(convert_to_mm=True)
        if not frame:
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_frame",
                data={},
            )
        img = frame_to_image(frame)
        if img is None or cv2 is None:
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="opencv_unavailable_or_no_image",
                data={},
            )
        gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        vis = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        points = []
        success = False
        # ArUco 检测
        try:
            aruco = cv2.aruco  # type: ignore
            dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
            params = aruco.DetectorParameters()
            corners, ids, _ = aruco.detectMarkers(gray, dictionary, parameters=params)
            if ids is not None and len(ids) > 0:
                for c in corners:
                    for p in c.reshape(-1, 2):
                        points.append((float(p[0]), float(p[1])))
                success = len(points) >= 4
        except Exception:
            success = False
        # Chessboard 回退
        if not success:
            try:
                found, corners = cv2.findChessboardCorners(gray, (7, 7))
                if found and corners is not None:
                    cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                    for p in corners.reshape(-1, 2):
                        points.append((float(p[0]), float(p[1])))
                    success = len(points) >= 4
            except Exception:
                success = False
        # 标注与上传
        upload_info = None
        if success:
            for i, (u, v) in enumerate(points, 1):
                cv2.circle(vis, (int(round(u)), int(round(v))), 5, (0, 255, 0), -1)
                cv2.putText(vis, str(i), (int(round(u)) + 4, int(round(v)) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
            jpg = encode_jpg(vis)
            if jpg is not None:
                upload_info = sftp_upload_bytes(ctx.sftp, jpg, ctx.project_root, prefix="calib")
        payload = {
            "points_xy": [{"index": i + 1, "u": round(p[0], 3), "v": round(p[1], 3)} for i, p in enumerate(points)],
            "points_count": len(points),
        }
        if upload_info:
            payload["image_remote"] = upload_info
        return MQTTResponse(
            command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
            component="calibrator",
            messageType=MessageType.SUCCESS if success else MessageType.ERROR,
            message="ok" if success else "no_enough_points",
            data=payload,
        )
    except Exception as e:
        return MQTTResponse(
            command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
            component="calibrator",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )


