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
    selected_model = cfg.get("model", {}).get("model_name", None)
    data = {
        "config": simplified_config,
        "models": {"all": models_info.get("all", []), "available": available, "selected": selected_model},
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
        payload = req.data if isinstance(req.data, dict) else {}
        
        # 解析 payload
        config_data = None
        models_data = None
        
        if "config" in payload:
            config_data = payload.get("config")
        if "models" in payload:
            models_data = payload.get("models")
            
        # 兼容字符串形式的 data
        if not config_data or not models_data:
            from json import loads
            raw = payload.get("data") if isinstance(payload.get("data"), str) else None
            if raw:
                parsed = loads(raw)
                if isinstance(parsed, dict):
                    config_data = config_data or parsed.get("config")
                    models_data = models_data or parsed.get("models")
        
        # 构建部分更新配置
        partial_updates = {}
        
        # 1. 更新 ROI 配置
        if isinstance(config_data, dict) and "roi" in config_data:
            partial_updates["roi"] = config_data["roi"]
        
        # 2. 更新 model 配置
        if isinstance(models_data, dict) and "selected" in models_data:
            model_name = models_data["selected"]
            if model_name:
                model_file = ctx.config.get("model", {}).get("model_file", "models")
                model_path = os.path.join(model_file, model_name).replace("\\", "/")
                partial_updates["model"] = {
                    "model_name": model_name,
                    "path": model_path
                }
        
        # 如果有更新内容，则保存
        if partial_updates:
            merged = backup_and_persist_config(ctx.project_root, partial_updates)
            ctx.config.clear()
            ctx.config.update(merged)
            
            # 触发系统重启以应用新配置
            if ctx.initializer:
                try:
                    if ctx.logger:
                        ctx.logger.info("配置已更新，准备重启系统以应用新配置...")
                    ctx.initializer.restart(new_config=merged, delay=2.0)
                except Exception as restart_err:
                    if ctx.logger:
                        ctx.logger.error(f"触发系统重启失败: {restart_err}")
            
            return MQTTResponse(
                command=VisionCoreCommands.SAVE_CONFIG.value,
                component="config_manager",
                messageType=MessageType.SUCCESS,
                message="saved",
                data={"restart_scheduled": True, "restart_delay": 2.0},
            )
        
        return MQTTResponse(
            command=VisionCoreCommands.SAVE_CONFIG.value,
            component="config_manager",
            messageType=MessageType.ERROR,
            message="no_valid_updates",
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
            
            # 创建备份目录
            backup_dir = os.path.join(project_root, "configs", "config_backup")
            os.makedirs(backup_dir, exist_ok=True)
            
            # 备份文件名：config.yaml.backup_YYYYMMDD_HHMMSS
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config.yaml.backup_{ts}"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            try:
                shutil.copy2(cfg_path, backup_path)
            except Exception:
                pass
            
            # 清理旧备份（在 config_back 文件夹中）
            try:
                backup_pattern = os.path.join(backup_dir, "config.yaml.backup_*")
                files = sorted(glob.glob(backup_pattern), key=lambda p: os.path.getmtime(p), reverse=True)
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


