#include "VisionaryCameraLib.h"
#include <algorithm>

using namespace visionary;

VisionaryCamera::VisionaryCamera(const std::string& ip, uint16_t control_port, bool use_single_step)
    : m_ip(ip), m_ctrl_port(control_port), m_data_port(2114), m_use_single_step(use_single_step), m_connected(false)
{
}

bool VisionaryCamera::connect()
{
    m_dataHandler = std::make_shared<VisionaryTMiniData>();
    m_dataStream = std::unique_ptr<VisionaryDataStream>(new VisionaryDataStream(m_dataHandler));
    m_control = std::unique_ptr<VisionaryControl>(new VisionaryControl());
    if (!m_dataStream->open(m_ip, htons(m_data_port))) return false;
    if (!m_control->open(VisionaryControl::ProtocolType::COLA_2, m_ip, 5000)) return false;
    if (!m_control->login(IAuthentication::UserLevel::AUTHORIZED_CLIENT, std::string("CLIENT"))) return false;
    if (m_use_single_step) m_control->stopAcquisition(); else m_control->startAcquisition();
    m_connected = true;
    return true;
}

void VisionaryCamera::disconnect()
{
    if (m_control) m_control->stopAcquisition();
    if (m_control) m_control->logout();
    if (m_control) m_control->close();
    if (m_dataStream) m_dataStream->close();
    m_connected = false;
}

bool VisionaryCamera::startAcquisition()
{
    if (!m_control) return false;
    return m_control->startAcquisition();
}

bool VisionaryCamera::stopAcquisition()
{
    if (!m_control) return false;
    return m_control->stopAcquisition();
}

bool VisionaryCamera::stepAcquisition()
{
    if (!m_control) return false;
    return m_control->stepAcquisition();
}

bool VisionaryCamera::healthy() const
{
    if (!m_connected) return false;
    if (!m_dataStream) return false;
    return m_dataStream->isConnected();
}

static inline uint8_t scale_intensity(uint16_t v)
{
    float x = v * 0.05f + 1.0f;
    if (x < 0.0f) x = 0.0f;
    if (x > 255.0f) x = 255.0f;
    return static_cast<uint8_t>(x);
}

bool VisionaryCamera::getFrame(Frame& out)
{
    if (!m_connected || !m_dataStream) return false;
    if (m_use_single_step) m_control->stepAcquisition();
    bool ok = m_dataStream->getNextFrame();
    if (!ok) return false;
    const auto& params = m_dataHandler->getCameraParameters();
    const auto& intensity16 = m_dataHandler->getIntensityMap();
    const auto& distance16 = m_dataHandler->getDistanceMap();
    out.width = params.width;
    out.height = params.height;
    out.intensity_u8.resize(intensity16.size());
    for (size_t i = 0; i < intensity16.size(); ++i) out.intensity_u8[i] = scale_intensity(intensity16[i]);
    out.depth_mm.resize(distance16.size());
    for (size_t i = 0; i < distance16.size(); ++i) out.depth_mm[i] = distance16[i] * VisionaryTMiniData::DISTANCE_MAP_UNIT;
    out.params.width = params.width;
    out.params.height = params.height;
    out.params.fx = params.fx;
    out.params.fy = params.fy;
    out.params.cx = params.cx;
    out.params.cy = params.cy;
    out.params.k1 = params.k1;
    out.params.k2 = params.k2;
    out.params.p1 = params.p1;
    out.params.p2 = params.p2;
    out.params.k3 = params.k3;
    out.params.f2rc = params.f2rc;
    out.params.cam2worldMatrix.assign(params.cam2worldMatrix, params.cam2worldMatrix + 16);
    
    // 获取帧号和时间戳（用于检测旧帧复用问题）
    out.frame_num = m_dataHandler->getFrameNum();
    out.timestamp_ms = m_dataHandler->getTimestampMS();
    
    return true;
}

