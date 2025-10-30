# -*- coding: utf-8 -*-

from typing import Dict, Any

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from .utils import scan_models, filter_models_by_platform, backup_and_persist_config


def handle_get_config(req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    cfg = ctx.config or {}
    models_info = scan_models(ctx.project_root)
    backend = str(((cfg.get("model") or {}).get("backend") or "")).lower()
    available = filter_models_by_platform(models_info.get("all", []), backend)
    data = {
        "config": cfg,
        "models": {"all": models_info.get("all", []), "available": available},
    }
    return MQTTResponse(
        command=VisionCoreCommands.GET_CONFIG.value,
        component="config_manager",
        messageType=MessageType.SUCCESS,
        message="ok",
        data=data,
    )


def handle_save_config(req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    try:
        cfg = (req.data or {}).get("config") if isinstance(req.data, dict) else None
        if isinstance(cfg, dict):
            ctx.config.clear()
            ctx.config.update(cfg)
            backup_and_persist_config(ctx.project_root, ctx.config)
            return MQTTResponse(
                command=VisionCoreCommands.SAVE_CONFIG.value,
                component="config_manager",
                messageType=MessageType.SUCCESS,
                message="saved",
                data={},
            )
        return MQTTResponse(
            command=VisionCoreCommands.SAVE_CONFIG.value,
            component="config_manager",
            messageType=MessageType.ERROR,
            message="invalid_config",
            data={},
        )
    except Exception as e:
        return MQTTResponse(
            command=VisionCoreCommands.SAVE_CONFIG.value,
            component="config_manager",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )


