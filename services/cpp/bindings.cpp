#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include "VisionaryCameraLib.h"
#include <cstring>

namespace py = pybind11;

static py::array_t<uint8_t> to_numpy_u8(const std::vector<uint8_t>& v, int h, int w)
{
    auto result = py::array_t<uint8_t>({h, w});
    auto buf = result.request();
    uint8_t* ptr = static_cast<uint8_t*>(buf.ptr);
    std::memcpy(ptr, v.data(), v.size());
    return result;
}

static py::array_t<float> to_numpy_f32(const std::vector<float>& v)
{
    auto result = py::array_t<float>(v.size());
    auto buf = result.request();
    float* ptr = static_cast<float*>(buf.ptr);
    std::memcpy(ptr, v.data(), v.size() * sizeof(float));
    return result;
}

PYBIND11_MODULE(vc_camera_cpp, m)
{
    py::class_<CameraParams>(m, "CameraParams")
        .def(py::init<>())
        .def_readwrite("width", &CameraParams::width)
        .def_readwrite("height", &CameraParams::height)
        .def_readwrite("fx", &CameraParams::fx)
        .def_readwrite("fy", &CameraParams::fy)
        .def_readwrite("cx", &CameraParams::cx)
        .def_readwrite("cy", &CameraParams::cy)
        .def_readwrite("k1", &CameraParams::k1)
        .def_readwrite("k2", &CameraParams::k2)
        .def_readwrite("p1", &CameraParams::p1)
        .def_readwrite("p2", &CameraParams::p2)
        .def_readwrite("k3", &CameraParams::k3)
        .def_readwrite("f2rc", &CameraParams::f2rc)
        .def_readwrite("cam2worldMatrix", &CameraParams::cam2worldMatrix);

    py::class_<VisionaryCamera>(m, "VisionaryCamera")
        .def(py::init<const std::string&, uint16_t, bool>())
        .def("connect", &VisionaryCamera::connect)
        .def("disconnect", &VisionaryCamera::disconnect)
        .def("startAcquisition", &VisionaryCamera::startAcquisition)
        .def("stopAcquisition", &VisionaryCamera::stopAcquisition)
        .def("stepAcquisition", &VisionaryCamera::stepAcquisition)
        .def("healthy", &VisionaryCamera::healthy)
        .def("get_frame", [](VisionaryCamera& cam) -> py::object {
            Frame f;
            if (!cam.getFrame(f)) return py::none();
            py::dict d;
            d["intensity_image"] = to_numpy_u8(f.intensity_u8, f.height, f.width);
            d["depthmap"] = to_numpy_f32(f.depth_mm);
            d["cameraParams"] = py::cast(f.params);
            d["frame_num"] = f.frame_num;        // 暴露帧号
            d["timestamp_ms"] = f.timestamp_ms;  // 暴露时间戳
            return d;
        });
}
