# -*- coding: utf-8 -*-

import os
import glob
import shutil
import platform
from datetime import datetime
from typing import Dict, Any

import yaml  # type: ignore

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext


def handle_get_config(req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    cfg = ctx.config or {}
    
    # 获取相机名称
    camera_name = None
    if ctx.camera and hasattr(ctx.camera, 'get_camera_name'):
        try:
            camera_name = ctx.camera.get_camera_name()
        except Exception:
            camera_name = None
    
    # 提取关键配置
    camera_cfg = cfg.get("camera") or {}
    mqtt_cfg = cfg.get("mqtt") or {}
    mqtt_conn = mqtt_cfg.get("connection") or {}
    
    # 构建精简配置
    simplified_config = {
        "roi": cfg.get("roi") or {},
        "camera": {
            "name": camera_name,
            "ip": (camera_cfg.get("connection") or {}).get("ip"),
            "port": (camera_cfg.get("connection") or {}).get("port"),
            "isConnected": ctx.camera.is_connected,
            "enable": camera_cfg.get("enable", False),
        },
        "mqtt": {
            "broker_host": mqtt_conn.get("broker_host"),
            "broker_port": mqtt_conn.get("broker_port"),
        },
    }
    
    # 获取模型信息
    models_info = scan_models(ctx.project_root)
    backend = str(((cfg.get("model") or {}).get("backend") or "")).lower()
    available = filter_models_by_platform(models_info.get("all", []), backend)
    
    data = {
        "config": simplified_config,
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
        cfg = None
        payload = req.data if isinstance(req.data, dict) else {}
        # 兼容字符串形式的 data
        if "config" in payload and isinstance(payload.get("config"), dict):
            cfg = payload.get("config")
        else:
            from json import loads
            raw = payload.get("data") if isinstance(payload.get("data"), str) else None
            if raw:
                parsed = loads(raw)
                if isinstance(parsed, dict) and isinstance(parsed.get("config"), dict):
                    cfg = parsed.get("config")
        if isinstance(cfg, dict):
            merged = backup_and_persist_config(ctx.project_root, cfg)
            ctx.config.clear()
            ctx.config.update(merged)
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


def scan_models(project_root: str) -> Dict[str, list[str]]:
    try:
        models_dir = os.path.join(project_root, "models")
        if not os.path.isdir(models_dir):
            return {"all": []}
        files = [f for f in os.listdir(models_dir) if f.lower().endswith((".rknn", ".pt"))]
        return {"all": sorted(files)}
    except Exception:
        return {"all": []}


def filter_models_by_platform(files: list[str], backend: str) -> list[str]:
    try:
        sys_name = platform.system().lower()
        machine = platform.machine().lower()
        if machine in ("aarch64", "arm64"):
            allowed_exts = [".rknn"]
        elif sys_name in ("windows",) or machine in ("x86_64", "amd64", "x86"):
            allowed_exts = [".pt"]
        else:
            allowed_exts = [".pt"]
        if backend == "rknn":
            allowed_exts = [".rknn"]
        elif backend == "pc":
            allowed_exts = [".pt"]

        def ok(name: str) -> bool:
            ln = name.lower()
            return any(ln.endswith(ext) for ext in allowed_exts)

        return sorted([f for f in files if ok(f)])
    except Exception:
        return sorted(files)


def backup_and_persist_config(project_root: str, updates: dict, max_backups: int = 10) -> dict:
    try:
        cfg_path = os.path.join(project_root, "configs", "config.yaml")
        current: Dict[str, Any] = {}
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        current = loaded
            except Exception:
                current = {}
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{cfg_path}.backup_{ts}"
            try:
                shutil.copy2(cfg_path, backup_path)
            except Exception:
                pass
            try:
                files = sorted(glob.glob(f"{cfg_path}.backup_*"), key=lambda p: os.path.getmtime(p), reverse=True)
                for old in files[max_backups:]:
                    try:
                        os.remove(old)
                    except Exception:
                        pass
            except Exception:
                pass
        merged = _deep_merge_dict(current, updates or {})
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(merged, f, allow_unicode=True, sort_keys=False)
        return merged
    except Exception:
        return updates


def _deep_merge_dict(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base) if isinstance(base, dict) else {}
    for key, value in (updates or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


