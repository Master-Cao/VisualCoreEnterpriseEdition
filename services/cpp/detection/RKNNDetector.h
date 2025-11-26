#pragma once
#include "DetectorLib.h"
#ifdef RKNN_AVAILABLE
#include <rknn_api.h>
#else
// Mock RKNN types for Windows compilation
typedef void* rknn_context;
typedef int rknn_core_mask;
#define RKNN_NPU_CORE_0_1_2 0
#endif
#include <vector>
#include <string>
#include <memory>
#include <cmath>

/**
 * RKNN YOLOv8-Seg 检测器
 * 支持256x256输入的分割模型
 */
class RKNNDetector : public DetectionService {
public:
    /**
     * 构造函数
     * @param model_path RKNN模型文件路径
     * @param conf_threshold 置信度阈值
     * @param nms_threshold NMS阈值
     * @param target 目标平台 ("rk3588", "rk3566"等)
     */
    RKNNDetector(
        const std::string& model_path,
        float conf_threshold = 0.5f,
        float nms_threshold = 0.45f,
        const std::string& target = "rk3588"
    );
    
    ~RKNNDetector() override;
    
    void load() override;
    
    std::vector<DetectionBox> detect(
        const uint8_t* image_data,
        int height,
        int width,
        int channels
    ) override;
    
    void release() override;

private:
    // 辅助函数
    void generateMeshgrid();
    
    void postprocessBoxes(
        const std::vector<float*>& outputs,
        const std::vector<int>& output_sizes,
        int img_h, 
        int img_w,
        std::vector<float>& boxes_xmin,
        std::vector<float>& boxes_ymin,
        std::vector<float>& boxes_xmax,
        std::vector<float>& boxes_ymax,
        std::vector<float>& scores,
        std::vector<int>& classes,
        std::vector<std::vector<float>>& mask_coeffs
    );
    
    std::vector<int> nmsRect(
        const std::vector<float>& boxes_xmin,
        const std::vector<float>& boxes_ymin,
        const std::vector<float>& boxes_xmax,
        const std::vector<float>& boxes_ymax,
        const std::vector<float>& scores,
        const std::vector<int>& classes
    );
    
    std::vector<std::vector<uint8_t>> decodeMasks(
        const float* proto_output,
        int proto_c,
        int proto_h,
        int proto_w,
        const std::vector<std::vector<float>>& mask_coeffs,
        const std::vector<float>& boxes_xmin,
        const std::vector<float>& boxes_ymin,
        const std::vector<float>& boxes_xmax,
        const std::vector<float>& boxes_ymax,
        int img_h, 
        int img_w
    );
    
    inline float sigmoid(float x) const {
        return 1.0f / (1.0f + std::exp(-x));
    }
    
    float calcIoU(
        float xmin1, float ymin1, float xmax1, float ymax1,
        float xmin2, float ymin2, float xmax2, float ymax2
    ) const;
    
    // 图像预处理
    std::vector<uint8_t> preprocessImage(
        const uint8_t* image_data,
        int height,
        int width,
        int channels,
        int& out_h,
        int& out_w
    );

    // 成员变量
    std::string model_path_;
    float conf_threshold_;
    float nms_threshold_;
    std::string target_;
    
    rknn_context ctx_;
    bool loaded_;
    
    // YOLOv8-Seg 256x256 模型参数
    int input_width_;
    int input_height_;
    int class_num_;
    int head_num_;
    std::vector<int> strides_;
    std::vector<std::pair<int, int>> map_sizes_;
    int mask_num_;
    std::vector<float> meshgrid_;
};

