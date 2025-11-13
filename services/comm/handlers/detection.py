# -*- coding: utf-8 -*-

import time

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from .utils import encode_jpg, upload_image_to_sftp, draw_detection_results


def handle_model_test(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    logger = getattr(ctx, "logger", None)
    try:
        det = ctx.detector
        cam = ctx.camera
        sftp = ctx.sftp
        
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
        if not sftp:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="sftp_not_ready",
                data={},
            )
        
        # 使用新的 get_frame 方法，只获取强度图像以加快速度
        result = cam.get_frame(depth=False, intensity=True, camera_params=False)
        img = result.get('intensity_image') if result else None
        
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_frame",
                data={},
            )
        
        # 执行检测
        t0 = time.time()
        results = det.detect(img)
        dt = (time.time() - t0) * 1000.0
        count = len(results) if hasattr(results, "__len__") else (1 if results else 0)
        
        # 绘制检测结果到图像上
        vis_img = draw_detection_results(img, results, class_names=["seasoning", "hand"], show_bbox=False)
        
        # 编码为JPG
        jpg = encode_jpg(vis_img)
        if jpg is None:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="encode_failed",
                data={},
            )
        
        # 上传到SFTP
        upload_info = upload_image_to_sftp(sftp, jpg, prefix="detection_test")
        if not upload_info:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="upload_failed",
                data={},
            )
        
        # 构建返回数据
        remote_path = upload_info.get("remote_path")
        filename = upload_info.get("filename")
        remote_rel_path = upload_info.get("remote_rel_path")
        
        # 获取SFTP配置前缀
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
            "detection_count": count,
            "infer_time_ms": round(dt, 1),
            "filename": filename,
            "remote_path": remote_path,
            "remote_rel_path": remote_rel_path,
            "remote_file": upload_info.get("remote_file"),
            "remote_full_path": remote_full_path,
            "file_size": upload_info.get("file_size"),
            "image_shape": list(vis_img.shape) if hasattr(vis_img, "shape") else None,
        }
        
        if logger and filename:
            try:
                logger.info(
                    f"检测测试完成: {count}个目标, 推理耗时={dt:.1f}ms, 图像已上传: {filename}"
                )
            except Exception:
                pass
        
        return MQTTResponse(
            command=VisionCoreCommands.MODEL_TEST.value,
            component="detector",
            messageType=MessageType.SUCCESS,
            message="ok",
            data=payload,
        )
    except Exception as e:
        if logger:
            try:
                logger.error(f"handle_model_test error: {e}")
            except Exception:
                pass
        return MQTTResponse(
            command=VisionCoreCommands.MODEL_TEST.value,
            component="detector",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )
