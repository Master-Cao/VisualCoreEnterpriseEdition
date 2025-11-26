#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试相机C++模块
验证vc_camera_cpp模块是否正确编译并可以导入使用
"""

import sys
import os

# 添加C++模块路径
cpp_dist_path = os.path.join(os.path.dirname(__file__), '../dist')
sys.path.insert(0, cpp_dist_path)

def print_header(text):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_success(text):
    """打印成功信息"""
    print(f"✓ {text}")

def print_error(text):
    """打印错误信息"""
    print(f"✗ {text}")

def print_info(text):
    """打印信息"""
    print(f"→ {text}")

def test_import():
    """测试模块导入"""
    print_header("测试1: 模块导入")
    
    try:
        import vc_camera_cpp
        print_success("vc_camera_cpp 模块导入成功")
        return True, vc_camera_cpp
    except ImportError as e:
        print_error(f"模块导入失败: {e}")
        print_info("请确保已编译C++模块:")
        print_info("  cd services/cpp")
        print_info("  ./build.sh --camera-only")
        return False, None
    except Exception as e:
        print_error(f"未知错误: {e}")
        return False, None

def test_classes(module):
    """测试类是否存在"""
    print_header("测试2: 检查类和方法")
    
    classes_to_check = {
        'VisionaryCamera': [
            'connect', 'disconnect', 'startAcquisition', 
            'stopAcquisition', 'stepAcquisition', 'healthy', 'get_frame'
        ],
        'CameraParams': [
            'width', 'height', 'fx', 'fy', 'cx', 'cy',
            'k1', 'k2', 'p1', 'p2', 'k3', 'f2rc', 'cam2worldMatrix'
        ]
    }
    
    all_ok = True
    for class_name, methods in classes_to_check.items():
        if hasattr(module, class_name):
            print_success(f"找到类: {class_name}")
            cls = getattr(module, class_name)
            
            for method in methods:
                if hasattr(cls, method):
                    print_info(f"  - {method}: ✓")
                else:
                    print_error(f"  - {method}: ✗ (未找到)")
                    all_ok = False
        else:
            print_error(f"未找到类: {class_name}")
            all_ok = False
    
    return all_ok

def test_camera_creation(module):
    """测试相机对象创建"""
    print_header("测试3: 创建相机对象")
    
    try:
        # 创建相机对象（不连接真实设备）
        camera = module.VisionaryCamera("192.168.1.10", 2114, True)
        print_success("VisionaryCamera 对象创建成功")
        print_info(f"类型: {type(camera)}")
        return True
    except Exception as e:
        print_error(f"创建相机对象失败: {e}")
        return False

def test_params_creation(module):
    """测试相机参数对象创建"""
    print_header("测试4: 创建参数对象")
    
    try:
        params = module.CameraParams()
        print_success("CameraParams 对象创建成功")
        
        # 测试设置属性
        params.width = 640
        params.height = 480
        params.fx = 500.0
        
        print_info(f"测试属性设置:")
        print_info(f"  width = {params.width}")
        print_info(f"  height = {params.height}")
        print_info(f"  fx = {params.fx}")
        
        if params.width == 640 and params.height == 480 and abs(params.fx - 500.0) < 0.001:
            print_success("属性读写正常")
            return True
        else:
            print_error("属性读写异常")
            return False
            
    except Exception as e:
        print_error(f"创建参数对象失败: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "相机C++模块测试" + " " * 27 + "║")
    print("╚" + "=" * 58 + "╝")
    
    results = []
    
    # 测试1: 导入模块
    success, module = test_import()
    results.append(("模块导入", success))
    
    if not success:
        print_header("测试终止")
        print_error("模块导入失败，无法继续后续测试")
        return False
    
    # 测试2: 检查类和方法
    success = test_classes(module)
    results.append(("类和方法检查", success))
    
    # 测试3: 创建相机对象
    success = test_camera_creation(module)
    results.append(("创建相机对象", success))
    
    # 测试4: 创建参数对象
    success = test_params_creation(module)
    results.append(("创建参数对象", success))
    
    # 打印测试总结
    print_header("测试总结")
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    for test_name, success in results:
        status = "通过" if success else "失败"
        symbol = "✓" if success else "✗"
        print(f"{symbol} {test_name}: {status}")
    
    print("\n" + "-" * 60)
    print(f"总计: {passed}/{total} 测试通过")
    print("-" * 60)
    
    if passed == total:
        print("\n🎉 所有测试通过！相机模块工作正常！")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查编译配置")
        return False

def main():
    """主函数"""
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

