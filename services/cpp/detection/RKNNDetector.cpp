#include "RKNNDetector.h"
#include <cmath>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <cstring>
#include <stdexcept>

#ifndef RKNN_AVAILABLE
// Mock RKNN definitions for Windows
#define RKNN_SUCC 0
struct rknn_input {
    int index;
    int type;
    int size;
    int fmt;
    void* buf;
};
struct rknn_output {
    int index;
    int want_float;
    void* buf;
    int size;
};
#define RKNN_TENSOR_UINT8 0
#define RKNN_TENSOR_NHWC 0
static int rknn_init(rknn_context* ctx, void* data, int size, int flag, void* ext) { return -1; }
static int rknn_set_core_mask(rknn_context ctx, rknn_core_mask mask) { return -1; }
static int rknn_inputs_set(rknn_context ctx, int n, rknn_input* inputs) { return -1; }
static int rknn_run(rknn_context ctx, void* ext) { return -1; }
static int rknn_outputs_get(rknn_context ctx, int n, rknn_output* outputs, void* ext) { return -1; }
static int rknn_outputs_release(rknn_context ctx, int n, rknn_output* outputs) { return -1; }
static int rknn_destroy(rknn_context ctx) { return -1; }
#endif

RKNNDetector::RKNNDetector(
    const std::string& model_path,
    float conf_threshold,
    float nms_threshold,
    const std::string& target
) : model_path_(model_path),
    conf_threshold_(conf_threshold),
    nms_threshold_(nms_threshold),
    target_(target),
    ctx_(0),
    loaded_(false),
    input_width_(256),
    input_height_(256),
    class_num_(2),
    head_num_(3),
    mask_num_(32)
{
    strides_ = {8, 16, 32};
    map_sizes_ = {{32, 32}, {16, 16}, {8, 8}};
    generateMeshgrid();
}

RKNNDetector::~RKNNDetector() {
    release();
}

void RKNNDetector::generateMeshgrid() {
    meshgrid_.clear();
    for (int idx = 0; idx < head_num_; ++idx) {
        int h = map_sizes_[idx].first;
        int w = map_sizes_[idx].second;
        for (int i = 0; i < h; ++i) {
            for (int j = 0; j < w; ++j) {
                meshgrid_.push_back(static_cast<float>(j) + 0.5f);
                meshgrid_.push_back(static_cast<float>(i) + 0.5f);
            }
        }
    }
}

void RKNNDetector::load() {
#ifndef RKNN_AVAILABLE
    throw std::runtime_error(
        "RKNN is not available on this platform (Windows). "
        "Please use this module on Linux/ARM platforms with RKNN support."
    );
#else
    // 读取RKNN模型文件
    std::ifstream file(model_path_, std::ios::binary | std::ios::ate);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open model file: " + model_path_);
    }
    
    size_t model_size = file.tellg();
    file.seekg(0, std::ios::beg);
    
    std::vector<uint8_t> model_data(model_size);
    file.read(reinterpret_cast<char*>(model_data.data()), model_size);
    file.close();
    
    // 初始化RKNN
    int ret = rknn_init(&ctx_, model_data.data(), model_size, 0, nullptr);
    if (ret != RKNN_SUCC) {
        throw std::runtime_error("RKNN initialization failed, error code: " + std::to_string(ret));
    }
    
    // 设置多核NPU
    rknn_core_mask core_mask = RKNN_NPU_CORE_0_1_2;
    ret = rknn_set_core_mask(ctx_, core_mask);
    if (ret != RKNN_SUCC) {
        std::cerr << "Warning: Failed to set NPU core mask, error code: " << ret << std::endl;
    }
    
    loaded_ = true;
    std::cout << "RKNN model loaded successfully: " << model_path_ << std::endl;
#endif
}

std::vector<uint8_t> RKNNDetector::preprocessImage(
    const uint8_t* image_data,
    int height,
    int width,
    int channels,
    int& out_h,
    int& out_w
) {
    out_h = input_height_;
    out_w = input_width_;
    
    std::vector<uint8_t> resized(out_h * out_w * 3);
    
    // 简单的最近邻插值resize（实际应用中可以使用更高质量的插值）
    float scale_h = static_cast<float>(height) / out_h;
    float scale_w = static_cast<float>(width) / out_w;
    
    for (int y = 0; y < out_h; ++y) {
        for (int x = 0; x < out_w; ++x) {
            int src_y = static_cast<int>(y * scale_h);
            int src_x = static_cast<int>(x * scale_w);
            
            if (src_y >= height) src_y = height - 1;
            if (src_x >= width) src_x = width - 1;
            
            int dst_idx = (y * out_w + x) * 3;
            int src_idx = (src_y * width + src_x) * channels;
            
            if (channels == 1) {
                // 灰度图转BGR
                resized[dst_idx + 0] = image_data[src_idx];
                resized[dst_idx + 1] = image_data[src_idx];
                resized[dst_idx + 2] = image_data[src_idx];
            } else if (channels == 3) {
                // BGR保持不变，但需要转RGB
                resized[dst_idx + 0] = image_data[src_idx + 2];  // R
                resized[dst_idx + 1] = image_data[src_idx + 1];  // G
                resized[dst_idx + 2] = image_data[src_idx + 0];  // B
            } else if (channels == 4) {
                // BGRA转RGB
                resized[dst_idx + 0] = image_data[src_idx + 2];  // R
                resized[dst_idx + 1] = image_data[src_idx + 1];  // G
                resized[dst_idx + 2] = image_data[src_idx + 0];  // B
            }
        }
    }
    
    return resized;
}

std::vector<DetectionBox> RKNNDetector::detect(
    const uint8_t* image_data,
    int height,
    int width,
    int channels
) {
#ifndef RKNN_AVAILABLE
    throw std::runtime_error(
        "RKNN is not available on this platform (Windows). "
        "This is a stub implementation for compilation only."
    );
    return {};
#else
    if (!loaded_) {
        load();
    }
    
    // 预处理图像
    int img_h = height;
    int img_w = width;
    int resized_h, resized_w;
    std::vector<uint8_t> resized_img = preprocessImage(
        image_data, height, width, channels, resized_h, resized_w
    );
    
    // 准备RKNN输入
    rknn_input inputs[1];
    memset(inputs, 0, sizeof(inputs));
    inputs[0].index = 0;
    inputs[0].type = RKNN_TENSOR_UINT8;
    inputs[0].size = resized_h * resized_w * 3;
    inputs[0].fmt = RKNN_TENSOR_NHWC;
    inputs[0].buf = resized_img.data();
    
    int ret = rknn_inputs_set(ctx_, 1, inputs);
    if (ret != RKNN_SUCC) {
        std::cerr << "Failed to set RKNN inputs, error code: " << ret << std::endl;
        return {};
    }
    
    // 执行推理
    ret = rknn_run(ctx_, nullptr);
    if (ret != RKNN_SUCC) {
        std::cerr << "RKNN inference failed, error code: " << ret << std::endl;
        return {};
    }
    
    // 获取输出数量
    rknn_output outputs[10];
    memset(outputs, 0, sizeof(outputs));
    for (int i = 0; i < 10; ++i) {
        outputs[i].want_float = 1;
    }
    
    ret = rknn_outputs_get(ctx_, 10, outputs, nullptr);
    if (ret != RKNN_SUCC) {
        std::cerr << "Failed to get RKNN outputs, error code: " << ret << std::endl;
        return {};
    }
    
    // 提取输出数据
    std::vector<float*> output_ptrs;
    std::vector<int> output_sizes;
    for (int i = 0; i < 10; ++i) {
        output_ptrs.push_back(reinterpret_cast<float*>(outputs[i].buf));
        output_sizes.push_back(outputs[i].size / sizeof(float));
    }
    
    // 后处理：解码检测框和mask系数
    std::vector<float> boxes_xmin, boxes_ymin, boxes_xmax, boxes_ymax;
    std::vector<float> scores;
    std::vector<int> classes;
    std::vector<std::vector<float>> mask_coeffs;
    
    postprocessBoxes(
        output_ptrs, output_sizes, img_h, img_w,
        boxes_xmin, boxes_ymin, boxes_xmax, boxes_ymax,
        scores, classes, mask_coeffs
    );
    
    // NMS
    std::vector<int> keep_indices = nmsRect(
        boxes_xmin, boxes_ymin, boxes_xmax, boxes_ymax,
        scores, classes
    );
    
    // 解码分割掩码（proto输出在outputs[9]）
    int proto_c = mask_num_;
    int proto_h = 64;  // YOLOv8-Seg的proto尺寸
    int proto_w = 64;
    
    std::vector<float> kept_boxes_xmin, kept_boxes_ymin, kept_boxes_xmax, kept_boxes_ymax;
    std::vector<std::vector<float>> kept_coeffs;
    
    for (int idx : keep_indices) {
        kept_boxes_xmin.push_back(boxes_xmin[idx]);
        kept_boxes_ymin.push_back(boxes_ymin[idx]);
        kept_boxes_xmax.push_back(boxes_xmax[idx]);
        kept_boxes_ymax.push_back(boxes_ymax[idx]);
        kept_coeffs.push_back(mask_coeffs[idx]);
    }
    
    std::vector<std::vector<uint8_t>> masks = decodeMasks(
        output_ptrs[9], proto_c, proto_h, proto_w,
        kept_coeffs,
        kept_boxes_xmin, kept_boxes_ymin, kept_boxes_xmax, kept_boxes_ymax,
        img_h, img_w
    );
    
    // 构建检测结果
    std::vector<DetectionBox> results;
    for (size_t i = 0; i < keep_indices.size(); ++i) {
        int idx = keep_indices[i];
        DetectionBox box;
        box.class_id = classes[idx];
        box.score = scores[idx];
        box.xmin = static_cast<int>(boxes_xmin[idx]);
        box.ymin = static_cast<int>(boxes_ymin[idx]);
        box.xmax = static_cast<int>(boxes_xmax[idx]);
        box.ymax = static_cast<int>(boxes_ymax[idx]);
        
        if (i < masks.size()) {
            box.seg_mask = masks[i];
            box.mask_height = img_h;
            box.mask_width = img_w;
        }
        
        results.push_back(box);
    }
    
    // 释放RKNN输出
    rknn_outputs_release(ctx_, 10, outputs);
    
    return results;
#endif
}

void RKNNDetector::postprocessBoxes(
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
) {
    float scale_h = static_cast<float>(img_h) / input_height_;
    float scale_w = static_cast<float>(img_w) / input_width_;
    
    int grid_index = -2;
    
    for (int head_idx = 0; head_idx < head_num_; ++head_idx) {
        // YOLOv8输出：reg(回归), cls(分类), mask(掩码系数)
        float* reg = outputs[head_idx * 2 + 0];
        float* cls = outputs[head_idx * 2 + 1];
        float* msk = outputs[6 + head_idx];
        
        int h = map_sizes_[head_idx].first;
        int w = map_sizes_[head_idx].second;
        int stride = strides_[head_idx];
        
        for (int i = 0; i < h; ++i) {
            for (int j = 0; j < w; ++j) {
                grid_index += 2;
                
                for (int class_id = 0; class_id < class_num_; ++class_id) {
                    // 计算分类置信度
                    int cls_idx = class_id * h * w + i * w + j;
                    float cls_val = sigmoid(cls[cls_idx]);
                    
                    if (cls_val <= conf_threshold_) {
                        continue;
                    }
                    
                    // 解码检测框
                    int base_idx = i * w + j;
                    float x1 = (meshgrid_[grid_index + 0] - reg[0 * h * w + base_idx]) * stride;
                    float y1 = (meshgrid_[grid_index + 1] - reg[1 * h * w + base_idx]) * stride;
                    float x2 = (meshgrid_[grid_index + 0] + reg[2 * h * w + base_idx]) * stride;
                    float y2 = (meshgrid_[grid_index + 1] + reg[3 * h * w + base_idx]) * stride;
                    
                    // 缩放到原图尺寸
                    float xmin = std::max(0.0f, x1 * scale_w);
                    float ymin = std::max(0.0f, y1 * scale_h);
                    float xmax = std::min(static_cast<float>(img_w), x2 * scale_w);
                    float ymax = std::min(static_cast<float>(img_h), y2 * scale_h);
                    
                    if (xmax <= xmin || ymax <= ymin) {
                        continue;
                    }
                    
                    // 提取mask系数
                    std::vector<float> mask_vec(mask_num_);
                    for (int m = 0; m < mask_num_; ++m) {
                        mask_vec[m] = msk[m * h * w + base_idx];
                    }
                    
                    boxes_xmin.push_back(xmin);
                    boxes_ymin.push_back(ymin);
                    boxes_xmax.push_back(xmax);
                    boxes_ymax.push_back(ymax);
                    scores.push_back(cls_val);
                    classes.push_back(class_id);
                    mask_coeffs.push_back(mask_vec);
                }
            }
        }
    }
}

float RKNNDetector::calcIoU(
    float xmin1, float ymin1, float xmax1, float ymax1,
    float xmin2, float ymin2, float xmax2, float ymax2
) const {
    float ixmin = std::max(xmin1, xmin2);
    float iymin = std::max(ymin1, ymin2);
    float ixmax = std::min(xmax1, xmax2);
    float iymax = std::min(ymax1, ymax2);
    
    float iw = std::max(0.0f, ixmax - ixmin);
    float ih = std::max(0.0f, iymax - iymin);
    float inter = iw * ih;
    
    float area1 = std::max(0.0f, xmax1 - xmin1) * std::max(0.0f, ymax1 - ymin1);
    float area2 = std::max(0.0f, xmax2 - xmin2) * std::max(0.0f, ymax2 - ymin2);
    float union_area = area1 + area2 - inter;
    
    return (union_area > 0) ? (inter / union_area) : 0.0f;
}

std::vector<int> RKNNDetector::nmsRect(
    const std::vector<float>& boxes_xmin,
    const std::vector<float>& boxes_ymin,
    const std::vector<float>& boxes_xmax,
    const std::vector<float>& boxes_ymax,
    const std::vector<float>& scores,
    const std::vector<int>& classes
) {
    std::vector<int> idxs;
    for (size_t i = 0; i < scores.size(); ++i) {
        idxs.push_back(i);
    }
    
    // 按置信度降序排序
    std::sort(idxs.begin(), idxs.end(), [&scores](int i1, int i2) {
        return scores[i1] > scores[i2];
    });
    
    std::vector<int> kept;
    
    while (!idxs.empty()) {
        int i = idxs[0];
        kept.push_back(i);
        idxs.erase(idxs.begin());
        
        std::vector<int> rest;
        for (int j : idxs) {
            // 不同类别不进行NMS
            if (classes[j] != classes[i]) {
                rest.push_back(j);
                continue;
            }
            
            // IoU小于阈值则保留
            float iou = calcIoU(
                boxes_xmin[i], boxes_ymin[i], boxes_xmax[i], boxes_ymax[i],
                boxes_xmin[j], boxes_ymin[j], boxes_xmax[j], boxes_ymax[j]
            );
            
            if (iou <= nms_threshold_) {
                rest.push_back(j);
            }
        }
        
        idxs = rest;
    }
    
    return kept;
}

std::vector<std::vector<uint8_t>> RKNNDetector::decodeMasks(
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
) {
    std::vector<std::vector<uint8_t>> masks;
    
    if (mask_coeffs.empty() || proto_output == nullptr) {
        return masks;
    }
    
    for (size_t i = 0; i < mask_coeffs.size(); ++i) {
        try {
            const auto& coeffs = mask_coeffs[i];
            
            // 计算mask: coeffs @ proto
            std::vector<float> mask_low(proto_h * proto_w, 0.0f);
            
            for (int y = 0; y < proto_h; ++y) {
                for (int x = 0; x < proto_w; ++x) {
                    float val = 0.0f;
                    for (int c = 0; c < proto_c && c < static_cast<int>(coeffs.size()); ++c) {
                        val += coeffs[c] * proto_output[c * proto_h * proto_w + y * proto_w + x];
                    }
                    mask_low[y * proto_w + x] = sigmoid(val);
                }
            }
            
            // 简单的双线性插值resize到原图尺寸
            std::vector<uint8_t> mask_full(img_h * img_w, 0);
            
            float scale_h = static_cast<float>(proto_h) / img_h;
            float scale_w = static_cast<float>(proto_w) / img_w;
            
            for (int y = 0; y < img_h; ++y) {
                for (int x = 0; x < img_w; ++x) {
                    float src_y = y * scale_h;
                    float src_x = x * scale_w;
                    
                    int y0 = static_cast<int>(src_y);
                    int x0 = static_cast<int>(src_x);
                    int y1 = std::min(y0 + 1, proto_h - 1);
                    int x1 = std::min(x0 + 1, proto_w - 1);
                    
                    float fy = src_y - y0;
                    float fx = src_x - x0;
                    
                    float v00 = mask_low[y0 * proto_w + x0];
                    float v01 = mask_low[y0 * proto_w + x1];
                    float v10 = mask_low[y1 * proto_w + x0];
                    float v11 = mask_low[y1 * proto_w + x1];
                    
                    float val = v00 * (1 - fx) * (1 - fy) +
                               v01 * fx * (1 - fy) +
                               v10 * (1 - fx) * fy +
                               v11 * fx * fy;
                    
                    mask_full[y * img_w + x] = (val > 0.5f) ? 1 : 0;
                }
            }
            
            // 裁剪到检测框区域
            int xmin = std::max(0, static_cast<int>(boxes_xmin[i]));
            int ymin = std::max(0, static_cast<int>(boxes_ymin[i]));
            int xmax = std::min(img_w, static_cast<int>(boxes_xmax[i]));
            int ymax = std::min(img_h, static_cast<int>(boxes_ymax[i]));
            
            std::vector<uint8_t> mask_final(img_h * img_w, 0);
            if (xmax > xmin && ymax > ymin) {
                for (int y = ymin; y < ymax; ++y) {
                    for (int x = xmin; x < xmax; ++x) {
                        mask_final[y * img_w + x] = mask_full[y * img_w + x];
                    }
                }
            }
            
            masks.push_back(mask_final);
            
                } catch (const std::exception& e) {
            std::cerr << "Failed to decode mask " << i << ": " << e.what() << std::endl;
            masks.push_back(std::vector<uint8_t>(img_h * img_w, 0));
        }
    }
    
    return masks;
}

void RKNNDetector::release() {
#ifdef RKNN_AVAILABLE
    if (loaded_ && ctx_ != 0) {
        rknn_destroy(ctx_);
        ctx_ = 0;
        loaded_ = false;
        std::cout << "RKNN resources released" << std::endl;
    }
#endif
}

