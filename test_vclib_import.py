#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 vclib 导入是否正常
验证平台自适应配置是否正确
"""

import os
import sys
import platform

def test_vclib_path():
    """测试 vclib 路径配置"""
    print("=" * 60)
    print("测试 vclib 导入路径")
    print("=" * 60)
    
    # 检测平台
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    
    print(f"\n平台信息:")
    print(f"  系统: {platform.system()}")
    print(f"  架构: {platform.machine()}")
    print(f"  Python: {platform.python_version()}")
    
    # 确定子目录
    if sysname.startswith("windows"):
        subdir = "x86"
        expected_ext = ".pyd"
    elif "arm" in machine or "aarch" in machine:
        subdir = "aarch"
        expected_ext = ".so"
    else:
        subdir = "x86"
        expected_ext = ".so"
    
    print(f"\n预期配置:")
    print(f"  子目录: {subdir}")
    print(f"  扩展名: {expected_ext}")
    
    # 检查 vclib 目录
    repo_root = os.path.abspath(os.path.dirname(__file__))
    vclib_root = os.path.join(repo_root, "vclib")
    lib_path = os.path.join(vclib_root, subdir)
    
    print(f"\n路径检查:")
    print(f"  项目根: {repo_root}")
    print(f"  vclib根: {vclib_root}")
    print(f"  库路径: {lib_path}")
    
    if not os.path.exists(vclib_root):
        print(f"\n✗ 错误: vclib 目录不存在!")
        return False
    
    if not os.path.exists(lib_path):
        print(f"\n✗ 错误: 库路径不存在: {lib_path}")
        print(f"  可用的子目录:")
        for item in os.listdir(vclib_root):
            item_path = os.path.join(vclib_root, item)
            if os.path.isdir(item_path):
                print(f"    - {item}")
        return False
    
    # 列出库文件
    print(f"\n✓ 库路径存在")
    print(f"\n库文件列表:")
    
    lib_files = []
    for filename in os.listdir(lib_path):
        filepath = os.path.join(lib_path, filename)
        if os.path.isfile(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"  - {filename} ({size_mb:.2f} MB)")
            if filename.endswith(('.pyd', '.so', '.dll')):
                lib_files.append(filename)
    
    if not lib_files:
        print(f"\n✗ 警告: 未找到库文件 ({expected_ext})")
        return False
    
    print(f"\n✓ 找到 {len(lib_files)} 个库文件")
    
    # 测试导入
    print(f"\n" + "=" * 60)
    print("测试导入 vc_camera_cpp")
    print("=" * 60)
    
    # 添加到路径
    if lib_path not in sys.path:
        sys.path.append(lib_path)
        print(f"✓ 已添加到 sys.path: {lib_path}")
    
    # Windows: 添加DLL目录
    if sysname.startswith("windows"):
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(lib_path)
                print(f"✓ 已添加DLL搜索目录")
        except Exception as e:
            print(f"✗ 添加DLL搜索目录失败: {e}")
    
    # 尝试导入
    try:
        import vc_camera_cpp
        print(f"\n✓ 成功导入 vc_camera_cpp")
        print(f"  模块: {vc_camera_cpp}")
        
        # 检查是否有 VisionaryCamera 类
        if hasattr(vc_camera_cpp, 'VisionaryCamera'):
            print(f"  ✓ VisionaryCamera 类可用")
        else:
            print(f"  ✗ 警告: 未找到 VisionaryCamera 类")
            print(f"  可用属性: {dir(vc_camera_cpp)}")
        
        return True
        
    except ImportError as e:
        print(f"\n✗ 导入失败: {e}")
        print(f"\n可能的原因:")
        print(f"  1. 库文件与当前Python版本不兼容")
        print(f"  2. 缺少依赖的运行时库")
        print(f"  3. 库文件损坏")
        
        if sysname.startswith("windows"):
            print(f"\nWindows 特定检查:")
            print(f"  - 确保安装了 Visual C++ Redistributable")
            print(f"  - 使用 Dependencies.exe 检查缺少的DLL")
        
        return False


if __name__ == "__main__":
    success = test_vclib_path()
    
    print(f"\n" + "=" * 60)
    if success:
        print("✓ 测试通过！vclib 配置正确")
    else:
        print("✗ 测试失败！请检查上述错误信息")
    print("=" * 60)
    
    sys.exit(0 if success else 1)

