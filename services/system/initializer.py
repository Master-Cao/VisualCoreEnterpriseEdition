#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional, Any
import time
import threading

from services.comm.command_router import CommandRouter
from services.comm.comm_manager import CommManager
from services.camera.sick_camera import SickCamera
from services.detection.factory import create_detector
from services.sftp.sftp_client import SftpClient
from .monitor import SystemMonitor


class SystemInitializer:
    def __init__(self, config: dict, logger: Optional[Any] = None):
        self._cfg = config or {}
        self._logger = logger
        self.router = CommandRouter()
        self.comm: Optional[CommManager] = None
        self.camera: Optional[SickCamera] = None
        self.detector = None
        self.sftp: Optional[SftpClient] = None
        self.monitor: Optional[SystemMonitor] = None
        
        # 添加停止事件，用于响应Ctrl+C中断
        self._stop_event = threading.Event()
        self._is_stopping = False

        bm = (self._cfg.get("board_mode") or {})
        mon = (bm.get("monitoring") or {})
        self._retry_delay = int(bm.get("retry_delay", 5))
        self._check_interval = int(mon.get("check_interval", 30))
        self._failure_threshold = int(mon.get("failure_threshold", 1))

    # 装配与启动
    def start(self):
        """
        启动系统组件（分级启动策略）
        
        关键组件（主线程阻塞重试直到成功）：
        - 相机 (Camera)
        - 检测器 (Detector)
        - TCP通信 (TCP Server)
        
        非关键组件（后台异步重试，不阻塞启动）：
        - MQTT通信 (MQTT Client)
        - SFTP客户端 (SFTP Client)
        """
        # 路由注册（在通信启动前完成），并先绑定可用依赖
        self.router.register_default()
        self.router.bind(config=self._cfg, logger=self._logger, initializer=self)
        
        # ========== 第一阶段：启动关键组件（主线程阻塞重试） ==========
        
        # 1. 启动TCP通信（关键组件，必须成功）
        self._start_tcp_with_retry()
        if self._is_stopping:
            if self._logger:
                self._logger.warning("启动过程被中断 (TCP)")
            return
        
        # 2. 启动相机（关键组件，必须成功）
        self._start_camera_with_retry()
        if self._is_stopping:
            if self._logger:
                self._logger.warning("启动过程被中断 (Camera)")
            return
        
        # 3. 启动检测器（关键组件，必须成功）
        self._start_detector_with_retry()
        if self._is_stopping:
            if self._logger:
                self._logger.warning("启动过程被中断 (Detector)")
            return
        
        # ========== 第二阶段：启动非关键组件（允许失败，后台重试） ==========
        
        # 4. 尝试启动MQTT（非关键组件，失败不阻塞）
        self._try_start_mqtt()
        
        # 5. 尝试启动SFTP（非关键组件，失败不阻塞）
        self._try_start_sftp()
        
        # ========== 第三阶段：启动监控器 ==========
        self._setup_monitor()
        
        # 绑定监控
        if self.monitor:
            self.router.bind(monitor=self.monitor)
        
        if self._logger:
            self._logger.info("✓ 系统启动完成 | 关键组件全部就绪")
    
    def _start_tcp_with_retry(self):
        """启动TCP服务器（主线程无限重试直到成功）"""
        tcp_cfg = (self._cfg.get("DetectionServer") or {})
        if not bool(tcp_cfg.get("enable", False)):
            if self._logger:
                self._logger.warning("TCP服务器已禁用")
            return
        
        if self._logger:
            self._logger.info("正在启动TCP服务器（关键组件）...")
        
        # 初始化CommManager
        self.comm = CommManager(config=self._cfg, router=self.router, logger=self._logger)
        
        # 无限重试直到TCP启动成功（可被Ctrl+C中断）
        retry_count = 0
        while not self._is_stopping:
            try:
                ok = self.comm.restart_tcp()
                if ok:
                    if self._logger:
                        # 如果之前有失败，记录总共重试次数
                        if retry_count > 0:
                            self._logger.info(f"✓ TCP服务器启动成功 | {tcp_cfg.get('host')}:{tcp_cfg.get('port')} | 重试{retry_count}次后成功")
                        else:
                            self._logger.info(f"✓ TCP服务器启动成功 | {tcp_cfg.get('host')}:{tcp_cfg.get('port')}")
                    break
                else:
                    retry_count += 1
                    # 每10次失败记录一次日志（或首次失败）
                    if self._logger and (retry_count == 1 or retry_count % 10 == 0):
                        self._logger.error(f"✗ TCP服务器启动失败 | 已重试{retry_count}次 | {self._retry_delay}秒后继续...")
                    # 使用可中断的等待
                    if self._stop_event.wait(timeout=self._retry_delay):
                        break  # 收到停止信号
            except Exception as e:
                retry_count += 1
                # 每10次失败记录一次日志（或首次失败）
                if self._logger and (retry_count == 1 or retry_count % 10 == 0):
                    self._logger.error(f"✗ TCP服务器启动异常: {e} | 已重试{retry_count}次 | {self._retry_delay}秒后继续...")
                # 使用可中断的等待
                if self._stop_event.wait(timeout=self._retry_delay):
                    break  # 收到停止信号
    
    def _start_camera_with_retry(self):
        """启动相机（主线程无限重试直到成功）"""
        cam_cfg = (self._cfg.get("camera") or {})
        if not bool(cam_cfg.get("enable", False)):
            if self._logger:
                self._logger.warning("相机已禁用")
            return
        
        if self._logger:
            self._logger.info("正在启动相机（关键组件）...")
        
        # 提取相机配置
        ip = (cam_cfg.get("connection") or {}).get("ip", "192.168.2.99")
        port = int((cam_cfg.get("connection") or {}).get("port", 2122))
        use_single = bool((cam_cfg.get("mode") or {}).get("useSingleStep", True))
        auth_cfg = (cam_cfg.get("auth") or {})
        login_attempts = auth_cfg.get("loginAttempts")
        
        # 创建相机实例
        self.camera = SickCamera(
            ip=ip,
            port=port,
            use_single_step=use_single,
            logger=self._logger,
            login_attempts=login_attempts,
        )
        
        # 无限重试直到相机连接成功（可被Ctrl+C中断）
        retry_count = 0
        while not self._is_stopping:
            try:
                ok = self.camera.connect()
                if ok and self.camera.healthy:
                    # 绑定相机到路由
                    self.router.bind(camera=self.camera)
                    if self._logger:
                        # 如果之前有失败，记录总共重试次数
                        if retry_count > 0:
                            self._logger.info(f"✓ 相机连接成功 | {ip}:{port} | 重试{retry_count}次后成功")
                        else:
                            self._logger.info(f"✓ 相机连接成功 | {ip}:{port}")
                    
                    # 预热取图（避免首次检测延迟）
                    self._warmup_camera()
                    break
                else:
                    retry_count += 1
                    # 每10次失败记录一次日志（或首次失败）
                    if self._logger and (retry_count == 1 or retry_count % 10 == 0):
                        self._logger.error(f"✗ 相机连接失败 | 已重试{retry_count}次 | {self._retry_delay}秒后继续...")
                    # 使用可中断的等待
                    if self._stop_event.wait(timeout=self._retry_delay):
                        break  # 收到停止信号
            except Exception as e:
                retry_count += 1
                # 每10次失败记录一次日志（或首次失败）
                if self._logger and (retry_count == 1 or retry_count % 10 == 0):
                    self._logger.error(f"✗ 相机连接异常: {e} | 已重试{retry_count}次 | {self._retry_delay}秒后继续...")
                # 使用可中断的等待
                if self._stop_event.wait(timeout=self._retry_delay):
                    break  # 收到停止信号
    
    def _warmup_camera(self):
        """
        相机预热取图
        
        首次从相机取图通常耗时较长（初始化、缓冲等），
        通过预热取图可以避免首次检测时的长延迟。
        """
        if not self.camera:
            return
        
        try:
            if self._logger:
                self._logger.info("正在执行相机预热取图...")
            
            warmup_start = time.time()
            
            # 尝试取一帧图像（只获取强度图像以加快预热速度）
            frame = self.camera.get_frame(depth=False, intensity=True, camera_params=False)
            
            warmup_time = (time.time() - warmup_start) * 1000  # 转换为毫秒
            
            if frame:
                if self._logger:
                    self._logger.info(f"✓ 相机预热完成 | 耗时={warmup_time:.1f}ms")
            else:
                if self._logger:
                    self._logger.warning(f"✗ 相机预热取图失败 | 耗时={warmup_time:.1f}ms | 首次检测可能较慢")
                    
        except Exception as e:
            if self._logger:
                self._logger.warning(f"✗ 相机预热异常: {e} | 首次检测可能较慢")
    
    def _visualize_warmup_detections(self, image, detections):
        """
        可视化预热检测结果（用于调试）
        
        Args:
            image: 输入图像
            detections: 检测结果列表
        """
        try:
            import cv2
            import numpy as np
            import os
            
            # 确保图像是3通道BGR格式
            if len(image.shape) == 2:
                vis_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            else:
                vis_image = image.copy()
            
            # 绘制检测框和掩码
            if detections:
                for i, det in enumerate(detections):
                    # 绘制边界框
                    cv2.rectangle(
                        vis_image,
                        (det.xmin, det.ymin),
                        (det.xmax, det.ymax),
                        (0, 255, 0),  # 绿色
                        2
                    )
                    
                    # 绘制类别和置信度
                    label = f"Class{det.class_id}: {det.score:.2f}"
                    cv2.putText(
                        vis_image,
                        label,
                        (det.xmin, det.ymin - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2
                    )
                    
                    # 如果有掩码，叠加显示
                    if det.seg_mask is not None:
                        # 创建彩色掩码
                        color = np.array([0, 255, 0], dtype=np.uint8)  # 绿色
                        mask_colored = np.zeros_like(vis_image)
                        mask_colored[det.seg_mask > 0] = color
                        
                        # 半透明叠加
                        vis_image = cv2.addWeighted(vis_image, 1.0, mask_colored, 0.3, 0)
                
                # 添加统计信息
                info_text = f"Detections: {len(detections)}"
                cv2.putText(
                    vis_image,
                    info_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),  # 红色
                    2
                )
            else:
                # 无检测结果
                cv2.putText(
                    vis_image,
                    "No Detections",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),  # 红色
                    2
                )
            # 保存到debug目录
            debug_dir = "debug"
            os.makedirs(debug_dir, exist_ok=True)
            # 保存检测结果
            output_path = os.path.join(debug_dir, "warmup_detection_result.jpg")
            cv2.imwrite(output_path, vis_image)
            
        except Exception as e:
            if self._logger:
                self._logger.warning(f"可视化预热检测失败: {e}")
    
    def _warmup_detector(self):
        """
        检测器预热推理
        
        首次推理通常耗时较长（模型加载到GPU、CUDA初始化等），
        通过预热推理可以避免首次实际检测时的长延迟。
        使用预设的warmup_image.jpg进行预热。
        """
        if not self.detector:
            return
        
        try:
            if self._logger:
                self._logger.info("正在执行检测器预热推理...")
            
            warmup_start = time.time()
            
            # 读取预热图像
            import cv2
            import os
            
            warmup_image_path = os.path.join("configs", "warmup_image.jpg")
            
            # 检查文件是否存在
            if not os.path.exists(warmup_image_path):
                if self._logger:
                    self._logger.warning(f"预热图像不存在: {warmup_image_path} | 跳过预热")
                return
            
            # 读取图像（灰度模式）
            warmup_image = cv2.imread(warmup_image_path, cv2.IMREAD_GRAYSCALE)
            
            if warmup_image is None:
                if self._logger:
                    self._logger.warning(f"无法读取预热图像: {warmup_image_path} | 跳过预热")
                return
            
            if self._logger:
                self._logger.info(f"已加载预热图像: {warmup_image_path} | 尺寸: {warmup_image.shape}")
            
            # 执行推理
            detections = self.detector.detect(warmup_image)
            
            warmup_time = (time.time() - warmup_start) * 1000  # 转换为毫秒
            
            detection_count = len(detections) if detections else 0
            if self._logger:
                self._logger.info(f"✓ 检测器预热完成 | 耗时={warmup_time:.1f}ms | 检测数={detection_count}")
            
            # 可视化检测结果（调试用）
            if self._cfg.get("board_mode", {}).get("debug_warmup", False):
                self._visualize_warmup_detections(warmup_image, detections)
                    
        except Exception as e:
            if self._logger:
                self._logger.warning(f"✗ 检测器预热异常: {e} | 首次检测可能较慢")
    
    def _start_detector_with_retry(self):
        """启动检测器（主线程无限重试直到成功）"""
        model_cfg = (self._cfg.get("model") or {})
        model_path = model_cfg.get("path", "")
        
        if self._logger:
            self._logger.info(f"正在加载检测器（关键组件）| 模型: {model_path}")
        
        # 无限重试直到检测器加载成功（可被Ctrl+C中断）
        retry_count = 0
        while not self._is_stopping:
            try:
                self.detector = create_detector(self._cfg, logger=self._logger)
                self.detector.load()
                
                # 绑定检测器到路由
                self.router.bind(detector=self.detector)
                
                if self._logger:
                    # 如果之前有失败，记录总共重试次数
                    if retry_count > 0:
                        self._logger.info(f"✓ 检测器加载成功 | 后端: {model_cfg.get('backend', 'auto')} | 重试{retry_count}次后成功")
                    else:
                        self._logger.info(f"✓ 检测器加载成功 | 后端: {model_cfg.get('backend', 'auto')}")
                
                # 预热推理（避免首次检测延迟）
                self._warmup_detector()
                break
                
            except Exception as e:
                retry_count += 1
                # 每10次失败记录一次日志（或首次失败）
                if self._logger and (retry_count == 1 or retry_count % 10 == 0):
                    self._logger.error(f"✗ 检测器加载失败: {e} | 已重试{retry_count}次 | {self._retry_delay}秒后继续...")
                self.detector = None
                # 使用可中断的等待
                if self._stop_event.wait(timeout=self._retry_delay):
                    break  # 收到停止信号
    
    def _try_start_mqtt(self):
        """尝试启动MQTT（非关键组件，失败不阻塞）"""
        mqtt_cfg = (self._cfg.get("mqtt") or {})
        if not bool(mqtt_cfg.get("enable", False)):
            if self._logger:
                self._logger.info("MQTT客户端已禁用")
            return
        
        try:
            if self._logger:
                self._logger.info("正在启动MQTT客户端（非关键组件）...")
            
            # 尝试连接MQTT
            ok = self.comm.restart_mqtt()
            
            if ok:
                if self._logger:
                    self._logger.info(f"✓ MQTT连接成功 | {mqtt_cfg.get('connection', {}).get('broker_host')}")
            else:
                if self._logger:
                    self._logger.warning("✗ MQTT连接失败 | 将由监控器在后台重试")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"✗ MQTT启动异常: {e} | 将由监控器在后台重试")
    
    def _try_start_sftp(self):
        """尝试启动SFTP（非关键组件，失败不阻塞）"""
        sftp_cfg = (self._cfg.get("sftp") or {})
        if not bool(sftp_cfg.get("enable", False)):
            if self._logger:
                self._logger.info("SFTP客户端已禁用")
            return
        
        try:
            if self._logger:
                self._logger.info("正在初始化SFTP客户端（非关键组件）...")
            
            # 创建SFTP客户端实例
            self.sftp = SftpClient(sftp_cfg, logger=self._logger)
            
            # 首次启动时显示详细日志（verbose=True）
            ok = self.sftp.connect(verbose=True)
            
            if ok:
                # 绑定SFTP到路由
                self.router.bind(sftp=self.sftp)
                
                if self._logger:
                    self._logger.info(f"✓ SFTP连接成功 | {sftp_cfg.get('host')}")
            else:
                if self._logger:
                    self._logger.warning(f"✗ SFTP初始连接失败 | {sftp_cfg.get('host')} | 将由监控器在后台静默重试")
                # 即使连接失败，也保留对象让监控器重试
                self.router.bind(sftp=self.sftp)
                
        except Exception as e:
            if self._logger:
                self._logger.warning(f"✗ SFTP初始化失败: {e} | 将由监控器在后台静默重试")
            # 创建一个对象，让监控器可以重试
            try:
                self.sftp = SftpClient(sftp_cfg, logger=self._logger)
                self.router.bind(sftp=self.sftp)
            except Exception:
                self.sftp = None

    def request_stop(self):
        """
        请求停止系统（从信号处理器调用）
        设置停止标志，中断所有阻塞等待
        """
        self._is_stopping = True
        self._stop_event.set()
        if self._logger:
            self._logger.info("收到停止请求，正在中断启动流程...")
    
    def stop(self):
        """
        停止系统并释放所有资源
        
        资源释放顺序：
        1. 停止监控器（所有监控线程）
        2. 停止通信服务（TCP、MQTT）
        3. 断开相机连接
        4. 断开SFTP连接
        """
        self._is_stopping = True
        self._stop_event.set()
        
        if self._logger:
            self._logger.info("正在停止系统...")
        
        try:
            # 1. 停止监控器（停止所有监控线程）
            if self.monitor:
                try:
                    if self._logger:
                        self._logger.info("停止监控器...")
                    self.monitor.stop()
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"停止监控器失败: {e}")
            
            # 2. 停止通信服务（TCP和MQTT）
            if self.comm:
                try:
                    if self._logger:
                        self._logger.info("停止通信服务...")
                    self.comm.stop()
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"停止通信服务失败: {e}")
            
            # 3. 断开相机
            if self.camera:
                try:
                    if self._logger:
                        self._logger.info("断开相机...")
                    self.camera.disconnect()
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"断开相机失败: {e}")
            
            # 4. 断开SFTP
            if self.sftp:
                try:
                    if self._logger:
                        self._logger.info("断开SFTP...")
                    self.sftp.disconnect(verbose=True)
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"断开SFTP失败: {e}")
            
        finally:
            if self._logger:
                self._logger.info("✓ 系统已完全停止，所有资源已释放")

    def restart(self, new_config: Optional[dict] = None, delay: float = 2.0):
        """
        重启系统（用于配置更新后重新加载）
        
        Args:
            new_config: 新的配置字典，如果为None则重新加载配置文件
            delay: 延迟启动时间（秒），给客户端足够时间接收响应
        """
        if self._logger:
            self._logger.info("收到系统重启请求...")
        
        def _do_restart():
            try:
                # 等待一段时间，确保响应已发送给客户端
                time.sleep(delay)
                
                if self._logger:
                    self._logger.info("开始执行系统重启...")
                
                # 1. 停止所有组件
                self.stop()
                
                # 2. 更新配置
                if new_config:
                    self._cfg = new_config
                    if self._logger:
                        self._logger.info("已加载新配置")
                else:
                    # 重新加载配置文件
                    try:
                        import yaml
                        import os
                        cfg_path = os.path.join(os.getcwd(), "configs", "config.yaml")
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            self._cfg = yaml.safe_load(f) or {}
                        if self._logger:
                            self._logger.info("已从文件重新加载配置")
                    except Exception as e:
                        if self._logger:
                            self._logger.error(f"重新加载配置失败: {e}，使用当前配置")
                
                # 3. 重新初始化配置参数
                bm = (self._cfg.get("board_mode") or {})
                mon = (bm.get("monitoring") or {})
                self._retry_delay = int(bm.get("retry_delay", 5))
                self._check_interval = int(mon.get("check_interval", 30))
                self._failure_threshold = int(mon.get("failure_threshold", 1))
                
                # 4. 重新启动所有组件
                self.start()
                
                if self._logger:
                    self._logger.info("✓ 系统重启完成")
                    
            except Exception as e:
                if self._logger:
                    self._logger.error(f"系统重启失败: {e}")
                # 重启失败也要尝试启动，确保系统不处于完全停止状态
                try:
                    self.start()
                except Exception as e2:
                    if self._logger:
                        self._logger.critical(f"重启后启动失败: {e2}")
        
        # 在后台线程执行重启，避免阻塞当前响应
        restart_thread = threading.Thread(target=_do_restart, daemon=True, name="SystemRestartThread")
        restart_thread.start()
        
        if self._logger:
            self._logger.info(f"系统重启已安排，将在 {delay} 秒后执行")

    # 监控注册
    def _setup_monitor(self):
        """
        配置系统监控器
        
        监控策略：
        - 关键组件（相机、检测器、TCP）：后台监控，异常时重启
        - 非关键组件（MQTT、SFTP）：后台监控，异常时重启
        
        注意：关键组件在主线程已经保证启动成功，这里只是持续监控运行时健康状态
        """
        self.monitor = SystemMonitor(
            logger=self._logger,
            check_interval=self._check_interval,
            retry_delay=self._retry_delay,
            failure_threshold=self._failure_threshold,
        )
        
        # ===== 监控关键组件 =====
        
        # TCP服务器（关键组件）
        tcp_cfg = (self._cfg.get("DetectionServer") or {})
        if self.comm and bool(tcp_cfg.get("enable", False)):
            self.monitor.register(
                "tcp_server",
                lambda: bool(self.comm._tcp and self.comm._tcp.healthy),
                lambda: self.comm.restart_tcp(),
                is_critical=True,
            )
        
        # 相机（关键组件）
        if self.camera:
            self.monitor.register(
                "camera",
                lambda: bool(self.camera.healthy),
                self._restart_camera,
                is_critical=True,
            )
        
        # 检测器（关键组件）
        if self.detector:
            self.monitor.register(
                "detector",
                self._check_detector,
                self._restart_detector,
                is_critical=True,
            )
        
        # ===== 监控非关键组件 =====
        
        # MQTT客户端（非关键组件，静默重试）
        mqtt_cfg = (self._cfg.get("mqtt") or {})
        if self.comm and bool(mqtt_cfg.get("enable", False)):
            self.monitor.register(
                "mqtt_client",
                lambda: bool(self.comm._mqtt and self.comm._mqtt.healthy),
                lambda: self.comm.restart_mqtt(),
                is_critical=False,
            )
        
        # SFTP客户端（非关键组件，静默重试）
        if self.sftp:
            self.monitor.register(
                "sftp_client",
                self._check_sftp,
                self._restart_sftp,
                is_critical=False,
            )
        
        self.monitor.start()
        
        if self._logger:
            self._logger.info(f"系统监控已启动 | 检查间隔={self._check_interval}秒 | 重试延迟={self._retry_delay}秒")

    # 重启实现
    def _restart_camera(self) -> bool:
        """重启相机"""
        try:
            if self.camera:
                try:
                    self.camera.disconnect()
                except Exception:
                    pass
                ok = self.camera.connect()
                if ok:
                    # 重新绑定到路由
                    self.router.bind(camera=self.camera)
                    if self._logger:
                        self._logger.info("相机已重启")
                    # 重启后预热取图
                    self._warmup_camera()
                return ok
        except Exception as e:
            if self._logger:
                self._logger.error(f"相机重启失败: {e}")
            return False
        return False

    def _check_detector(self) -> bool:
        try:
            # 简单认为加载成功即健康；如需细化，可执行一次空推理/自检
            return self.detector is not None
        except Exception:
            return False

    def _restart_detector(self) -> bool:
        """重启检测器"""
        try:
            self.detector = create_detector(self._cfg, logger=self._logger)
            self.detector.load()
            # 重新绑定到路由
            self.router.bind(detector=self.detector)
            if self._logger:
                self._logger.info("检测器已重启")
            # 重启后预热推理
            self._warmup_detector()
            return True
        except Exception as e:
            if self._logger:
                self._logger.error(f"检测器重启失败: {e}")
            self.detector = None
            return False

    def _check_sftp(self) -> bool:
        """检查SFTP客户端健康状态"""
        if self.sftp is None:
            return False
        
        # 检查SFTP连接是否真正活跃
        try:
            return self.sftp.healthy
        except Exception:
            return False
    
    def _restart_sftp(self) -> bool:
        """重启SFTP客户端（静默重试，作为非关键组件）"""
        sftp_cfg = (self._cfg.get("sftp") or {})
        try:
            # 先断开旧连接
            if self.sftp:
                try:
                    self.sftp.disconnect()
                except Exception:
                    pass
            
            # 重新创建SFTP客户端实例
            self.sftp = SftpClient(sftp_cfg, logger=self._logger)
            
            # 静默尝试连接（verbose=False，不输出错误日志）
            ok = self.sftp.connect(verbose=False)
            if not ok:
                self.sftp = None
                return False
            
            # 重新绑定到路由
            self.router.bind(sftp=self.sftp)
            
            # 连接成功，记录一次日志
            if self._logger:
                self._logger.info(f"SFTP客户端已重启 | {sftp_cfg.get('host')}")
            return True
        except Exception:
            # 静默失败
            self.sftp = None
            return False

