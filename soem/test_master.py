#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EtherCAT 主站测试脚本
用于验证主站实现的正确性
"""

import logging
import time
from ethercat_master import EtherCATMaster

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_basic_connection():
    """测试1：基本连接"""
    logger.info("=" * 60)
    logger.info("测试1：基本连接和扫描")
    logger.info("=" * 60)
    
    # 修改为您的网卡接口
    interface = "eth0"
    
    master = EtherCATMaster(interface, logger=logger)
    
    try:
        # 打开主站
        if not master.open():
            logger.error("❌ 打开主站失败")
            return False
        
        logger.info("✅ 主站已打开")
        
        # 扫描从站
        slave_count = master.scan_slaves()
        if slave_count == 0:
            logger.warning("⚠️ 未发现从站（这可能是正常的，如果没有连接设备）")
            return True
        
        logger.info(f"✅ 发现 {slave_count} 个从站")
        
        # 配置 PDO 映射
        if not master.config_map():
            logger.error("❌ PDO 映射配置失败")
            return False
        
        logger.info("✅ PDO 映射配置成功")
        
        # 显示从站信息
        for i, slave in enumerate(master.slaves):
            logger.info(f"\n从站 {i} 详细信息:")
            logger.info(f"  名称: {slave.name}")
            logger.info(f"  厂商ID: 0x{slave.man:08X}")
            logger.info(f"  产品代码: 0x{slave.id:08X}")
            logger.info(f"  输入字节数: {slave.ibytes}")
            logger.info(f"  输出字节数: {slave.obytes}")
        
        return True
        
    finally:
        master.close()


def test_sdo_operations():
    """测试2：SDO 读写操作"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2：SDO 读写操作")
    logger.info("=" * 60)
    
    interface = "eth0"
    master = EtherCATMaster(interface, logger=logger)
    
    try:
        if not master.open():
            return False
        
        slave_count = master.scan_slaves()
        if slave_count == 0:
            logger.warning("⚠️ 没有从站可以测试 SDO")
            return True
        
        master.config_map()
        
        # 测试读取标准 CiA 对象
        logger.info("\n尝试读取从站 0 的标准对象...")
        
        # 读取设备类型 (0x1000)
        device_type = master.sdo_read(0, 0x1000, 0, 'I')
        if device_type is not None:
            logger.info(f"✅ 设备类型 (0x1000): 0x{device_type:08X}")
        
        # 读取设备名称 (0x1008)
        # 注意：字符串读取需要特殊处理
        try:
            # 先读取长度
            name_data = master._master.sdo_read(1, 0x1008, 0, 128)
            if name_data:
                device_name = name_data.decode('utf-8', errors='ignore').rstrip('\x00')
                logger.info(f"✅ 设备名称 (0x1008): {device_name}")
        except Exception as e:
            logger.warning(f"⚠️ 读取设备名称失败: {e}")
        
        # 读取厂商ID (0x1018.01)
        vendor_id = master.sdo_read(0, 0x1018, 1, 'I')
        if vendor_id is not None:
            logger.info(f"✅ 厂商ID (0x1018.01): 0x{vendor_id:08X}")
        
        # 读取产品代码 (0x1018.02)
        product_code = master.sdo_read(0, 0x1018, 2, 'I')
        if product_code is not None:
            logger.info(f"✅ 产品代码 (0x1018.02): 0x{product_code:08X}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ SDO 测试失败: {e}")
        return False
    finally:
        master.close()


def test_operational_state():
    """测试3：进入 OPERATIONAL 状态"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3：进入 OPERATIONAL 状态")
    logger.info("=" * 60)
    
    interface = "eth0"
    master = EtherCATMaster(interface, logger=logger)
    
    try:
        if not master.open():
            return False
        
        slave_count = master.scan_slaves()
        if slave_count == 0:
            logger.warning("⚠️ 没有从站可以测试状态转换")
            return True
        
        master.config_map()
        
        # 尝试进入 OPERATIONAL 状态
        if master.set_operational():
            logger.info("✅ 成功进入 OPERATIONAL 状态")
            
            # 保持一段时间
            logger.info("保持 OPERATIONAL 状态 3 秒...")
            time.sleep(3)
            
            return True
        else:
            logger.error("❌ 未能进入 OPERATIONAL 状态")
            return False
        
    except Exception as e:
        logger.error(f"❌ 状态转换测试失败: {e}")
        return False
    finally:
        master.close()


def main():
    """运行所有测试"""
    logger.info("\n\n")
    logger.info("*" * 60)
    logger.info("EtherCAT 主站测试套件")
    logger.info("*" * 60)
    
    tests = [
        ("基本连接", test_basic_connection),
        ("SDO操作", test_sdo_operations),
        ("OPERATIONAL状态", test_operational_state),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"测试 '{test_name}' 异常: {e}")
            results[test_name] = False
        
        time.sleep(1)  # 测试间隔
    
    # 显示结果
    logger.info("\n\n")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name:20s}: {status}")
    
    all_passed = all(results.values())
    logger.info("\n" + ("="*60))
    if all_passed:
        logger.info("🎉 所有测试通过！")
    else:
        logger.info("⚠️ 部分测试失败")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

