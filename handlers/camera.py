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
        # SFTP是非关键组件，允许为None（禁用时不影响图像获取功能）

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

        # 上传到SFTP（非关键操作，失败不影响图像获取）
        upload_info = None
        if sftp:
            try:
                upload_info = SftpHelper.upload_image_bytes(sftp, jpg, prefix="camera_image")
                if upload_info:
                    # 获取SFTP配置并构建完整路径
                    sftp_cfg = ctx.config.get("sftp") if isinstance(ctx.config, dict) else {}
                    upload_info = SftpHelper.get_upload_info_with_prefix(upload_info, sftp_cfg)
                elif logger:
                    logger.warning("SFTP上传失败，但继续返回图像信息")
            except Exception as e:
                if logger:
                    logger.warning(f"SFTP上传异常: {e}，但继续返回图像信息")
        else:
            if logger:
                logger.debug("SFTP未启用，跳过图像上传")
        
        # 构建返回数据（SFTP信息可选）
        payload = {
            "has_frame": True,
            "filename": upload_info.get("filename") if upload_info else None,
            "remote_path": upload_info.get("remote_path") if upload_info else None,
            "remote_rel_path": upload_info.get("remote_rel_path") if upload_info else None,
            "remote_file": upload_info.get("remote_file") if upload_info else None,
            "file_size": upload_info.get("file_size") if upload_info else None,
            "image_shape": list(img.shape) if hasattr(img, "shape") else None,
            "image_remote": upload_info,
            "remote_full_path": upload_info.get("remote_full_path") if upload_info else None,
        }

        if logger and upload_info:
            try:
                logger.info(
                    "camera image captured",
                    extra={"filename": upload_info.get("filename"), "remote_path": upload_info.get("remote_path")},
                )
            except Exception:
                try:
                    logger.info(f"camera image captured: {upload_info.get('filename')} -> {upload_info.get('remote_path')}")
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
