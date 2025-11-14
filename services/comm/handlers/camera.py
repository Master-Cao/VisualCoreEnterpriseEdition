# -*- coding: utf-8 -*-

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from services.shared import ImageUtils, SftpHelper


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

        # 使用新的 get_frame 方法，只获取强度图像以加快速度
        result = cam.get_frame(depth=False, intensity=True, camera_params=False)
        if not result:
            if logger:
                try:
                    logger.error("camera.get_frame failed: returned None")
                except Exception:
                    pass
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_capture_failed",
                data={},
            )

        img = result.get('intensity_image')
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_image",
                data={},
            )

        jpg = ImageUtils.encode_jpg(img)
        if jpg is None:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="encode_failed",
                data={},
            )

        upload_info = SftpHelper.upload_image_bytes(sftp, jpg, prefix="camera_image")
        if not upload_info:
            return MQTTResponse(
                command=VisionCoreCommands.GET_IMAGE.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="upload_failed",
                data={},
            )

        # 获取SFTP配置并构建完整路径
        sftp_cfg = ctx.config.get("sftp") if isinstance(ctx.config, dict) else {}
        upload_info = SftpHelper.get_upload_info_with_prefix(upload_info, sftp_cfg)
        
        remote_path = upload_info.get("remote_path")
        filename = upload_info.get("filename")
        remote_rel_path = upload_info.get("remote_rel_path")
        remote_full_path = upload_info.get("remote_full_path")
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
