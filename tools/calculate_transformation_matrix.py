"""
坐标系变换矩阵计算工具
用于根据相机世界坐标系和机器人坐标系的映射关系计算变换矩阵

使用方法：
1. 在下方填入 XY 平面的坐标对（至少3组）：
   - CAMERA_POINTS_XY: 相机世界坐标系的 (X, Y) 坐标
   - ROBOT_POINTS_XY: 对应的机器人坐标系的 (X, Y) 坐标
   
2. 在下方填入 Z 轴的校准对（可选，至少2组）：
   - Z_CALIBRATION_PAIRS: (相机世界坐标Zw, 机器人坐标Zr) 的配对列表

3. 运行脚本：python calculate_transformation_matrix.py

4. 查看计算结果和精度验证，选择是否保存到 Config/transformation_matrix.json

说明：
- XY平面使用仿射变换（6参数）
- Z轴使用线性映射（2参数）: Zr = alpha * Zw + beta
- Z轴校准可以使用不同于XY的点集，也可以留空只计算XY变换
"""

import numpy as np
import json
from datetime import datetime
from pathlib import Path


# ============================================================
# 请在此处填入坐标数据
# ============================================================

# 用于XY平面仿射变换的坐标对
# 相机世界坐标系的点 (X, Y)
CAMERA_POINTS_XY = [
    # 示例数据（请替换为实际数据）
    [121.18, 48.57, 657.93],
    [253.60, -59.87, 658.54],
    [196.16, 45.36, 666.31],
    [108.54, -39.48, 664.09],
    [52.82, 46.76, 670.16],
    [-42.43, -236.96, 662.47],
    [70.63, -149.94, 664.57],
    [-87.27, -236.83, 662.33],
    [-72.14, -138.84, 664.08],
    [30.06, -193.90, 664.52],
    [-76.80, -54.18, 663.00],
    [170.40, 63.82, 666.07],
    [241.40, -28.09, 659.75],
    [183.13, 8.38, 658.73],
    [228.47, -20.03, 664.36],
    # 在此输入你的相机坐标 (Xw, Yw)
    [238.21, 59.55, 661.08],
    [137.50, -6.30, 666.43],
    [249.73, -60.94, 660.29]
]

# 机器人坐标系的点 (X, Y) - 顺序需与相机坐标一一对应
ROBOT_POINTS_XY = [
    [191.675,-263.794],
    [320.312,-375.7],
    [197.398, -338.106],
    [307.139, -220.403],
    [199.343, -194.925],
    [496.454, -57.100],
    [411.657, -188.073],
    [497.744, -27.237],
    [399.681, -35.854],
    [457.08, -149.27],
    [314.694,-35.274],
    [178.107, -302.999],
    [297.074, -358.294],
    [261.386, -298.976],
    # 示例数据（请替换为实际数据）
    [284.464, -341.244],
    [174.503, -379.53],
    [268.516,-252.387],
    [325.881, -361.406]
    # [100.0, 200.0],
    # [150.0, 180.0],
    # [200.0, 220.0],
    # [250.0, 210.0],
    
    # 在此输入你的机器人坐标 (Xr, Yr)
    
]

# 用于Z轴线性映射的校准对
# 格式：[(相机世界坐标Zw, 机器人坐标Zr), ...]
Z_CALIBRATION_PAIRS = [
    # 示例数据（请替换为实际数据）
    (665.0, -80),
    (655, -70),
    (644, -60),
    (636, -51),
    (625, -40),
    (615, -30),
    # 在此输入你的Z轴校准对 (Zw, Zr)
    
]

# ============================================================
# 以下是计算代码，无需修改
# ============================================================


def calculate_affine_transform_2d(src_points, dst_points):
    """
    计算2D仿射变换矩阵
    
    参数:
        src_points: 源坐标点列表 [[x1,y1], [x2,y2], ...]
        dst_points: 目标坐标点列表 [[x1,y1], [x2,y2], ...]
    
    返回:
        matrix: 2x3仿射变换矩阵
        rmse_x: X方向的均方根误差
        rmse_y: Y方向的均方根误差
    """
    src_points = np.array(src_points, dtype=np.float64)
    dst_points = np.array(dst_points, dtype=np.float64)
    
    n = len(src_points)
    
    # 构建方程组 [x, y, 1, 0, 0, 0] * [a, b, c, d, e, f]^T = [x', y']
    # 对于X坐标: x' = a*x + b*y + c
    # 对于Y坐标: y' = d*x + e*y + f
    
    A = np.zeros((2*n, 6))
    b = np.zeros(2*n)
    
    for i in range(n):
        # X方程
        A[2*i] = [src_points[i, 0], src_points[i, 1], 1, 0, 0, 0]
        b[2*i] = dst_points[i, 0]
        
        # Y方程
        A[2*i+1] = [0, 0, 0, src_points[i, 0], src_points[i, 1], 1]
        b[2*i+1] = dst_points[i, 1]
    
    # 最小二乘求解
    params, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
    
    # 构建2x3矩阵
    matrix = np.array([
        [params[0], params[1], params[2]],
        [params[3], params[4], params[5]]
    ])
    
    # 计算RMSE
    predicted = []
    for point in src_points:
        x_pred = params[0] * point[0] + params[1] * point[1] + params[2]
        y_pred = params[3] * point[0] + params[4] * point[1] + params[5]
        predicted.append([x_pred, y_pred])
    
    predicted = np.array(predicted)
    errors = dst_points - predicted
    
    rmse_x = np.sqrt(np.mean(errors[:, 0]**2))
    rmse_y = np.sqrt(np.mean(errors[:, 1]**2))
    
    return matrix, rmse_x, rmse_y


def calculate_linear_z_mapping(src_z, dst_z):
    """
    计算Z轴的线性映射关系: dst_z = alpha * src_z + beta
    
    参数:
        src_z: 源Z坐标列表
        dst_z: 目标Z坐标列表
    
    返回:
        alpha: 斜率
        beta: 截距
        rmse: 均方根误差
    """
    src_z = np.array(src_z, dtype=np.float64)
    dst_z = np.array(dst_z, dtype=np.float64)
    
    # 最小二乘拟合
    A = np.vstack([src_z, np.ones(len(src_z))]).T
    alpha, beta = np.linalg.lstsq(A, dst_z, rcond=None)[0]
    
    # 计算RMSE
    predicted = alpha * src_z + beta
    rmse = np.sqrt(np.mean((dst_z - predicted)**2))
    
    return alpha, beta, rmse


def build_transformation_matrix_4x4(matrix_xy, z_alpha=None, z_beta=None):
    """
    构建4x4齐次变换矩阵
    
    参数:
        matrix_xy: 2x3 XY平面仿射变换矩阵
        z_alpha: Z轴缩放因子（可选）
        z_beta: Z轴偏移（可选）
    
    返回:
        4x4齐次变换矩阵
    """
    matrix_4x4 = np.eye(4, dtype=np.float64)
    
    # 填充XY变换
    matrix_4x4[0, 0] = matrix_xy[0, 0]
    matrix_4x4[0, 1] = matrix_xy[0, 1]
    matrix_4x4[0, 3] = matrix_xy[0, 2]
    matrix_4x4[1, 0] = matrix_xy[1, 0]
    matrix_4x4[1, 1] = matrix_xy[1, 1]
    matrix_4x4[1, 3] = matrix_xy[1, 2]
    
    # 填充Z变换（如果有）
    if z_alpha is not None and z_beta is not None:
        matrix_4x4[2, 2] = z_alpha
        matrix_4x4[2, 3] = z_beta
    
    return matrix_4x4


def save_transformation_matrix(matrix_4x4, matrix_xy, z_mapping, 
                               calibration_info, output_path):
    """
    保存变换矩阵到JSON文件
    
    参数:
        matrix_4x4: 4x4齐次变换矩阵
        matrix_xy: 2x3 XY平面仿射变换矩阵
        z_mapping: Z轴映射参数字典
        calibration_info: 校准信息字典
        output_path: 输出文件路径
    """
    data = {
        "matrix": matrix_4x4.tolist(),
        "matrix_xy": matrix_xy.tolist(),
        "transformation_type": "affine_xy" + ("_linear_z" if z_mapping else ""),
        "matrix_size": "4x4",
        "calibration_datetime": datetime.now().isoformat()
    }
    
    # 添加Z映射信息（如果有）
    if z_mapping:
        data["z_mapping"] = z_mapping
        data["z_rmse"] = calibration_info.get("z_rmse", 0.0)
        data["calibration_points_count_z"] = calibration_info.get("z_points_count", 0)
    
    # 添加XY校准信息
    data["calibration_points_count_xy"] = calibration_info.get("xy_points_count", 0)
    data["xy_rmse_x"] = calibration_info.get("xy_rmse_x", 0.0)
    data["xy_rmse_y"] = calibration_info.get("xy_rmse_y", 0.0)
    
    # 保存到文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ 变换矩阵已保存到: {output_path}")


def print_results(matrix_xy, rmse_x, rmse_y, z_mapping=None, z_rmse=None):
    """
    打印计算结果
    """
    print("\n" + "="*60)
    print("计算结果")
    print("="*60)
    
    print("\nXY平面仿射变换矩阵 (2x3):")
    print(matrix_xy)
    
    print(f"\nXY变换参数:")
    print(f"  x_robot = {matrix_xy[0,0]:.6f} * x_camera + {matrix_xy[0,1]:.6f} * y_camera + {matrix_xy[0,2]:.6f}")
    print(f"  y_robot = {matrix_xy[1,0]:.6f} * x_camera + {matrix_xy[1,1]:.6f} * y_camera + {matrix_xy[1,2]:.6f}")
    
    print(f"\nXY平面误差:")
    print(f"  X方向RMSE: {rmse_x:.6f}")
    print(f"  Y方向RMSE: {rmse_y:.6f}")
    
    if z_mapping:
        print(f"\nZ轴线性映射:")
        print(f"  z_robot = {z_mapping['alpha']:.6f} * z_camera + {z_mapping['beta']:.6f}")
        print(f"  Z方向RMSE: {z_rmse:.6f}")
    
    print("="*60)


def test_transformation_xy(matrix_xy, camera_xy, robot_xy):
    """
    测试XY平面变换矩阵的准确性
    """
    print("\n" + "="*60)
    print("验证XY平面变换精度")
    print("="*60)
    
    for i, (cam_pt, rob_pt) in enumerate(zip(camera_xy, robot_xy), 1):
        # 预测机器人坐标
        cam_x, cam_y = cam_pt[0], cam_pt[1]
        pred_x = matrix_xy[0,0] * cam_x + matrix_xy[0,1] * cam_y + matrix_xy[0,2]
        pred_y = matrix_xy[1,0] * cam_x + matrix_xy[1,1] * cam_y + matrix_xy[1,2]
        
        # 实际机器人坐标
        actual_x, actual_y = rob_pt[0], rob_pt[1]
        
        # 计算误差
        error_x = abs(pred_x - actual_x)
        error_y = abs(pred_y - actual_y)
        error_total = np.sqrt(error_x**2 + error_y**2)
        
        print(f"\n点 {i}:")
        print(f"  相机坐标: ({cam_x:.2f}, {cam_y:.2f})")
        print(f"  预测机器人坐标: ({pred_x:.2f}, {pred_y:.2f})")
        print(f"  实际机器人坐标: ({actual_x:.2f}, {actual_y:.2f})")
        print(f"  误差: ΔX={error_x:.2f}, ΔY={error_y:.2f}, 总误差={error_total:.2f}")


def test_transformation_z(z_mapping, z_calibration_pairs):
    """
    测试Z轴线性映射的准确性
    """
    print("\n" + "="*60)
    print("验证Z轴映射精度")
    print("="*60)
    
    for i, (cam_z, rob_z) in enumerate(z_calibration_pairs, 1):
        # 预测机器人Z坐标
        pred_z = z_mapping['alpha'] * cam_z + z_mapping['beta']
        
        # 计算误差
        error_z = abs(pred_z - rob_z)
        
        print(f"\n点 {i}:")
        print(f"  相机Z坐标: {cam_z:.2f}")
        print(f"  预测机器人Z: {pred_z:.2f}")
        print(f"  实际机器人Z: {rob_z:.2f}")
        print(f"  误差: ΔZ={error_z:.2f}")


def main():
    """
    主函数
    """
    try:
        print("\n" + "="*60)
        print("坐标系变换矩阵计算工具")
        print("="*60)
        
        # 1. 检查XY坐标输入数据
        if not CAMERA_POINTS_XY or not ROBOT_POINTS_XY:
            print("\n错误：请在文件顶部的 CAMERA_POINTS_XY 和 ROBOT_POINTS_XY 中填入坐标数据！")
            print("\n示例格式：")
            print("CAMERA_POINTS_XY = [")
            print("    [173.71, 22.87],")
            print("    [81.19, -10.93],")
            print("    [-7.66, 14.89],")
            print("]")
            print("\nROBOT_POINTS_XY = [")
            print("    [237.96, -286.302],")
            print("    [273.822, -179.879],")
            print("    [244.257, -86.047],")
            print("]")
            print("\nZ_CALIBRATION_PAIRS = [")
            print("    (665.0, -80),")
            print("    (655, -70),")
            print("    (644, -60),")
            print("]")
            return
        
        if len(CAMERA_POINTS_XY) != len(ROBOT_POINTS_XY):
            print(f"\n错误：相机XY坐标点数量({len(CAMERA_POINTS_XY)})与机器人XY坐标点数量({len(ROBOT_POINTS_XY)})不匹配！")
            return
        
        if len(CAMERA_POINTS_XY) < 3:
            print(f"\n错误：至少需要3个XY点对来计算仿射变换，当前只有{len(CAMERA_POINTS_XY)}个！")
            return
        
        print(f"\n✓ 已读取 {len(CAMERA_POINTS_XY)} 个XY坐标点对")
        
        # 2. 计算XY平面仿射变换
        print("正在计算XY平面仿射变换...")
        camera_xy = [[float(pt[0]), float(pt[1])] for pt in CAMERA_POINTS_XY]
        robot_xy = [[float(pt[0]), float(pt[1])] for pt in ROBOT_POINTS_XY]
        matrix_xy, rmse_x, rmse_y = calculate_affine_transform_2d(camera_xy, robot_xy)
        
        # 3. 检查是否有Z校准数据
        z_mapping = None
        z_rmse = None
        z_points_count = 0
        
        if Z_CALIBRATION_PAIRS and len(Z_CALIBRATION_PAIRS) >= 2:
            print(f"\n✓ 已读取 {len(Z_CALIBRATION_PAIRS)} 个Z轴校准对")
            print("正在计算Z轴线性映射...")
            
            camera_z = [float(pair[0]) for pair in Z_CALIBRATION_PAIRS]
            robot_z = [float(pair[1]) for pair in Z_CALIBRATION_PAIRS]
            
            alpha, beta, z_rmse = calculate_linear_z_mapping(camera_z, robot_z)
            z_mapping = {
                "alpha": float(alpha),
                "beta": float(beta)
            }
            z_points_count = len(Z_CALIBRATION_PAIRS)
        else:
            print("\n提示：未提供Z轴校准数据（Z_CALIBRATION_PAIRS），将只计算XY平面变换")
        
        # 4. 构建4x4变换矩阵
        if z_mapping:
            matrix_4x4 = build_transformation_matrix_4x4(
                matrix_xy, 
                z_mapping['alpha'], 
                z_mapping['beta']
            )
        else:
            matrix_4x4 = build_transformation_matrix_4x4(matrix_xy)
        
        # 5. 打印结果
        print_results(matrix_xy, rmse_x, rmse_y, z_mapping, z_rmse)
        
        # 6. 测试XY变换
        test_transformation_xy(matrix_xy, camera_xy, robot_xy)
        
        # 7. 测试Z变换（如果有）
        if z_mapping:
            test_transformation_z(z_mapping, Z_CALIBRATION_PAIRS)
        
        # 8. 询问是否保存
        print("\n" + "="*60)
        save_choice = input("\n是否保存变换矩阵？(y/n): ").strip().lower()
        
        if save_choice == 'y':
            # 默认保存路径
            default_path = Path(__file__).parent.parent / "Config" / "transformation_matrix.json"
            custom_path = input(f"\n输入保存路径 (直接回车使用默认路径: {default_path}): ").strip()
            
            output_path = Path(custom_path) if custom_path else default_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 准备校准信息
            calibration_info = {
                "xy_points_count": len(CAMERA_POINTS_XY),
                "xy_rmse_x": float(rmse_x),
                "xy_rmse_y": float(rmse_y),
            }
            
            if z_mapping:
                calibration_info["z_points_count"] = z_points_count
                calibration_info["z_rmse"] = float(z_rmse)
            
            # 保存
            save_transformation_matrix(
                matrix_4x4, 
                matrix_xy, 
                z_mapping, 
                calibration_info, 
                output_path
            )
            
            print("\n完成！")
        else:
            print("\n未保存变换矩阵。")
    
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

