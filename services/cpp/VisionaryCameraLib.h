#pragma once
#include <string>
#include <vector>
#include <memory>
#include "VisionaryControl.h"
#include "VisionaryDataStream.h"
#include "VisionaryTMiniData.h"

struct CameraParams
{
    int width;
    int height;
    double fx;
    double fy;
    double cx;
    double cy;
    double k1;
    double k2;
    double p1;
    double p2;
    double k3;
    double f2rc;
    std::vector<double> cam2worldMatrix;
};

struct Frame
{
    int width;
    int height;
    std::vector<float> depth_mm;
    std::vector<uint8_t> intensity_u8;
    CameraParams params;
    uint32_t frame_num;      // 帧号（用于检测旧帧复用）
    uint64_t timestamp_ms;   // 时间戳（毫秒）
};

class VisionaryCamera
{
public:
    VisionaryCamera(const std::string& ip, uint16_t control_port, bool use_single_step);
    bool connect();
    void disconnect();
    bool startAcquisition();
    bool stopAcquisition();
    bool stepAcquisition();
    bool healthy() const;
    bool getFrame(Frame& out);
private:
    std::string m_ip;
    uint16_t m_ctrl_port;
    uint16_t m_data_port;
    bool m_use_single_step;
    std::shared_ptr<visionary::VisionaryTMiniData> m_dataHandler;
    std::unique_ptr<visionary::VisionaryDataStream> m_dataStream;
    std::unique_ptr<visionary::VisionaryControl> m_control;
    bool m_connected;
};

