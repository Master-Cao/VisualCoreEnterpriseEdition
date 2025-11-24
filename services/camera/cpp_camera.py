import numpy as np
from typing import Any, Dict, Optional

import os
import sys
try:
    import vc_camera_cpp
except ImportError:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        os.path.dirname(__file__),  # 添加这一行：cpp_camera.py所在的目录
        os.path.join(base, "cpp", "build", "Release"),
        os.path.join(base, "cpp", "build"),
        os.path.join(base, "cpp", "dist"),
        os.path.abspath(os.path.join(base, "..")),
    ]
    for p in candidates:
        if p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)
    import vc_camera_cpp


class CppCamera:
    def __init__(self, ip: str, port: int = 2122, use_single_step: bool = True, logger: Optional[Any] = None, login_attempts=None):
        self._ip = ip
        self._port = port
        self._use_single_step = use_single_step
        self._logger = logger
        self._cam = vc_camera_cpp.VisionaryCamera(ip, int(port), bool(use_single_step))
        self.is_connected = False
        self._last_frame_num = 0  # 记录上一帧号（用于检测旧帧复用）
        self._frame_retry_enabled = True  # 是否启用帧号验证和重试

    def connect(self) -> bool:
        ok = self._cam.connect()
        self.is_connected = bool(ok)
        return self.is_connected

    def disconnect(self):
        try:
            self._cam.disconnect()
        finally:
            self.is_connected = False

    def get_frame(self, depth: bool = True, intensity: bool = True, camera_params: bool = True) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        
        # 获取帧数据
        d = self._cam.get_frame()
        if d is None:
            return None
        
        # 帧号验证：检测旧帧复用问题（特别是在ARM平台上）
        current_frame_num = d.get("frame_num", 0)
        timestamp_ms = d.get("timestamp_ms", 0)
        
        if self._frame_retry_enabled and current_frame_num > 0:
            if current_frame_num <= self._last_frame_num:
                # 检测到旧帧复用（帧号未递增）
                if self._logger:
                    self._logger.warning(
                        f"检测到旧帧复用 | frame_num={current_frame_num} <= last={self._last_frame_num}, "
                        f"timestamp={timestamp_ms}ms | 尝试重新获取"
                    )
                # 重新获取一次（通常能获取到新帧）
                d_retry = self._cam.get_frame()
                if d_retry is not None:
                    retry_frame_num = d_retry.get("frame_num", 0)
                    retry_timestamp = d_retry.get("timestamp_ms", 0)
                    if retry_frame_num > self._last_frame_num:
                        # 重试成功，获取到新帧
                        if self._logger:
                            self._logger.info(
                                f"✓ 重试成功 | 新帧 frame_num={retry_frame_num}, "
                                f"timestamp={retry_timestamp}ms"
                            )
                        d = d_retry
                        current_frame_num = retry_frame_num
                    else:
                        # 重试仍然是旧帧，记录警告但继续使用
                        if self._logger:
                            self._logger.warning(
                                f"✗ 重试后仍为旧帧 | frame_num={retry_frame_num}, "
                                f"timestamp={retry_timestamp}ms | 继续使用"
                            )
            
            # 更新最后的帧号
            self._last_frame_num = current_frame_num
        
        # 提取所需数据
        img = d.get("intensity_image") if intensity else None
        dep = d.get("depthmap") if depth else None
        params_obj = d.get("cameraParams") if camera_params else None
        if dep is not None and isinstance(dep, np.ndarray):
            dep = dep.tolist()
        
        return {
            "intensity_image": img, 
            "depthmap": dep, 
            "cameraParams": params_obj,
            "frame_num": current_frame_num,
            "timestamp_ms": timestamp_ms
        }

    @property
    def healthy(self) -> bool:
        try:
            return bool(self._cam.healthy())
        except Exception:
            return False
