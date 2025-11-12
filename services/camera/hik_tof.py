import ctypes
import time
from ctypes import *
import numpy as np
import cv2
import logging
import sys
import os

# 修复 HikTOF SDK 导入路径：从 infrastructure.hikTof 中导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from infrastructure.hikTof.Mv3dRgbdImport.Mv3dRgbdDefine import *
from infrastructure.hikTof.Mv3dRgbdImport.Mv3dRgbdApi import *
from infrastructure.hikTof.Mv3dRgbdImport.Mv3dRgbdDefine import (
    DeviceType_Ethernet, DeviceType_USB, DeviceType_Ethernet_Vir, DeviceType_USB_Vir,
    MV3D_RGBD_FLOAT_EXPOSURETIME, ParamType_Float, ParamType_Int, ParamType_Enum,
    CoordinateType_Depth, MV3D_RGBD_FLOAT_Z_UNIT, MV3D_RGBD_OK, FileType_BMP,
    ImageType_PointCloud, PointCloudFileType_PLY, FileType_JPG, ImageType_Depth,
    ImageType_RGB8_Planar, ImageType_YUV420SP_NV12, ImageType_YUV420SP_NV21,
    ImageType_YUV422, ImageType_Mono8, MV3D_RGBD_ENUM_WORKINGMODE, MV3D_RGBD_ENUM_IMAGEMODE
)


class HikCamera:
    def __init__(self, cameraType, Save = False, SavePath = "./", ):
        """初始化相机对象并配置保存选项。
        参数:
            cameraType: 相机类型,支持 ir | rgbd | pointCloud
            Save: 是否保存采集图像到磁盘
            SavePath: 图像保存目录
        """
        self.Save = Save
        self.SavePath = SavePath
        self.cameraType = cameraType
        self.camera = self._build()

    def _build(self, ):
        """枚举并连接第一个可用设备，返回相机句柄；失败返回 None。"""
        nDeviceNum=ctypes.c_uint(0)
        nDeviceNum_p=byref(nDeviceNum)
        # ch:获取设备数量 | en:Get device number
        ret=Mv3dRgbd.MV3D_RGBD_GetDeviceNumber(DeviceType_Ethernet | DeviceType_USB | DeviceType_Ethernet_Vir | DeviceType_USB_Vir, nDeviceNum_p) 
        if  ret!=0:
            print("MV3D_RGBD_GetDeviceNumber fail! ret[0x%x]" % ret)
            return None
        if  nDeviceNum==0:
            print("find no device!")
            return None
        print("Find devices numbers:", nDeviceNum.value)
        stDeviceList = MV3D_RGBD_DEVICE_INFO_LIST()
        net = Mv3dRgbd.MV3D_RGBD_GetDeviceList(DeviceType_Ethernet | DeviceType_USB | DeviceType_Ethernet_Vir | DeviceType_USB_Vir, pointer(stDeviceList.DeviceInfo[0]), 20, nDeviceNum_p)
        for i in range(0, nDeviceNum.value):
            print("\ndevice: [%d]" % i)
            strModeName = ""
            for per in stDeviceList.DeviceInfo[i].chModelName:
                strModeName = strModeName + chr(per)
            print("device model name: %s" % strModeName)
            strSerialNumber = ""
            for per in stDeviceList.DeviceInfo[i].chSerialNumber:
                strSerialNumber = strSerialNumber + chr(per)
            print("device SerialNumber: %s" % strSerialNumber)
        camera=Mv3dRgbd()
        print("默认连接第一个设备")
        nConnectionNum = 0   # 默认连接第一个设备
        ret = camera.MV3D_RGBD_OpenDevice(pointer(stDeviceList.DeviceInfo[int(nConnectionNum)]))
        if ret != 0:
          print("Open device failed")
          return None
        mode_name = ""
        for per in stDeviceList.DeviceInfo[nConnectionNum].chSerialNumber:
            mode_name = mode_name + chr(per)
        if self.cameraType == "ir":
            work_mode = MV3D_RGBD_PARAM()
            work_mode.enParamType = 4
            work_mode.ParamInfo.stEnumParam.nCurValue=0
            ret1=camera.MV3D_RGBD_SetParam(MV3D_RGBD_ENUM_WORKINGMODE, pointer(work_mode))
            if MV3D_RGBD_OK != ret1:
                print ("SetParam fail! ret[0x%x]" % ret1)
                camera.MV3D_RGBD_CloseDevice()
                return None
        elif self.cameraType == "rgbd":
            work_mode = MV3D_RGBD_PARAM()
            work_mode.enParamType = 4
            work_mode.ParamInfo.stEnumParam.nCurValue = 4
            ret1=camera.MV3D_RGBD_SetParam(MV3D_RGBD_ENUM_WORKINGMODE, pointer(work_mode))
            if MV3D_RGBD_OK != ret1:
                print ("SetParam fail! ret[0x%x]" % ret1)
                camera.MV3D_RGBD_CloseDevice()
                return None
        elif self.cameraType == "pointCloud":
            work_mode2 = MV3D_RGBD_PARAM()
            work_mode2.enParamType = 4
            work_mode2.ParamInfo.stEnumParam.nCurValue = 1
            ret1=self.camera.MV3D_RGBD_SetParam(MV3D_RGBD_ENUM_WORKINGMODE, pointer(work_mode2))
            if MV3D_RGBD_OK != ret1:
                print ("SetParam fail! ret[0x%x]" % ret1)
                self.camera.MV3D_RGBD_CloseDevice()
                return False
        time.sleep(0.1)
        ret = camera.MV3D_RGBD_Start()
        if ret != 0:
            camera.MV3D_RGBD_CloseDevice()
            return None
        print("设备连接成功和初始化成功,设备型号为:%s"%mode_name)
        return camera

    def get_intensity_image(self, ) -> np.ndarray:
        """采集红外/灰度图，返回 uint8 的 (H, W) ndarray；失败返回 None。"""
        image = np.array([])
        # Get the number of devices
        if self.camera is None:
            print("相机未正确初始化,请检查.....")
            return None
        stFrameData = MV3D_RGBD_FRAME_DATA()
        # ch:获取图像数据 | en:Get image data
        ret = self.camera.MV3D_RGBD_FetchFrame(pointer(stFrameData), 5000)
        if MV3D_RGBD_OK == ret:
            for i in range(0, stFrameData.nImageCount):
                if ImageType_Mono8 == stFrameData.stImageData[i].enImageType:
                    print("Get mono image succeed: framenum (%d) height(%d) width(%d) len(%d)!" % (stFrameData.stImageData[i].nFrameNum,
                        stFrameData.stImageData[i].nHeight, stFrameData.stImageData[i].nWidth, stFrameData.stImageData[i].nDataLen))
                    chMonoFileName = "[{:d}]_Mono".format(stFrameData.stImageData[i].nFrameNum)
                    if self.Save:
                        ret = self.camera.MV3D_RGBD_SaveImage(pointer(stFrameData.stImageData[i]), FileType_BMP, chMonoFileName)
                        if MV3D_RGBD_OK == ret:
                            print("Save mono image success.")
                        else:
                            print("Save mono image failed.")
                    image_bytes = string_at(stFrameData.stImageData[i].pData,stFrameData.stImageData[i].nDataLen)
                    image = np.frombuffer(image_bytes, dtype=np.uint8).reshape(stFrameData.stImageData[i].nHeight, stFrameData.stImageData[i].nWidth)
        else:
            print("MV3D_RGBD_FetchFrame lost frame!")
            # ch:停止取流 | en:Stop grabbing
            ret=self.camera.MV3D_RGBD_Stop()
            if ret != 0:
                print ("stop fail! ret[0x%x]" % ret)
                return None
        return image
    
    def get_rgb_image(self, ) -> np.ndarray:
        """自动解码 RGB8 Planar / NV12 / NV21 / YUV422，
        统一返回 uint8 的 (H, W, 3) RGB；失败返回 None。"""
        image = np.array([])
        if self.camera is None:
            print("相机未正确初始化,请检查.....")
            return None
        stFrameData = MV3D_RGBD_FRAME_DATA()
        # ch:获取图像数据 | en:Get image data
        ret = self.camera.MV3D_RGBD_FetchFrame(pointer(stFrameData), 5000)
        if MV3D_RGBD_OK == ret:
            for i in range(0, stFrameData.nImageCount):
                img_info = stFrameData.stImageData[i]
                img_type = img_info.enImageType
                h, w, data_len = img_info.nHeight, img_info.nWidth, img_info.nDataLen
                if img_type in (ImageType_RGB8_Planar, ImageType_YUV420SP_NV12, ImageType_YUV420SP_NV21, ImageType_YUV422):
                    print("Get color image succeed: framenum (%d) height(%d) width(%d) len(%d)!" % (img_info.nFrameNum, h, w, data_len))
                    chColorFileName = "[{:d}]_Color".format(img_info.nFrameNum)
                    if self.Save:
                        ret = self.camera.MV3D_RGBD_SaveImage(pointer(img_info), FileType_JPG, chColorFileName)
                        if MV3D_RGBD_OK == ret:
                            print("Save color image success.")
                        else:
                            print("Save color image failed.")
                    buf = string_at(img_info.pData, data_len)
                    if img_type == ImageType_RGB8_Planar:
                        # 平面RGB -> HWC RGB
                        chw = np.frombuffer(buf, dtype=np.uint8).reshape(3, h, w)
                        image = np.transpose(chw, (1, 2, 0))
                    elif img_type == ImageType_YUV420SP_NV12:
                        # NV12: (H + H/2, W), 格式 Y + interleaved UV
                        yuv = np.frombuffer(buf, dtype=np.uint8).reshape((h * 3) // 2, w)
                        image = cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB_NV12)
                    elif img_type == ImageType_YUV420SP_NV21:
                        # NV21: (H + H/2, W), 格式 Y + interleaved VU
                        yuv = np.frombuffer(buf, dtype=np.uint8).reshape((h * 3) // 2, w)
                        image = cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB_NV21)
                    elif img_type == ImageType_YUV422:
                        # 视为YUY2: 每像素16bit，按 (H, W*2) 交错
                        yuy2 = np.frombuffer(buf, dtype=np.uint8).reshape(h, w * 2)
                        image = cv2.cvtColor(yuy2, cv2.COLOR_YUV2RGB_YUY2)
        else:
            print("MV3D_RGBD_FetchFrame lost frame!")
            # ch:停止取流 | en:Stop grabbing
            ret=self.camera.MV3D_RGBD_Stop()
            if ret != 0:
                print ("stop fail! ret[0x%x]" % ret)
                return None
        return image
    
    def get_depth_image(self, ) -> np.ndarray:
        """采集深度图，返回 uint16 的 (H, W) 深度矩阵（单位由 SDK 决定）；失败返回 None。"""
        image = np.array([])
        if self.camera is None:
            print("相机未正确初始化,请检查.....")
            return None
        # ret = self.camera.MV3D_RGBD_Start()
        # if ret != 0:
        #     self.camera.MV3D_RGBD_CloseDevice()
        #     return None
        stFrameData = MV3D_RGBD_FRAME_DATA()
        # ch:获取图像数据 | en:Get image data
        ret = self.camera.MV3D_RGBD_FetchFrame(pointer(stFrameData), 5000)
        if MV3D_RGBD_OK == ret:
            for i in range(0, stFrameData.nImageCount):
                img_info = stFrameData.stImageData[i]
                if ImageType_Depth == img_info.enImageType:
                    print("Get depth image succeed: framenum (%d) height(%d) width(%d) len(%d)!" %( img_info.nFrameNum,
                    img_info.nHeight, img_info.nWidth, img_info.nDataLen))
                    chDepthFileName ="[{:d}]_Depth".format(img_info.nFrameNum)
                    if self.Save:
                        ret = self.camera.MV3D_RGBD_SaveImage(pointer(img_info), FileType_JPG, chDepthFileName)
                        if MV3D_RGBD_OK == ret:
                            print("Save depth image success.")
                        else:
                            print("Save depth image failed.")
                    buf = string_at(img_info.pData, img_info.nDataLen)
                    # 将两字节的深度数据还原为 uint16 (H, W)
                    image = np.frombuffer(buf, dtype=np.uint16).reshape(img_info.nHeight, img_info.nWidth)
        else:
            print("MV3D_RGBD_FetchFrame lost frame!")
            # ch:停止取流 | en:Stop grabbing
            ret=self.camera.MV3D_RGBD_Stop()
            if ret != 0:
                print ("stop fail! ret[0x%x]" % ret)
                return None
        return image
    
    def get_point_cloud_ply(self, ) -> bool:
        """采集点云并保存为 PLY 文件，成功返回 True，失败返回 False。"""
        if self.camera is None:
            print("相机未正确初始化,请检查.....")
            return False
        
        stFrameData = MV3D_RGBD_FRAME_DATA()
        # ch:获取图像数据 | en:Get image data
        ret = self.camera.MV3D_RGBD_FetchFrame(pointer(stFrameData), 5000)
        if MV3D_RGBD_OK == ret:
            print("MV3D_RGBD_FetchFrame success.")
            for i in range(0, stFrameData.nImageCount):
                # ch:解析点云数据 | en:Parse point cloud data
                if ImageType_PointCloud == stFrameData.stImageData[i].enImageType:
                    print("Get point cloud succeed: framenum (%d) height(%d) width(%d) len(%d)!" %(stFrameData.stImageData[i].nFrameNum,
                            stFrameData.stImageData[i].nHeight, stFrameData.stImageData[i].nWidth, stFrameData.stImageData[i].nDataLen))
                    # ch:保存点云图像 | en:Save point cloud image
                    chFileName = "[{:d}]_PointCloudImage".format(stFrameData.stImageData[i].nFrameNum)
                    ret = self.camera.MV3D_RGBD_SavePointCloudImage(pointer(stFrameData.stImageData[i]), PointCloudFileType_PLY, chFileName)
                    if MV3D_RGBD_OK == ret:
                        print("Save %s success!" % chFileName)
        else:
            print("MV3D_RGBD_FetchFrame lost frame!")
            # ch:停止取流 | en:Stop grabbing
            ret=self.camera.MV3D_RGBD_Stop()
            if ret != 0:
                print ("stop fail! ret[0x%x]" % ret)
                return False
        return True


    def close(self):
        """关闭设备连接并释放资源。"""
        # 先停止流.再关闭设备,可能会停止失败。不影响使用
        ret=self.camera.MV3D_RGBD_Stop()
        if ret != 0:
            print ("stop fail! ret[0x%x]" % ret)
            return None
        if self.camera is not None:
            self.camera.MV3D_RGBD_CloseDevice()
            self.camera = None

    def __del__(self):
        """析构时确保设备已关闭。"""
        if self.camera is not None:
            self.camera.MV3D_RGBD_CloseDevice()