# -*- coding: utf-8 -*-

from typing import List, Tuple

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from .utils import frame_to_image, encode_jpg, sftp_upload_bytes

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None


def handle_get_image(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
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
        frame = cam.get_frame(convert_to_mm=True)
        ok = bool(frame)
        upload_info = None
        if ok:
            img = frame_to_image(frame)
            if img is not None:
                jpg = encode_jpg(img)
                if jpg is not None:
                    upload_info = sftp_upload_bytes(ctx.sftp, jpg, ctx.project_root, prefix="camera_image")
        return MQTTResponse(
            command=VisionCoreCommands.GET_IMAGE.value,
            component="camera",
            messageType=MessageType.SUCCESS if ok else MessageType.ERROR,
            message="ok" if ok else "no_frame",
            data={"has_frame": ok, "sftp": upload_info} if upload_info else {"has_frame": ok},
        )
    except Exception as e:
        return MQTTResponse(
            command=VisionCoreCommands.GET_IMAGE.value,
            component="camera",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )


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


