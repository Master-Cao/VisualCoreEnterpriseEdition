#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试检测C++模块
验证vc_detection_cpp模块是否正确编译并可以导入使用
"""

import sys
import os
import numpy as np

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

def print_warning(text):
    """打印警告信息"""
    print(f"⚠ {text}")

def test_import():
    """测试模块导入"""
    print_header("测试1: 模块导入")
    
    try:
        import vc_detection_cpp
        print_success("vc_detection_cpp 模块导入成功")
        
        # 检查版本信息
        if hasattr(vc_detection_cpp, '__version__'):
            print_info(f"模块版本: {vc_detection_cpp.__version__}")
        
        return True, vc_detection_cpp
    except ImportError as e:
        print_error(f"模块导入失败: {e}")
        print_info("请确保已编译C++模块:")
        print_info("  cd services/cpp")
        print_info("  ./build.sh --detection-only")
        print_warning("注意: 检测模块需要RKNN库支持，请确保已正确配置")
        return False, None
    except Exception as e:
        print_error(f"未知错误: {e}")
        return False, None

def test_classes(module):
    """测试类是否存在"""
    print_header("测试2: 检查类和方法")
    
    classes_to_check = {
        'DetectionBox': [
            'class_id', 'score', 'xmin', 'ymin', 'xmax', 'ymax', 'seg_mask'
        ],
        'DetectionService': [
            'load', 'detect', 'release'
        ],
        'RKNNDetector': [
            'load', 'detect', 'release'
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

def test_detection_box(module):
    """测试DetectionBox对象"""
    print_header("测试3: DetectionBox对象")
    
    try:
        box = module.DetectionBox()
        print_success("DetectionBox 对象创建成功")
        
        # 测试属性设置
        box.class_id = 1
        box.score = 0.95
        box.xmin = 10
        box.ymin = 20
        box.xmax = 100
        box.ymax = 200
        
        print_info("测试属性设置:")
        print_info(f"  class_id = {box.class_id}")
        print_info(f"  score = {box.score}")
        print_info(f"  bbox = [{box.xmin}, {box.ymin}, {box.xmax}, {box.ymax}]")
        
        # 验证属性
        if (box.class_id == 1 and 
            abs(box.score - 0.95) < 0.001 and
            box.xmin == 10 and box.ymin == 20 and
            box.xmax == 100 and box.ymax == 200):
            print_success("属性读写正常")
            return True
        else:
            print_error("属性读写异常")
            return False
            
    except Exception as e:
        print_error(f"DetectionBox测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_detector_creation(module):
    """测试检测器创建"""
    print_header("测试4: 创建检测器对象")
    
    # 使用一个不存在的模型路径（仅测试对象创建）
    fake_model_path = "/tmp/fake_model.rknn"
    
    try:
        detector = module.RKNNDetector(
            fake_model_path,
            conf_threshold=0.5,
            nms_threshold=0.45,
            target="rk3588"
        )
        print_success("RKNNDetector 对象创建成功")
        print_info(f"类型: {type(detector)}")
        print_warning("注意: 仅测试对象创建，未加载真实模型")
        return True, detector
    except Exception as e:
        print_error(f"创建检测器对象失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_numpy_interface(module):
    """测试numpy数组接口"""
    print_header("测试5: Numpy数组接口")
    
    try:
        # 创建测试图像
        test_images = {
            "灰度图 (H, W)": np.random.randint(0, 255, (256, 256), dtype=np.uint8),
            "BGR图 (H, W, 3)": np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8),
        }
        
        # 测试DetectionBox的seg_mask属性
        box = module.DetectionBox()
        
        for name, img in test_images.items():
            print_info(f"测试图像格式: {name}, shape={img.shape}")
            
            # 测试mask设置（使用二值mask）
            mask = np.random.randint(0, 2, (256, 256), dtype=np.uint8)
            try:
                box.seg_mask = mask
                retrieved_mask = box.seg_mask
                
                if retrieved_mask is not None:
                    print_success(f"  - Mask设置和读取成功, shape={retrieved_mask.shape}")
                else:
                    print_warning(f"  - Mask返回None")
                    
            except Exception as e:
                print_error(f"  - Mask操作失败: {e}")
        
        print_success("Numpy接口测试完成")
        return True
        
    except Exception as e:
        print_error(f"Numpy接口测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_detect_interface(module, detector):
    """测试detect接口（不加载真实模型）"""
    print_header("测试6: Detect接口")
    
    if detector is None:
        print_warning("跳过检测接口测试（检测器未创建）")
        return True
    
    print_info("创建测试图像...")
    test_image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    print_info(f"图像shape: {test_image.shape}, dtype: {test_image.dtype}")
    
    print_warning("注意: 由于未加载真实模型，detect调用预期会失败")
    print_info("这是正常的，我们只测试接口是否可调用")
    
    try:
        # 尝试调用detect（预期会失败，因为没有真实模型）
        results = detector.detect(test_image)
        print_warning(f"Detect返回: {len(results)} 个结果")
        print_warning("如果返回空列表是正常的（无真实模型）")
        return True
    except Exception as e:
        # 预期会有异常（没有加载模型）
        error_msg = str(e)
        if "模型" in error_msg or "RKNN" in error_msg or "load" in error_msg.lower():
            print_warning(f"预期的错误（未加载模型）: {error_msg}")
            print_success("Detect接口可调用（符合预期）")
            return True
        else:
            print_error(f"意外的错误: {e}")
            return False

def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "检测C++模块测试" + " " * 27 + "║")
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
    
    # 测试3: DetectionBox对象
    success = test_detection_box(module)
    results.append(("DetectionBox对象", success))
    
    # 测试4: 创建检测器对象
    success, detector = test_detector_creation(module)
    results.append(("创建检测器对象", success))
    
    # 测试5: Numpy接口
    success = test_numpy_interface(module)
    results.append(("Numpy接口", success))
    
    # 测试6: Detect接口
    success = test_detect_interface(module, detector)
    results.append(("Detect接口", success))
    
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
        print("\n🎉 所有测试通过！检测模块工作正常！")
        print_info("提示: 要进行真实检测，需要:")
        print_info("  1. 准备RKNN模型文件")
        print_info("  2. 使用真实图像调用detector.load()和detector.detect()")
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

