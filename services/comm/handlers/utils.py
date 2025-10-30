# -*- coding: utf-8 -*-

import os
import glob
import shutil
import platform
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:
    cv2 = None
    np = None


def scan_models(project_root: str) -> Dict[str, List[str]]:
    try:
        models_dir = os.path.join(project_root, "models")
        if not os.path.isdir(models_dir):
            return {"all": []}
        files = [f for f in os.listdir(models_dir) if f.lower().endswith((".rknn", ".pt"))]
        return {"all": sorted(files)}
    except Exception:
        return {"all": []}


def filter_models_by_platform(files: List[str], backend: str) -> List[str]:
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


def backup_and_persist_config(project_root: str, cfg: dict, max_backups: int = 10):
    try:
        if yaml is None:
            return
        cfg_path = os.path.join(project_root, "configs", "config.yaml")
        if os.path.isfile(cfg_path):
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
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    except Exception:
        pass


def frame_to_image(frame: Dict[str, Any]) -> Optional["np.ndarray"]:
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


def sftp_upload_bytes(sftp, data: bytes, project_root: str, prefix: str = "image") -> Optional[Dict[str, Any]]:
    try:
        if not sftp or data is None:
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{prefix}_{ts}.jpg"
        remote_rel = os.path.join("images", filename).replace("\\", "/")
        ok = sftp.upload_bytes(data, remote_rel)
        if ok:
            return {"filename": filename, "remote_path": "/images/", "file_size": len(data)}
        return None
    except Exception:
        return None


