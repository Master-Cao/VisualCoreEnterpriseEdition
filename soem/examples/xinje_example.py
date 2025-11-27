#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
信捷 DS5C1S 伺服单轴速度控制示例 (PV模式)
适用于传送带启停控制
"""

import sys
import time
import logging

sys.path.insert(0, '..')

from ethercat_master import EtherCATMaster
from xinje_servo import XinJeDS5C1S
from servo_drive import ServoMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数 - 信捷 DS5C1S 伺服 PV 模式控制"""
    
    logger.info("=== 信捷 DS5C1S 伺服单轴速度控制 (PV模式) ===")
    
    # 配置参数
    INTERFACE = "\\Device\\NPF_{YOUR_NETWORK_ADAPTER_GUID}"  # 修改为您的网卡
    SLAVE_INDEX = 0      # 从站索引（通常为0）
    
    # 创建 EtherCAT 主站
    master = EtherCATMaster(INTERFACE, logger=logger)
    
    try:
        # 1. 打开主站
        logger.info("1. 打开 EtherCAT 主站...")
        if not master.open():
            logger.error("打开失败！请检查网卡名称")
            return
        
        # 2. 扫描从站
        logger.info("2. 扫描 EtherCAT 从站...")
        slave_count = master.scan_slaves()
        if slave_count == 0:
            logger.error("未发现从站！请检查：")
            logger.error("  - 伺服驱动器是否上电")
            logger.error("  - 网线是否连接")
            logger.error("  - 驱动器是否支持 EtherCAT")
            return
        logger.info(f"发现 {slave_count} 个从站")
        
        # 3. 配置 PDO 映射
        logger.info("3. 配置 PDO 映射...")
        master.config_map()
        
        # 4. 创建信捷 DS5C1S 伺服对象（PV模式）
        logger.info("4. 创建信捷 DS5C1S 伺服对象（PV 模式）...")
        servo = XinJeDS5C1S(master, SLAVE_INDEX, pdo_mode='velocity', logger=logger)
        
        # 5. 设置为 PV 模式（Profile Velocity，模式代码 3）
        logger.info("5. 设置工作模式为 PV...")
        servo.set_mode(ServoMode.PROFILE_VELOCITY)  # 模式 3
        
        # 6. 配置 PV 模式参数（通过SDO）
        logger.info("6. 配置 PV 模式参数...")
        servo.configure_pv_parameters()  # 配置加减速度等参数
        
        # 7. 进入 OPERATIONAL 状态
        logger.info("7. 进入 OPERATIONAL 状态...")
        if not master.set_operational():
            logger.error("无法进入 OPERATIONAL 状态")
            return
        
        # 8. 定义周期性数据处理回调
        def process_data():
            """
            每1ms执行一次
            在 PV 模式下：
            - 读取速度反馈（0x606C）
            - 发送目标速度（0x60FF）
            """
            servo.read_inputs()   # 读取伺服反馈（速度）
            if not servo.is_enabled:
                servo.enable()    # 尝试使能
            servo.write_outputs() # 发送命令（目标速度）
        
        master.set_process_data_callback(process_data)
        master.start_cycle(0.001)  # 1ms 循环周期
        
        # 9. 等待伺服使能
        logger.info("8. 等待伺服使能（约100ms）...")
        timeout = 5.0
        start_time = time.time()
        while not servo.is_enabled:
            if time.time() - start_time > timeout:
                logger.error("伺服使能超时！")
                return
            time.sleep(0.1)
        
        logger.info("✅ 伺服已使能，可以控制")
        logger.info("")
        logger.info("=" * 60)
        logger.info("开始 PV 模式速度控制演示")
        logger.info("=" * 60)
        logger.info("注意：速度单位为 '指令单位/s'")
        logger.info("      实际RPM取决于608Fh和6092h的配置")
        logger.info("")
        
        # 10. 速度控制演示（PV模式）
        
        # 演示1：启动 - 低速
        logger.info("[演示1] 启动传送带 - 低速 500")
        servo.set_target_velocity(500)  # 指令单位/s
        time.sleep(3)
        logger.info(f"  当前速度反馈: {servo.velocity}")
        
        # 演示2：加速到中速
        logger.info("\n[演示2] 加速到中速 1000")
        servo.set_target_velocity(1000)
        time.sleep(3)
        logger.info(f"  当前速度反馈: {servo.velocity}")
        
        # 演示3：加速到高速
        logger.info("\n[演示3] 加速到高速 1500")
        servo.set_target_velocity(1500)
        time.sleep(3)
        logger.info(f"  当前速度反馈: {servo.velocity}")
        
        # 演示4：减速
        logger.info("\n[演示4] 减速到 500")
        servo.set_target_velocity(500)
        time.sleep(3)
        logger.info(f"  当前速度反馈: {servo.velocity}")
        
        # 演示5：停止
        logger.info("\n[演示5] 停止传送带")
        servo.set_target_velocity(0)
        time.sleep(2)
        logger.info(f"  当前速度反馈: {servo.velocity}")
        logger.info("  ✅ 传送带已停止")
        
        # 演示6：反转
        logger.info("\n[演示6] 反转运行 -1000")
        servo.set_target_velocity(-1000)
        time.sleep(3)
        logger.info(f"  当前速度反馈: {servo.velocity}")
        
        # 演示7：停止
        logger.info("\n[演示7] 再次停止")
        servo.set_target_velocity(0)
        time.sleep(2)
        logger.info(f"  当前速度反馈: {servo.velocity}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 演示完成！")
        logger.info("=" * 60)
        
        # 11. 进入手动控制模式（可选）
        logger.info("\n进入手动控制模式...")
        logger.info("输入速度值来控制伺服，输入 'q' 退出")
        logger.info("  正数 = 正转，负数 = 反转，0 = 停止")
        logger.info("  速度单位：指令单位/s（根据编码器和Feed常数配置）")
        
        try:
            while True:
                logger.info(f"\n当前状态: 速度反馈={servo.velocity}, "
                          f"状态={servo.get_state().name}, "
                          f"状态字=0x{servo.statusword:04X}")
                
                cmd = input("输入速度 (或 q 退出): ").strip()
                
                if cmd.lower() == 'q':
                    break
                
                try:
                    speed = int(cmd)
                    logger.info(f"设置目标速度: {speed}")
                    servo.set_target_velocity(speed)
                except ValueError:
                    logger.warning("无效输入，请输入数字")
        
        except KeyboardInterrupt:
            logger.info("\n用户中断")
        
        # 停止伺服
        logger.info("\n停止伺服...")
        servo.set_target_velocity(0)
        time.sleep(1)
        
    finally:
        # 12. 关闭主站
        logger.info("关闭 EtherCAT 主站...")
        master.close()
        logger.info("程序结束")


if __name__ == "__main__":
    main()

