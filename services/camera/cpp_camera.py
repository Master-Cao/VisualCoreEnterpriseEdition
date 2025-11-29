import numpy as np
from typing import Any, Dict, Optional

import os
import sys
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
        self._released = False  # 防止重复释放

    def connect(self) -> bool:
        ok = self._cam.connect()
        self.is_connected = bool(ok)
        return self.is_connected

    def disconnect(self):
        """断开连接（不释放C++对象）"""
        if self._released:
            return
        try:
            if hasattr(self, '_cam') and self._cam and self.is_connected:
                self._cam.disconnect()
                if self._logger:
                    self._logger.debug("C++相机已断开连接")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"断开C++相机连接时出错: {e}")
        finally:
            self.is_connected = False
    
    def release(self):
        """显式释放所有资源（包括C++对象）"""
        if self._released:
            return
        
        self._released = True
        
        try:
            # 1. 先断开连接
            if hasattr(self, 'is_connected') and self.is_connected:
                if hasattr(self, '_cam') and self._cam:
                    try:
                        self._cam.disconnect()
                    except Exception:
                        pass
                self.is_connected = False
            
            # 2. 清理引用
            self._last_frame_num = 0
            
            # 3. 删除C++对象（不再调用disconnect）
            if hasattr(self, '_cam') and self._cam:
                try:
                    # 直接删除，让C++析构函数处理清理
                    del self._cam
                except Exception:
                    pass
                finally:
                    self._cam = None
            
            if self._logger:
                self._logger.info("✓ C++相机资源已释放")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"释放C++相机资源时出错: {e}")
    
    def __del__(self):
        """析构函数：确保C++资源被释放"""
        try:
            if not self._released:
                self.release()
        except Exception:
            pass

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
        
        # 之前的 dep.tolist() 会导致 256x256=65536 个元素的转换，耗时约 30-50ms
        # 如果下游需要 list，在使用时再转换
        
        return {
            "intensity_image": img, 
            "depthmap": dep,  # 保持 numpy.ndarray 格式
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

# 兼容顶级导入名：允许通过 'cpp_camera' 导入本模块
try:
    import sys as _sys
    _sys.modules.setdefault("cpp_camera", _sys.modules[__name__])
except Exception:
    pass
