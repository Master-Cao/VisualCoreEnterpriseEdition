#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
坐标处理模块
负责从检测结果计算3D坐标和角度
专注于坐标计算，不涉及ROI过滤等业务逻辑
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import math


class CoordinateProcessor:
    """
    坐标处理器
    专注于3D坐标计算：像素坐标 + 深度 → 相机坐标 → 机器人坐标
    
    职责：
    - 3D坐标计算（畸变校正、深度投影）
    - 坐标系变换（相机坐标→机器人坐标）
    - 深度值稳健估计
    
    不包含：
    - ROI过滤（由 RoiProcessor 负责）
    - 目标选择（由 RoiProcessor 负责）
    - 可视化（由 DetectionVisualizer 负责）
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
    def calculate_coordinate_for_detection(
        cls,
        detection: Any,
        depth_data: List[float],
        camera_params: Any,
        transformation_matrix: Optional[np.ndarray] = None
    ) -> Optional[Dict[str, Any]]:
        """
        为单个检测框计算3D坐标
        
        Args:
            detection: 单个检测框对象
            depth_data: 深度数据（一维数组）
            camera_params: 相机参数对象
            transformation_matrix: 坐标变换矩阵（相机→机器人）
        
        Returns:
            包含坐标信息的字典：
            {
                'center': [x, y],           # 像素中心点
                'depth': float,             # 深度值(mm)
                'camera_3d': [x, y, z],    # 相机坐标系3D坐标
                'robot_3d': [x, y, z],     # 机器人坐标系3D坐标
                'area': float,              # mask面积或bbox面积
                'score': float,             # 置信度
                'class_id': int             # 类别ID
            }
            计算失败返回None
        """
        try:
            # 提取相机参数
            width = camera_params.width
            height = camera_params.height
            cx, cy = camera_params.cx, camera_params.cy
            fx, fy = camera_params.fx, camera_params.fy
            k1, k2 = camera_params.k1, camera_params.k2
            f2rc = camera_params.f2rc
            
            # 相机到世界坐标系的变换矩阵（内置于相机参数中）
            m_c2w = None
            if hasattr(camera_params, 'cam2worldMatrix') and len(camera_params.cam2worldMatrix) == 16:
                m_c2w = np.array(camera_params.cam2worldMatrix).reshape(4, 4)
            
            # 计算中心点
            center_x = 0.5 * (float(detection.xmin) + float(detection.xmax))
            center_y = 0.5 * (float(detection.ymin) + float(detection.ymax))
            
            # 获取mask面积
            mask = getattr(detection, 'seg_mask', None)
            if mask is not None:
                area = float(mask.sum())
            else:
                # 没有mask，使用矩形面积
                area = float((detection.xmax - detection.xmin) * (detection.ymax - detection.ymin))
            
            # 获取深度值（使用稳健估计）
            cx_int = int(round(center_x))
            cy_int = int(round(center_y))
            
            # 检查 depth_data 格式
            if not isinstance(depth_data, (list, tuple)):
                import sys
                print(f"[CoordinateProcessor] depth_data 类型错误: {type(depth_data)}", file=sys.stderr)
                return None
            
            depth = cls._get_robust_depth_at_point(cx_int, cy_int, depth_data, width, height, radius=1)
            
            if depth <= 0:
                import sys
                print(f"[CoordinateProcessor] 深度值无效: depth={depth}, center=({cx_int},{cy_int})", file=sys.stderr)
                return None
            
            # 第一步：计算3D世界坐标（相机已通过 m_c2w 转换为世界坐标）
            # 注意：这里返回的是世界坐标，不是相机坐标
            success, world3d = cls._calculate_3d_fast(
                center_x, center_y, depth,
                cx, cy, fx, fy, k1, k2, f2rc, m_c2w
            )
            
            if not success:
                return None
            
            # 第二步：转换到机器人坐标系（仅当提供了标定矩阵时）
            # 注意：在 VisualCoreEnterpriseEdition 中，第二步转换在 handle_catch 中完成
            # 这里保留是为了兼容直接传入 transformation_matrix 的情况
            if transformation_matrix is not None:
                robot3d = cls._transform_point_fast(world3d, transformation_matrix)
                if robot3d is None:
                    robot3d = world3d  # 回退到世界坐标
            else:
                robot3d = world3d  # 不进行第二步转换，直接使用世界坐标
            
            return {
                'center': [center_x, center_y],
                'depth': depth,
                'camera_3d': world3d,  # 世界坐标（相机内部已通过 cam2worldMatrix 转换）
                'robot_3d': robot3d,   # 机器人坐标（如果提供了 transformation_matrix）或世界坐标
                'area': area,
                'score': float(detection.score),
                'class_id': int(detection.class_id)
            }
            
        except Exception:
            return None
    
   