#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
坐标处理模块
负责从检测结果计算3D坐标和角度
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import math


class CoordinateProcessor:
    """
    坐标处理器
    负责从检测结果、深度数据和相机参数计算3D坐标
    """
    
    @staticmethod
    def _calculate_3d_fast(x: float, y: float, depth: float, 
                          cx: float, cy: float, fx: float, fy: float,
                          k1: float, k2: float, f2rc: float, 
                          m_c2w: Optional[np.ndarray]) -> Tuple[bool, List[float]]:
        """
        快速3D坐标计算
        
        Args:
            x, y: 像素坐标
            depth: 深度值
            cx, cy: 相机主点
            fx, fy: 相机焦距
            k1, k2: 径向畸变系数
            f2rc: 相机到参考点距离
            m_c2w: 相机到世界坐标系的变换矩阵 (4x4)
        
        Returns:
            (success, [x, y, z]): 成功标志和3D坐标
        """
        try:
            # 计算相机坐标系下的坐标
            xp = (cx - x) / fx
            yp = (cy - y) / fy
            
            # 径向畸变校正
            r2 = xp * xp + yp * yp
            k = 1 + k1 * r2 + k2 * r2 * r2
            
            xd = xp * k
            yd = yp * k
            
            # 3D坐标计算
            s0_inv = 1.0 / math.sqrt(xd * xd + yd * yd + 1)
            x_cam = xd * depth * s0_inv
            y_cam = yd * depth * s0_inv
            z_cam = depth * s0_inv - f2rc
            
            # 世界坐标系转换（如果提供了变换矩阵）
            if m_c2w is not None:
                x_world = m_c2w[0, 3] + z_cam * m_c2w[0, 2] + y_cam * m_c2w[0, 1] + x_cam * m_c2w[0, 0]
                y_world = m_c2w[1, 3] + z_cam * m_c2w[1, 2] + y_cam * m_c2w[1, 1] + x_cam * m_c2w[1, 0]
                z_world = m_c2w[2, 3] + z_cam * m_c2w[2, 2] + y_cam * m_c2w[2, 1] + x_cam * m_c2w[2, 0]
                return True, [x_world, y_world, z_world]
            else:
                return True, [x_cam, y_cam, z_cam]
                
        except Exception:
            return False, [0.0, 0.0, 0.0]
    
    @staticmethod
    def _transform_point_fast(camera_point: List[float], 
                             transformation_matrix: Optional[np.ndarray]) -> Optional[List[float]]:
        """
        快速坐标变换（相机坐标→机器人坐标）
        
        Args:
            camera_point: 相机坐标系下的点 [x, y, z]
            transformation_matrix: 4x4变换矩阵
        
        Returns:
            机器人坐标系下的点 [x, y, z]，失败返回None
        """
        if transformation_matrix is None:
            return camera_point
        
        try:
            x, y, z = camera_point
            T = transformation_matrix
            
            # 齐次坐标变换
            x_robot = T[0, 0] * x + T[0, 1] * y + T[0, 2] * z + T[0, 3]
            y_robot = T[1, 0] * x + T[1, 1] * y + T[1, 2] * z + T[1, 3]
            z_robot = T[2, 0] * x + T[2, 1] * y + T[2, 2] * z + T[2, 3]
            w = T[3, 0] * x + T[3, 1] * y + T[3, 2] * z + T[3, 3]
            
            if w != 0:
                return [x_robot / w, y_robot / w, z_robot / w]
            else:
                return [x_robot, y_robot, z_robot]
                
        except Exception:
            return None
    
    @staticmethod
    def _get_robust_depth_at_point(x: int, y: int, depth_data: List[float], 
                                   width: int, height: int, radius: int = 1) -> float:
        """
        获取指定点的稳定深度值，通过邻近像素平均值提高稳定性
        
        Args:
            x, y: 目标点坐标
            depth_data: 深度数据数组
            width, height: 图像尺寸
            radius: 邻近像素搜索半径
        
        Returns:
            稳定的深度值，无法获取有效深度则返回0
        """
        valid_depths = []
        
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                px, py = x + dx, y + dy
                
                if 0 <= px < width and 0 <= py < height:
                    depth_index = py * width + px
                    if depth_index < len(depth_data):
                        depth = depth_data[depth_index]
                        if depth > 0:
                            valid_depths.append(depth)
        
        if valid_depths:
            return sum(valid_depths) / len(valid_depths)
        else:
            return 0.0
    
    @classmethod
    def process_detection_to_coordinates(
        cls,
        detection_boxes: List[Any],
        depth_data: List[float],
        camera_params: Any,
        roi_config: Optional[Dict],
        transformation_matrix: Optional[np.ndarray] = None
    ) -> Optional[Dict[str, Any]]:
        """
        处理检测结果，计算最佳目标的3D坐标
        
        选择策略：
        1. 过滤ROI外的目标（如果启用ROI）
        2. 按mask面积选择最大的目标
        
        Args:
            detection_boxes: 检测框列表
            depth_data: 深度数据
            camera_params: 相机参数
            roi_config: ROI配置
            transformation_matrix: 坐标变换矩阵（相机→机器人）
        
        Returns:
            包含最佳目标信息的字典，无有效目标返回None
        """
        if not detection_boxes or not depth_data or not camera_params:
            return None
        
        # 提取相机参数
        width = camera_params.width
        height = camera_params.height
        cx, cy = camera_params.cx, camera_params.cy
        fx, fy = camera_params.fx, camera_params.fy
        k1, k2 = camera_params.k1, camera_params.k2
        f2rc = camera_params.f2rc
        
        # 相机到世界坐标系的变换矩阵
        m_c2w = None
        if hasattr(camera_params, 'cam2worldMatrix') and len(camera_params.cam2worldMatrix) == 16:
            m_c2w = np.array(camera_params.cam2worldMatrix).reshape(4, 4)
        
        # 构建深度二维数组
        try:
            depth_np = np.array(depth_data, dtype=np.float32).reshape((height, width))
        except Exception:
            depth_np = None
        
        if depth_np is None:
            return None
        
        # 按ROI过滤候选目标
        candidates = []
        for idx, box in enumerate(detection_boxes):
            # 计算中心点
            center_x = 0.5 * (float(box.xmin) + float(box.xmax))
            center_y = 0.5 * (float(box.ymin) + float(box.ymax))
            
            # ROI过滤
            if roi_config and roi_config.get('enabled'):
                if not cls._is_point_in_roi(center_x, center_y, roi_config):
                    continue
            
            # 获取mask面积
            mask = getattr(box, 'seg_mask', None)
            if mask is not None:
                area = float(mask.sum())
            else:
                # 没有mask，使用矩形面积
                area = float((box.xmax - box.xmin) * (box.ymax - box.ymin))
            
            # 获取深度值（使用稳健估计）
            cx_int = int(round(center_x))
            cy_int = int(round(center_y))
            depth = cls._get_robust_depth_at_point(cx_int, cy_int, depth_data, width, height, radius=1)
            
            if depth <= 0:
                continue
            
            # 计算3D相机坐标
            success, cam3d = cls._calculate_3d_fast(
                center_x, center_y, depth,
                cx, cy, fx, fy, k1, k2, f2rc, m_c2w
            )
            
            if not success:
                continue
            
            # 转换到机器人坐标系
            robot3d = cls._transform_point_fast(cam3d, transformation_matrix)
            if robot3d is None:
                robot3d = cam3d  # 回退到相机坐标
            
            candidates.append({
                'idx': idx,
                'box': box,
                'center': [center_x, center_y],
                'depth': depth,
                'camera_3d': cam3d,
                'robot_3d': robot3d,
                'area': area,
                'score': box.score,
                'class_id': box.class_id
            })
        
        if not candidates:
            return None
        
        # 选择面积最大的目标
        best = max(candidates, key=lambda c: c['area'])
        
        return {
            'target_id': best['idx'] + 1,
            'center': best['center'],
            'camera_3d': best['camera_3d'],
            'robot_3d': best['robot_3d'],
            'depth': best['depth'],
            'angle': 0.0,  # 分割模型不提供角度
            'score': best['score'],
            'class_id': best['class_id'],
            'area': best['area'],
            'original_box': best['box']
        }
    
    @staticmethod
    def _is_point_in_roi(x: float, y: float, roi_config: Dict) -> bool:
        """
        检查点是否在矩形ROI内
        
        Args:
            x, y: 点坐标
            roi_config: ROI配置
        
        Returns:
            点是否在ROI内
        """
        x1 = roi_config.get('x1')
        y1 = roi_config.get('y1')
        x2 = roi_config.get('x2')
        y2 = roi_config.get('y2')
        
        if x1 is None or y1 is None or x2 is None or y2 is None:
            return True
        
        return x1 <= x <= x2 and y1 <= y <= y2

