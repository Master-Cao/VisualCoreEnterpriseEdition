#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
C++ 相机测试脚本
测试 CppCamera 的连接和采图性能
"""

import os
import sys
import time

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def prepare_cpp_libs():
    """
    准备 C++ 库路径（必须在导入 CppCamera 之前调用）
    """
    import platform
    
    # 获取 vclib 目录
    vclib_root = os.path.join(project_root, "vclib")
    
    # 检测平台
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    
    # 确定子目录
    if sysname.startswith("windows"):
        subdir = "x86"
        platform_name = f"Windows ({machine})"
    elif "arm" in machine or "aarch" in machine:
        subdir = "aarch"
        platform_name = f"Linux ARM ({machine})"
    else:
        subdir = "x86"
        platform_name = f"Linux x86 ({machine})"
    
    # 构建完整路径
    lib_path = os.path.join(vclib_root, subdir)
    lib_path = os.path.normpath(lib_path)
    
    print(f"准备 C++ 库路径...")
    print(f"  平台: {platform_name}")
    print(f"  库路径: {lib_path}")
    
    # 检查目录是否存在
    if not os.path.isdir(lib_path):
        print(f"  ✗ 错误: 库目录不存在")
        return False
    
    # 列出库文件
    try:
        files = os.listdir(lib_path)
        lib_files = [f for f in files if f.endswith(('.pyd', '.so', '.dll'))]
        if lib_files:
            print(f"  找到库文件: {', '.join(lib_files)}")
        else:
            print(f"  ✗ 警告: 未找到库文件")
            return False
    except Exception as e:
        print(f"  ✗ 无法列出目录: {e}")
        return False
    
    # Windows: 添加 DLL 搜索目录
    if sysname.startswith("windows"):
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(lib_path)
                print(f"  ✓ 已添加 DLL 搜索目录")
        except Exception as e:
            print(f"  ✗ 添加 DLL 搜索目录失败: {e}")
            return False
    
    # 添加到 sys.path
    if lib_path not in sys.path:
        sys.path.append(lib_path)
        print(f"  ✓ 已添加到 sys.path")
    
    # Linux: 设置 LD_LIBRARY_PATH
    if not sysname.startswith("windows"):
        ld = os.environ.get("LD_LIBRARY_PATH", "")
        if lib_path not in ld:
            os.environ["LD_LIBRARY_PATH"] = (ld + (":" if ld else "") + lib_path)
            print(f"  ✓ 已设置 LD_LIBRARY_PATH")
    
    print(f"✓ C++ 库路径准备完成\n")
    return True


def load_config():
    """加载配置文件"""
    import yaml
    cfg_path = os.path.join(project_root, "configs", "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    print("=" * 60)
    print("C++ 相机测试")
    print("=" * 60)
    print()
    
    # 1. 准备 C++ 库路径（必须在导入之前）
    if not prepare_cpp_libs():
        print("\n✗ C++ 库路径准备失败，无法继续")
        return
    
    # 2. 导入 CppCamera（现在路径已经准备好了）
    try:
        from services.camera.cpp_camera import CppCamera
        print("✓ CppCamera 模块导入成功\n")
    except ImportError as e:
        print(f"✗ 导入 CppCamera 失败: {e}")
        print("\n可能的原因:")
        print("  1. vclib 中的库文件与当前 Python 版本不兼容")
        print("  2. 缺少依赖的运行时库")
        return
    
    # 3. 加载配置
    try:
        cfg = load_config()
        print("✓ 配置文件加载成功\n")
    except Exception as e:
        print(f"✗ 加载配置失败: {e}")
        return
    
    cam_cfg = cfg.get("camera", {})
    ip = (cam_cfg.get("connection") or {}).get("ip", "192.168.2.99")
    port = int((cam_cfg.get("connection") or {}).get("port", 2122))
    use_single = bool((cam_cfg.get("mode") or {}).get("useSingleStep", True))
    
    # 4. 连接相机
    print("-" * 60)
    print(f"正在连接相机...")
    print(f"  IP: {ip}")
    print(f"  端口: {port}")
    print(f"  单步模式: {use_single}")
    print("-" * 60)
    
    try:
        cam = CppCamera(ip=ip, port=port, use_single_step=use_single)
    except Exception as e:
        print(f"\n✗ 创建相机对象失败: {e}")
        return
    
    connect_start = time.perf_counter()
    ok = cam.connect()
    connect_time = (time.perf_counter() - connect_start) * 1000
    
    if not ok:
        print(f"✗ 连接失败 | 耗时={connect_time:.1f}ms")
        return
    
    print(f"✓ 连接成功 | 耗时={connect_time:.1f}ms\n")
    
    # 5. 采集图像测试
    num_captures = 10
    capture_times = []
    success_count = 0
    
    print("=" * 60)
    print(f"开始采集 {num_captures} 次图像")
    print("=" * 60)
    
    for i in range(num_captures):
        start_time = time.perf_counter()
        fr = cam.get_frame(depth=True, intensity=True, camera_params=True)
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        capture_times.append(elapsed_ms)
        
        if not fr:
            print(f"[{i+1:2d}/{num_captures}] ✗ 采图失败 | 耗时={elapsed_ms:6.1f}ms")
            continue
        
        success_count += 1
        
        # 提取图像信息
        intensity_img = fr.get("intensity_image")
        depthmap = fr.get("depthmap")
        camera_params = fr.get("cameraParams")
        frame_num = fr.get("frame_num", 0)
        timestamp = fr.get("timestamp_ms", 0)
        
        # 构建信息字符串
        info_parts = [f"耗时={elapsed_ms:6.1f}ms"]
        
        if intensity_img is not None:
            info_parts.append(f"图像={intensity_img.shape}")
        
        if depthmap is not None:
            depth_points = len(depthmap) if isinstance(depthmap, list) else depthmap.size
            info_parts.append(f"深度={depth_points}点")
        
        if camera_params is not None:
            info_parts.append(f"分辨率={camera_params.width}x{camera_params.height}")
        
        if frame_num > 0:
            info_parts.append(f"帧号={frame_num}")
        
        if timestamp > 0:
            info_parts.append(f"时间戳={timestamp}ms")
        
        print(f"[{i+1:2d}/{num_captures}] ✓ " + " | ".join(info_parts))
    
    print("=" * 60)
    
    # 6. 统计信息
    if capture_times:
        avg_time = sum(capture_times) / len(capture_times)
        min_time = min(capture_times)
        max_time = max(capture_times)
        
        print(f"\n采图统计:")
        print(f"  总次数: {len(capture_times)}")
        print(f"  成功次数: {success_count}")
        print(f"  失败次数: {len(capture_times) - success_count}")
        print(f"  成功率: {success_count/len(capture_times)*100:.1f}%")
        print(f"  平均耗时: {avg_time:.2f} ms")
        print(f"  最小耗时: {min_time:.2f} ms")
        print(f"  最大耗时: {max_time:.2f} ms")
        print(f"  理论 FPS: {1000/avg_time:.2f}")
        print()
    
    # 7. 断开连接
    try:
        cam.disconnect()
        print("✓ 相机已断开连接")
    except Exception as e:
        print(f"✗ 断开连接时出错: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()

