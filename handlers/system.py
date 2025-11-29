from domain.models.mqtt import MQTTResponse
from domain.enums.commands import MessageType, VisionCoreCommands
import threading
import time
import os
import json
import numpy as np
from services.detection import TargetSelector, RoiProcessor, CoordinateProcessor
from services.shared.calibration_utils import world_to_robot_using_calib


_runner_thread = None
_stop_event = threading.Event()
_gpio_resources = {}
_target_client_id = None

# 机器人抓取状态管理
_robot_state = {
    "is_picking": False,           # 是否正在抓取
    "picking_roi": None,           # 正在抓取的ROI名称（用于只停止对应的皮带）
    "lock": threading.Lock(),      # 状态锁，保证线程安全
    "last_send_time": 0,           # 上次发送时间
}


def handle_robot_complete(message: str, ctx) -> None:
    """
    处理机器人发送的 complete 消息
    当机器人抓取完成后调用，解除抓取锁定状态
    
    Args:
        message: 接收到的消息（通常是 "complete"）
        ctx: 上下文对象
    """
    global _robot_state
    
    logger = getattr(ctx, "logger", None)
    
    # 检查消息是否包含 complete 标识
    if message and "complete" in message.lower():
        with _robot_state["lock"]:
            was_picking = _robot_state["is_picking"]
            completed_roi = _robot_state["picking_roi"]
            _robot_state["is_picking"] = False
            _robot_state["picking_roi"] = None  # 清除ROI记录
            pick_duration = time.perf_counter() - _robot_state["last_send_time"]
        
        if logger and was_picking:
            roi_info = f"（ROI: {completed_roi}）" if completed_roi else ""
            logger.info(f"✓ 收到complete消息，机器人抓取完成{roi_info}（耗时{pick_duration:.2f}秒），恢复检测发送")
        elif logger:
            logger.debug(f"收到complete消息，但机器人未在抓取状态")
        
        return True
    
    return False


def handle_start(req: MQTTResponse, ctx) -> MQTTResponse:
    cam = getattr(ctx, "camera", None)
    det = getattr(ctx, "detector", None)
    base_gpio = getattr(ctx, "gpio", None)
    if not cam or not getattr(cam, "healthy", False):
        return MQTTResponse(command=VisionCoreCommands.START.value, component="camera", messageType=MessageType.ERROR, message="camera_not_ready", data={})
    if not det:
        return MQTTResponse(command=VisionCoreCommands.START.value, component="detector", messageType=MessageType.ERROR, message="detector_not_ready", data={})
    global _runner_thread, _gpio_resources, _target_client_id, _robot_state
    if _runner_thread and _runner_thread.is_alive():
        return MQTTResponse(command=VisionCoreCommands.START.value, component=req.component, messageType=MessageType.SUCCESS, message="already_running", data={"status": "ok"})
    
    # 重置机器人抓取状态
    with _robot_state["lock"]:
        _robot_state["is_picking"] = False
        _robot_state["picking_roi"] = None
        _robot_state["last_send_time"] = 0
    
    _gpio_resources = {}
    gpio_map = []
    roi_cfg = ctx.config.get("roi") or {}
    regions = roi_cfg.get("regions") or []
    for r in regions:
        try:
            gcfg = r.get("gpio") or {}
            if not bool(gcfg.get("enable", False)):
                continue
            chip = str(gcfg.get("chip", ""))
            pin = int(gcfg.get("pin"))
            roi_name = str(r.get("name", "roi"))
            if chip and not chip.startswith("/"):
                chip = "/" + chip
            from services.servo.gpio import GPIO
            g = GPIO()
            if g.open(chip, pin, consumer=f"gpio-{roi_name}"):
                _gpio_resources[roi_name] = g
                gpio_map.append(roi_name)
        except Exception:
            continue
    if not gpio_map and base_gpio and getattr(base_gpio, "healthy", False):
        for r in regions:
            try:
                roi_name = str(r.get("name", "roi"))
                _gpio_resources[roi_name] = base_gpio
                gpio_map.append(roi_name)
            except Exception:
                continue
    _target_client_id = (req.data or {}).get("client_id")
    _stop_event.clear()
    _runner_thread = threading.Thread(target=_run_loop, args=(ctx, gpio_map), daemon=True)
    _runner_thread.start()
    return MQTTResponse(command=VisionCoreCommands.START.value, component=req.component, messageType=MessageType.SUCCESS, message="ok", data={"status": "ok"})


def handle_stop(req: MQTTResponse, ctx) -> MQTTResponse:
    global _runner_thread, _gpio_resources, _target_client_id, _robot_state
    _stop_event.set()
    
    # 重置机器人抓取状态
    with _robot_state["lock"]:
        _robot_state["is_picking"] = False
        _robot_state["picking_roi"] = None
        _robot_state["last_send_time"] = 0
    
    # 等待运行循环线程结束
    if _runner_thread and _runner_thread.is_alive():
        try:
            _runner_thread.join(timeout=2.0)
        except Exception:
            pass
    
    # 释放GPIO资源
    for k, g in list(_gpio_resources.items()):
        try:
            if g is not getattr(ctx, "gpio", None):
                g.close()
        except Exception:
            pass
    
    # 清空全局变量
    _gpio_resources = {}
    _target_client_id = None
    _runner_thread = None
    
    # 强制垃圾回收（清理numpy数组等）
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    
    return MQTTResponse(command=VisionCoreCommands.STOP.value, component=req.component, messageType=MessageType.SUCCESS, message="ok", data={"status": "stopped"})


def _run_loop(ctx, gpio_map):
    cam = getattr(ctx, "camera", None)
    det = getattr(ctx, "detector", None)
    logger = getattr(ctx, "logger", None)
    
    loop_count = 0
    
    # 从配置中读取稳定等待时间
    roi_cfg = ctx.config.get("roi") or {}
    stability_wait_time = float(roi_cfg.get("stabilityWaitTime", 0.15))  # 默认150ms
    
    # 稳定检测状态（解决传送带停止后物体晃动问题）
    stability_state = {
        "waiting_stable": False,      # 是否正在等待物体稳定
        "stable_start_time": 0,       # 开始等待的时间
        "stable_wait_duration": stability_wait_time,  # 从配置读取
        "last_gpio_state": {},        # 记录上次GPIO状态，用于检测状态变化
    }
    
    while not _stop_event.is_set():
        try:
            loop_count += 1
            loop_start = time.perf_counter()
            current_time = time.perf_counter()
            
            # 检查是否正在等待物体稳定（只影响坐标发送，不影响GPIO控制）
            if stability_state["waiting_stable"]:
                elapsed = current_time - stability_state["stable_start_time"]
                if elapsed >= stability_state["stable_wait_duration"]:
                    # 等待结束，标记为可以发送
                    stability_state["waiting_stable"] = False
                    if logger:
                        logger.info(f"物体已稳定（等待{elapsed*1000:.0f}ms），准备检测和发送")
            
            # 1. 取图
            capture_start = time.perf_counter()
            result = cam.get_frame(depth=True, intensity=True, camera_params=True)
            capture_time = (time.perf_counter() - capture_start) * 1000  # 转换为毫秒
            
            # 数据提取
            extract_start = time.perf_counter()
            img = result.get("intensity_image") if result else None
            depth_data = result.get("depthmap") if result else None
            camera_params = result.get("cameraParams") if result else None
            extract_time = (time.perf_counter() - extract_start) * 1000
            
            if img is None:
                if logger:
                    logger.warning(f"[循环#{loop_count}] 取图失败 | get_frame={capture_time:.1f}ms")
                time.sleep(0.2)
                continue
            
            # 2. 检测
            detect_start = time.perf_counter()
            dets = det.detect(img)
            detect_time = (time.perf_counter() - detect_start) * 1000  # 转换为毫秒
            roi_cfg = ctx.config.get("roi") or {}
            regions = roi_cfg.get("regions") or []
            min_area = float(roi_cfg.get("minArea", 0))
            height, width = img.shape[:2]
            rois = []
            for region in regions:
                try:
                    rw = int(region.get("width", 120))
                    rh = int(region.get("height", 140))
                    x1 = int(region.get("offsetx", 0))
                    y1 = int(region.get("offsety", 0))
                    x2 = max(0, min(x1 + rw, width))
                    y2 = max(0, min(y1 + rh, height))
                    rois.append({"x1": max(0, min(x1, width)), "y1": max(0, min(y1, height)), "x2": x2, "y2": y2, "priority": int(region.get("priority", 999)), "name": str(region.get("name", "roi"))})
                except Exception:
                    continue
            seasoning = []
            for d in dets:
                cid = int(getattr(d, "class_id", getattr(d, "classId", -1)))
                if cid == 0:
                    # 使用mask面积（检测结果肯定有mask）
                    mask = getattr(d, 'seg_mask', None)
                    if mask is not None and isinstance(mask, np.ndarray):
                        area = float(np.sum(mask > 0))  # mask像素数
                        if area >= min_area:
                            seasoning.append(d)
            # 检查机器人状态（线程安全）- 需要在GPIO控制前获取
            with _robot_state["lock"]:
                is_robot_picking = _robot_state["is_picking"]
                picking_roi_name = _robot_state["picking_roi"]
            
            p1 = 0
            p2 = 0
            best_target = None
            best_target_roi = None  # 记录best_target所属的ROI名称
            
            for roi in rois:
                name = roi.get("name")
                priority = roi.get("priority", 999)
                count = 0
                for d in seasoning:
                    xmin = float(getattr(d, "xmin", 0))
                    ymin = float(getattr(d, "ymin", 0))
                    xmax = float(getattr(d, "xmax", 0))
                    ymax = float(getattr(d, "ymax", 0))
                    cx = 0.5 * (xmin + xmax)
                    cy = 0.5 * (ymin + ymax)
                    if roi["x1"] <= cx <= roi["x2"] and roi["y1"] <= cy <= roi["y2"]:
                        count += 1
                if roi.get("priority") == 1:
                    p1 = count
                elif roi.get("priority") == 2:
                    p2 = count
                
                gpio_inst = _gpio_resources.get(name)
                if gpio_inst:
                    # 关键逻辑：只有当前ROI是正在抓取的ROI时，才强制保持GPIO低电平
                    if is_robot_picking and name == picking_roi_name:
                        desired = 0  # 该ROI正在被抓取，强制低电平，皮带不移动
                    else:
                        desired = 1 if count == 0 else 0  # 正常逻辑（其他ROI或非抓取状态）
                    
                    current = gpio_inst.get()
                    
                    # 记录上次状态（用于检测状态变化）
                    last_state = stability_state["last_gpio_state"].get(name)
                    
                    if current is None or current != desired:
                        if desired == 1:
                            gpio_inst.high()
                        else:
                            # GPIO从高变低（传送带停止），启动稳定等待
                            gpio_inst.low()
                            if last_state == 1 and desired == 0:
                                # 传送带刚停止，启动稳定等待
                                stability_state["waiting_stable"] = True
                                stability_state["stable_start_time"] = current_time
                                if logger:
                                    logger.info(f"{name}: 传送带停止，等待物体稳定 {stability_state['stable_wait_duration']*1000:.0f}ms")
                    
                    # 更新状态记录
                    stability_state["last_gpio_state"][name] = desired
                
                if count > 0 and best_target is None:
                    sel = TargetSelector.select_by_multi_roi_priority(seasoning, [roi], min_area=min_area)
                    if sel and sel.get("detection"):
                        best_target = sel
                        best_target_roi = name  # 记录该目标来自哪个ROI
            # 3. 坐标计算和TCP响应
            tcp_response = None
            coord_time = 0
            tcp_time = 0
            
            # 只有在非等待稳定状态 AND 机器人非抓取状态时才计算和发送坐标
            if best_target and depth_data is not None and camera_params is not None:
                # 条件1：等待物体稳定
                if stability_state["waiting_stable"]:
                    if logger and loop_count % 10 == 0:  # 每10帧打印一次，避免刷屏
                        logger.debug(f"[循环#{loop_count}] 等待物体稳定中，暂不发送坐标")
                # 条件2：机器人正在抓取
                elif is_robot_picking:
                    if logger and loop_count % 10 == 0:  # 每10帧打印一次
                        logger.debug(f"[循环#{loop_count}] 机器人抓取中，等待complete消息")
                # 条件3：都满足，可以计算和发送
                else:
                    coord_start = time.perf_counter()
                    coord = CoordinateProcessor.calculate_coordinate_for_detection(best_target["detection"], depth_data, camera_params, None)
                    coord_time = (time.perf_counter() - coord_start) * 1000
                    
                    if coord and coord.get("camera_3d"):
                        world_xyz = coord["camera_3d"]
                        robot = world_to_robot_using_calib(world_xyz, ctx.project_root)
                        if robot and len(robot) >= 3:
                            x, y, z = robot[0], robot[1], robot[2]
                        else:
                            x, y, z = world_xyz[0], world_xyz[1], world_xyz[2]
                        tcp_response = f"{x:.2f},{y:.2f},{z:.2f}"
            
            if tcp_response:
                tcp_start = time.perf_counter()
                send_success = False
                try:
                    cid = _target_client_id
                    comm = getattr(getattr(ctx, "initializer", None), "comm", None)
                    if comm and cid:
                        comm.push_to_client(cid, tcp_response)
                        send_success = True
                    elif comm:
                        comm.broadcast(tcp_response)
                        send_success = True
                except Exception as e:
                    if logger:
                        logger.error(f"[循环#{loop_count}] TCP发送失败: {e}")
                tcp_time = (time.perf_counter() - tcp_start) * 1000
                
                # 发送成功后，设置机器人状态为抓取中
                if send_success:
                    with _robot_state["lock"]:
                        _robot_state["is_picking"] = True
                        _robot_state["picking_roi"] = best_target_roi  # 记录正在抓取的ROI
                        _robot_state["last_send_time"] = current_time
                    if logger:
                        logger.info(f"✓ 坐标已发送 [{tcp_response}]，机器人进入抓取状态（ROI: {best_target_roi}），等待complete消息")
            
            # 4. 计算总耗时
            total_time = (time.perf_counter() - loop_start) * 1000
            
            # 5. 输出详细日志
            if logger:
                # 基础信息（总是显示）
                log_parts = [
                    f"[循环#{loop_count}]",
                    f"取图={capture_time:.1f}ms",
                    f"检测={detect_time:.1f}ms",
                    f"检测数={len(dets) if dets else 0}",
                    f"目标数={len(seasoning)}",
                    f"ROI1={p1}",
                    f"ROI2={p2}"
                ]
                
                # TCP响应信息（总是显示）
                if best_target and tcp_response:
                    # 情况1：有目标且已发送
                    log_parts.append(f"坐标={coord_time:.1f}ms")
                    log_parts.append(f"TCP=[{tcp_response}]")
                    log_parts.append(f"发送={tcp_time:.1f}ms")
                elif best_target and not tcp_response:
                    # 情况2：有目标但未发送，区分原因
                    if is_robot_picking:
                        log_parts.append("状态=抓取中")
                        log_parts.append("TCP=[等待complete]")
                    elif stability_state["waiting_stable"]:
                        log_parts.append("状态=等待稳定")
                        log_parts.append("TCP=[暂不发送]")
                    else:
                        log_parts.append(f"坐标={coord_time:.1f}ms")
                        log_parts.append("TCP=[未发送]")
                else:
                    # 情况3：无目标，但要检查机器人是否在抓取中
                    if is_robot_picking:
                        # 机器人抓取中，即使无目标（遮挡）也显示抓取中状态
                        log_parts.append("状态=抓取中(遮挡)")
                        log_parts.append("TCP=[等待complete]")
                    else:
                        # 真正的无目标状态
                        log_parts.append("状态=无目标")
                        log_parts.append("TCP=[0,0,0,0,0]")
                
                log_parts.append(f"总计={total_time:.1f}ms")
                
                # 无目标状态每10条才记录一次，其他情况都记录
                should_log = True
                if not best_target and not is_robot_picking:
                    # 无目标且非抓取中，每10条记录一次
                    should_log = (loop_count % 10 == 0)
                
                if should_log:
                    logger.info(" | ".join(log_parts))
                
                # 详细的性能分析（仅在DEBUG模式下）
                if logger.level <= 10:  # DEBUG level
                    perf_details = [
                        f"  性能分析:",
                        f"get_frame调用={capture_time:.2f}ms",
                        f"数据提取={extract_time:.3f}ms",
                        f"ROI处理={(time.perf_counter() - detect_start - detect_time/1000)*1000:.2f}ms",
                    ]
                    logger.debug(" | ".join(perf_details))
            
            # 显式清理大对象（numpy数组等）以减少内存占用
            try:
                del img, depth_data, result, dets, seasoning
            except Exception:
                pass
            
            time.sleep(0.01)  # 从100ms减少到10ms，提高响应速度
            
        except Exception as e:
            if logger:
                logger.error(f"[循环#{loop_count}] 异常: {e}")
                import traceback
                logger.debug(traceback.format_exc())
            
            # 异常情况下也要清理
            try:
                del img, depth_data, result, dets, seasoning
            except Exception:
                pass
            
            time.sleep(0.01)  # 从100ms减少到10ms，提高响应速度
        
        # 每100次循环执行一次垃圾回收（平衡性能和内存）
        if loop_count % 100 == 0:
            try:
                import gc
                gc.collect()
            except Exception:
                pass


 
