#pragma once
#include <vector>
#include <string>
#include <memory>
#include <cstdint>

// 检测框结构
struct DetectionBox {
    int class_id;
    float score;
    int xmin;
    int ymin;
    int xmax;
    int ymax;
    std::vector<uint8_t> seg_mask;  // 分割掩码数据 (H * W)
    int mask_height;
    int mask_width;
    
    DetectionBox() 
        : class_id(0), score(0.0f), 
          xmin(0), ymin(0), xmax(0), ymax(0),
          mask_height(0), mask_width(0) {}
};

// 检测器基类
class DetectionService {
public:
    virtual ~DetectionService() = default;
    
    /**
     * 加载模型
     */
    virtual void load() = 0;
    
    /**
     * 执行检测
     * @param image_data 图像数据指针 (BGR或灰度格式)
     * @param height 图像高度
     * @param width 图像宽度
     * @param channels 图像通道数 (1=灰度, 3=BGR)
     * @return 检测结果列表
     */
    virtual std::vector<DetectionBox> detect(
        const uint8_t* image_data,
        int height,
        int width,
        int channels
    ) = 0;
    
    /**
     * 释放资源
     */
    virtual void release() = 0;
};

