# -*- coding: utf-8 -*-

import time
from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from .utils import frame_to_image


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


