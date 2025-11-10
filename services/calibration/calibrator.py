#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
坐标系标定器
XY使用仿射变换，Z使用线性映射，合成4x4变换矩阵
移植自 VisionCore/tools/detect_black_block_to_xy.py
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional


def fit_affine_xy(world_xy: List[Tuple[float, float]], 
                  robot_xy: List[Tuple[float, float]]) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    拟合XY平面的仿射变换
    
    Args:
        world_xy: 世界坐标系的XY坐标列表 [(xw, yw), ...]
        robot_xy: 机器人坐标系的XY坐标列表 [(xr, yr), ...]
    
    Returns:
        (A, stats): A为2x3仿射矩阵，stats包含RMSE统计
    """
    if len(world_xy) != len(robot_xy):
        raise ValueError("世界坐标和机器人坐标数量必须相同")
    
    if len(world_xy) < 3:
        raise ValueError("至少需要3组对应点进行XY仿射拟合")
    
    X = np.array(world_xy, dtype=np.float64)
    Y = np.array(robot_xy, dtype=np.float64)
    
    # 设计矩阵 H: [xw, yw, 1]
    ones = np.ones((X.shape[0], 1), dtype=np.float64)
    H = np.hstack([X, ones])  # (N,3)
    
    # 分别拟合 Xr, Yr
    a_x, _, _, _ = np.linalg.lstsq(H, Y[:, 0], rcond=None)  # (3,)
    a_y, _, _, _ = np.linalg.lstsq(H, Y[:, 1], rcond=None)  # (3,)
    
    # 预测与RMSE
    pred_x = H @ a_x
    pred_y = H @ a_y
    rmse_x = float(np.sqrt(np.mean((pred_x - Y[:, 0]) ** 2)))
    rmse_y = float(np.sqrt(np.mean((pred_y - Y[:, 1]) ** 2)))
    
    # 2x3矩阵: [a11, a12, a13]
    #          [a21, a22, a23]
    A = np.vstack([a_x, a_y])  # shape (2,3)
    
    return A, {'rmse_x': rmse_x, 'rmse_y': rmse_y}


def fit_linear_z(z_world: List[float], 
                 z_robot: List[float]) -> Tuple[float, float, Dict[str, float]]:
    """
    拟合Z轴的线性映射: zr = alpha * zw + beta
    
    Args:
        z_world: 世界坐标系的Z坐标列表
        z_robot: 机器人坐标系的Z坐标列表
    
    Returns:
        (alpha, beta, stats): 线性系数和RMSE统计
    """
    if len(z_world) != len(z_robot):
        raise ValueError("世界Z坐标和机器人Z坐标数量必须相同")
    
    if len(z_world) < 2:
        raise ValueError("至少需要2组对应点进行Z线性拟合")
    
    ZW = np.array(z_world, dtype=np.float64)
    ZR = np.array(z_robot, dtype=np.float64)
    
    # H = [zw, 1]
    H = np.vstack([ZW, np.ones_like(ZW)]).T  # (N,2)
    coeff, _, _, _ = np.linalg.lstsq(H, ZR, rcond=None)  # (2,) -> alpha, beta
    
    alpha = float(coeff[0])
    beta = float(coeff[1])
    
    pred = H @ coeff
    rmse_z = float(np.sqrt(np.mean((pred - ZR) ** 2)))
    
    return alpha, beta, {'rmse_z': rmse_z}


def compose_affine_4x4_from_xy_and_z(A2x3: Optional[np.ndarray], 
                                      alpha: Optional[float], 
                                      beta: Optional[float]) -> np.ndarray:
    """
    从XY仿射变换和Z线性映射合成4x4齐次变换矩阵
    
    矩阵形式:
    [ a11 a12  0  a13 ]
    [ a21 a22  0  a23 ]
    [  0   0   α   β  ]
    [  0   0   0   1  ]
    
    Args:
        A2x3: XY平面的2x3仿射矩阵，None则使用单位变换
        alpha: Z轴的缩放系数，None则使用1.0
        beta: Z轴的偏移量，None则使用0.0
    
    Returns:
        4x4齐次变换矩阵
    """
    M = np.eye(4, dtype=np.float64)
    
    if A2x3 is not None:
        M[0, 0] = float(A2x3[0, 0])
        M[0, 1] = float(A2x3[0, 1])
        M[0, 3] = float(A2x3[0, 2])
        M[1, 0] = float(A2x3[1, 0])
        M[1, 1] = float(A2x3[1, 1])
        M[1, 3] = float(A2x3[1, 2])
    
    if alpha is not None:
        M[2, 2] = float(alpha)
    if beta is not None:
        M[2, 3] = float(beta)
    
    return M


def save_transformation_matrix(path: Path,
                               matrix_4x4: np.ndarray,
                               A2x3: Optional[np.ndarray] = None,
                               alpha: Optional[float] = None,
                               beta: Optional[float] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    保存变换矩阵到JSON文件
    
    Args:
        path: 输出文件路径
        matrix_4x4: 4x4变换矩阵
        A2x3: XY仿射矩阵（可选，用于兼容）
        alpha: Z线性系数（可选，用于兼容）
        beta: Z线性偏移（可选，用于兼容）
        metadata: 额外的元数据
    """
    data = {
        'matrix': matrix_4x4.tolist(),
        'calibration_datetime': datetime.now().isoformat(),
        'transformation_type': 'affine_xy_linear_z',
        'matrix_size': '4x4'
    }
    
    # 保存XY和Z的原始参数（用于调试和兼容）
    if A2x3 is not None:
        data['matrix_xy'] = A2x3.tolist()
    if alpha is not None and beta is not None:
        data['z_mapping'] = {'alpha': float(alpha), 'beta': float(beta)}
    
    # 添加用户元数据
    if metadata:
        data.update(metadata)
    
    # 保存到文件
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_transformation_matrix(path: Path) -> Optional[np.ndarray]:
    """
    从JSON文件加载变换矩阵
    
    Args:
        path: 变换矩阵文件路径
    
    Returns:
        4x4变换矩阵，失败返回None
    """
    if not path.exists():
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        matrix = data.get('matrix')
        if not matrix or len(matrix) != 4:
            return None
        
        if not all(isinstance(row, list) and len(row) == 4 for row in matrix):
            return None
        
        return np.array(matrix, dtype=np.float64)
    
    except Exception:
        return None


def calibrate_from_points(world_points: List[Tuple[float, float, float]],
                          robot_points: List[Tuple[float, float, float]],
                          output_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    从世界坐标和机器人坐标执行完整标定流程
    
    Args:
        world_points: 世界坐标系点列表 [(xw, yw, zw), ...]
        robot_points: 机器人坐标系点列表 [(xr, yr, zr), ...]
        output_path: 输出文件路径，None则不保存
    
    Returns:
        标定结果字典，包含矩阵和统计信息
    """
    if len(world_points) != len(robot_points):
        raise ValueError("世界坐标和机器人坐标数量必须相同")
    
    if len(world_points) < 3:
        raise ValueError("至少需要3组对应点进行标定")
    
    # 分离XY和Z
    world_xy = [(p[0], p[1]) for p in world_points]
    robot_xy = [(p[0], p[1]) for p in robot_points]
    world_z = [p[2] for p in world_points]
    robot_z = [p[2] for p in robot_points]
    
    # XY仿射拟合
    A2x3, xy_stats = fit_affine_xy(world_xy, robot_xy)
    
    # Z线性拟合
    alpha, beta, z_stats = fit_linear_z(world_z, robot_z)
    
    # 合成4x4矩阵
    matrix_4x4 = compose_affine_4x4_from_xy_and_z(A2x3, alpha, beta)
    
    # 准备元数据
    metadata = {
        'calibration_points_count': len(world_points),
        'xy_rmse_x': xy_stats['rmse_x'],
        'xy_rmse_y': xy_stats['rmse_y'],
        'z_rmse': z_stats['rmse_z'],
        'overall_rmse_2d': float(np.sqrt(xy_stats['rmse_x']**2 + xy_stats['rmse_y']**2))
    }
    
    # 保存到文件
    if output_path:
        save_transformation_matrix(output_path, matrix_4x4, A2x3, alpha, beta, metadata)
    
    return {
        'matrix': matrix_4x4,
        'matrix_xy': A2x3,
        'z_alpha': alpha,
        'z_beta': beta,
        'metadata': metadata
    }

