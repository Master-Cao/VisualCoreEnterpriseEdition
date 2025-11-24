import os
import sys
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def load_config():
    import yaml
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "configs", "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    from services.camera.cpp_camera import CppCamera
    cfg = load_config()
    cam_cfg = cfg.get("camera", {})
    ip = (cam_cfg.get("connection") or {}).get("ip", "192.168.2.99")
    port = int((cam_cfg.get("connection") or {}).get("port", 2122))
    use_single = bool((cam_cfg.get("mode") or {}).get("useSingleStep", True))
    
    print(f"正在连接相机: {ip}:{port}")
    cam = CppCamera(ip=ip, port=port, use_single_step=use_single)
    ok = cam.connect()
    if not ok:
        print("连接失败")
        return
    print("连接成功\n")
    
    # 采集10次图像并统计耗时
    num_captures = 10
    capture_times = []
    
    print(f"开始采集{num_captures}次图像...\n")
    print("-" * 60)
    
    for i in range(num_captures):
        start_time = time.perf_counter()
        fr = cam.get_frame(depth=True, intensity=True, camera_params=True)
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        capture_times.append(elapsed_ms)
        
        if not fr:
            print(f"第 {i+1:2d} 次采图失败")
            continue
        
        info = {
            "intensity_shape": None if fr.get("intensity_image") is None else fr["intensity_image"].shape,
            "depth_len": None if fr.get("depthmap") is None else len(fr["depthmap"]),
            "params_width": None if fr.get("cameraParams") is None else fr["cameraParams"].width,
            "params_height": None if fr.get("cameraParams") is None else fr["cameraParams"].height,
        }
        
        print(f"第 {i+1:2d} 次采图耗时: {elapsed_ms:7.2f} ms | "
              f"图像尺寸: {info['intensity_shape']} | "
              f"深度点数: {info['depth_len']}")
    
    print("-" * 60)
    
    # 统计信息
    if capture_times:
        avg_time = sum(capture_times) / len(capture_times)
        min_time = min(capture_times)
        max_time = max(capture_times)
        
        print(f"\n采图统计:")
        print(f"  总次数: {len(capture_times)}")
        print(f"  平均耗时: {avg_time:.2f} ms")
        print(f"  最小耗时: {min_time:.2f} ms")
        print(f"  最大耗时: {max_time:.2f} ms")
        print(f"  理论FPS: {1000/avg_time:.2f}")
    
    cam.disconnect()
    print("\n相机已断开连接")

if __name__ == "__main__":
    main()

