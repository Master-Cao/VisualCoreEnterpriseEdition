# -*- coding: utf-8 -*-

import time

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext

import cv2  # type: ignore
import numpy as np  # type: ignore


def handle_model_test(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    try:
        det = ctx.detector
        cam = ctx.camera
        if not det:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="detector",
                messageType=MessageType.ERROR,
                message="detector_not_ready",
                data={},
            )
        if not cam or not getattr(cam, "healthy", False):
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_not_ready",
                data={},
            )
        frame = cam.get_frame(convert_to_mm=True)
        img = frame_to_image(frame) if frame else None
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_frame",
                data={},
            )
        t0 = time.time()
        results = det.detect(img)
        dt = (time.time() - t0) * 1000.0
        count = len(results) if hasattr(results, "__len__") else (1 if results else 0)
        return MQTTResponse(
            command=VisionCoreCommands.MODEL_TEST.value,
            component="detector",
            messageType=MessageType.SUCCESS,
            message="ok",
            data={"detection_count": count, "infer_time_ms": round(dt, 1)},
        )
    except Exception as e:
        return MQTTResponse(
            command=VisionCoreCommands.MODEL_TEST.value,
            component="detector",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )


def frame_to_image(frame):
    try:
        if frame is None or cv2 is None or np is None:
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


