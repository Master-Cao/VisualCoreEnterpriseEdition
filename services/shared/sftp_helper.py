#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SFTP辅助工具模块
提供SFTP上传相关的便捷功能
"""

import os
from datetime import datetime
from typing import Optional, Dict


class SftpHelper:
    """
    SFTP辅助工具类
    提供图像上传等便捷方法
    """
    
    @staticmethod
    def upload_image_bytes(
        sftp,
        image_data: bytes,
        prefix: str = "image",
        remote_dir: str = "images"
    ) -> Optional[Dict[str, any]]:
        """
        上传图像字节数据到SFTP服务器
        
        Args:
            sftp: SFTP客户端实例
            image_data: 图像字节数据
            prefix: 文件名前缀，默认"image"
            remote_dir: 远程目录，默认"images"
            
        Returns:
            上传信息字典，包含文件名、路径等信息，失败返回None
            {
                "filename": 文件名,
                "remote_path": 远程目录路径,
                "remote_rel_path": 相对路径,
                "remote_file": 完整文件路径,
                "file_size": 文件大小
            }
        """
        try:
            if not sftp or image_data is None:
                return None
            
            # 生成带时间戳的文件名
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"{prefix}_{ts}.jpg"
            
            # 构建远程路径
            remote_rel = os.path.join(remote_dir, filename).replace("\\", "/")
            
            # 使用SFTP客户端的upload_bytes方法上传
            ok = sftp.upload_bytes(image_data, remote_rel)
            if not ok:
                return None
            
            # 构建返回信息
            remote_path = os.path.dirname(remote_rel).replace("\\", "/")
            if not remote_path.startswith("/"):
                remote_path = f"/{remote_path}" if remote_path else "/"
            if not remote_path.endswith("/"):
                remote_path = f"{remote_path}/"
            remote_file = f"{remote_path.rstrip('/')}/{filename}"
            
            return {
                "filename": filename,
                "remote_path": remote_path,
                "remote_rel_path": remote_rel,
                "remote_file": remote_file,
                "file_size": len(image_data),
            }
            
        except Exception:
            return None
    
    @staticmethod
    def build_full_path(
        remote_rel_path: str,
        sftp_prefix: Optional[str] = None
    ) -> str:
        """
        构建完整的远程路径
        
        Args:
            remote_rel_path: 相对路径（如 "images/test_20231114.jpg"）
            sftp_prefix: SFTP配置中的前缀（如 "http://example.com/files"）
            
        Returns:
            完整路径
        """
        try:
            if not remote_rel_path:
                return ""
            
            rel = str(remote_rel_path)
            
            if sftp_prefix:
                base = str(sftp_prefix)
                # 确保base以/结尾，rel不以/开头
                if not base.endswith("/"):
                    base = f"{base}/"
                if rel.startswith("/"):
                    rel = rel.lstrip("/")
                return f"{base}{rel}"
            else:
                return rel
                
        except Exception:
            return remote_rel_path
    
    @staticmethod
    def get_upload_info_with_prefix(
        upload_info: Dict[str, any],
        sftp_config: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        为上传信息添加完整路径（包含SFTP前缀）
        
        Args:
            upload_info: upload_image_bytes返回的上传信息
            sftp_config: SFTP配置字典
            
        Returns:
            增强后的上传信息（添加了remote_full_path字段）
        """
        try:
            if not upload_info:
                return upload_info
            
            result = dict(upload_info)
            
            # 获取SFTP前缀
            sftp_prefix = None
            if sftp_config and isinstance(sftp_config, dict):
                sftp_prefix = sftp_config.get("prefix")
            
            # 构建完整路径
            remote_rel_path = result.get("remote_rel_path")
            if remote_rel_path:
                result["remote_full_path"] = SftpHelper.build_full_path(
                    remote_rel_path, sftp_prefix
                )
            
            return result
            
        except Exception:
            return upload_info

