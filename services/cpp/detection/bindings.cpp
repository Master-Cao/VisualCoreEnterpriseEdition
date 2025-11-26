#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include "DetectorLib.h"
#include "RKNNDetector.h"
#include <cstring>

namespace py = pybind11;

// Convert numpy array to image data pointer
// Supports grayscale (H,W) and color (H,W,C) images
static std::tuple<const uint8_t*, int, int, int> numpy_to_image_data(py::array_t<uint8_t> arr) {
    py::buffer_info buf = arr.request();
    
    if (buf.ndim == 2) {
        // Grayscale image (H, W)
        return std::make_tuple(
            static_cast<const uint8_t*>(buf.ptr),
            static_cast<int>(buf.shape[0]),  // height
            static_cast<int>(buf.shape[1]),  // width
            1  // channels
        );
    } else if (buf.ndim == 3) {
        // Color image (H, W, C)
        return std::make_tuple(
            static_cast<const uint8_t*>(buf.ptr),
            static_cast<int>(buf.shape[0]),  // height
            static_cast<int>(buf.shape[1]),  // width
            static_cast<int>(buf.shape[2])   // channels
        );
    } else {
        throw std::runtime_error("Unsupported image format, need 2D (grayscale) or 3D (color) array");
    }
}

// Convert mask data to numpy array
static py::array_t<uint8_t> mask_to_numpy(const std::vector<uint8_t>& mask, int height, int width) {
    auto result = py::array_t<uint8_t>({height, width});
    auto buf = result.request();
    uint8_t* ptr = static_cast<uint8_t*>(buf.ptr);
    std::memcpy(ptr, mask.data(), mask.size());
    return result;
}

PYBIND11_MODULE(vc_detection_cpp, m) {
    m.doc() = "Visual Core Detection Module C++ Implementation";
    
    // DetectionBox class binding
    py::class_<DetectionBox>(m, "DetectionBox")
        .def(py::init<>())
        .def_readwrite("class_id", &DetectionBox::class_id, "Class ID")
        .def_readwrite("score", &DetectionBox::score, "Confidence score")
        .def_readwrite("xmin", &DetectionBox::xmin, "Bounding box left-top X")
        .def_readwrite("ymin", &DetectionBox::ymin, "Bounding box left-top Y")
        .def_readwrite("xmax", &DetectionBox::xmax, "Bounding box right-bottom X")
        .def_readwrite("ymax", &DetectionBox::ymax, "Bounding box right-bottom Y")
        .def_property("seg_mask",
            // getter: convert C++ mask to numpy array
            [](const DetectionBox& box) -> py::object {
                if (box.seg_mask.empty()) {
                    return py::none();
                }
                return mask_to_numpy(box.seg_mask, box.mask_height, box.mask_width);
            },
            // setter: convert numpy array to C++ mask
            [](DetectionBox& box, py::array_t<uint8_t> arr) {
                py::buffer_info buf = arr.request();
                if (buf.ndim != 2) {
                    throw std::runtime_error("Mask must be 2D array");
                }
                box.mask_height = buf.shape[0];
                box.mask_width = buf.shape[1];
                box.seg_mask.resize(box.mask_height * box.mask_width);
                std::memcpy(box.seg_mask.data(), buf.ptr, box.seg_mask.size());
            },
            "Segmentation mask (numpy array)"
        )
        .def("__repr__", [](const DetectionBox& box) {
            return "<DetectionBox class_id=" + std::to_string(box.class_id) +
                   " score=" + std::to_string(box.score) +
                   " box=[" + std::to_string(box.xmin) + "," + 
                   std::to_string(box.ymin) + "," +
                   std::to_string(box.xmax) + "," + 
                   std::to_string(box.ymax) + "]>";
        });
    
    // DetectionService base class binding
    py::class_<DetectionService, std::shared_ptr<DetectionService>>(m, "DetectionService")
        .def("load", &DetectionService::load, "Load model")
        .def("detect", [](DetectionService& svc, py::array_t<uint8_t> img) {
            auto [data, height, width, channels] = numpy_to_image_data(img);
            return svc.detect(data, height, width, channels);
        }, py::arg("image"), "Perform detection")
        .def("release", &DetectionService::release, "Release resources");
    
    // RKNNDetector class binding
    py::class_<RKNNDetector, DetectionService, std::shared_ptr<RKNNDetector>>(m, "RKNNDetector")
        .def(py::init<const std::string&, float, float, const std::string&>(),
            py::arg("model_path"),
            py::arg("conf_threshold") = 0.5f,
            py::arg("nms_threshold") = 0.45f,
            py::arg("target") = "rk3588",
            "RKNN YOLOv8-Seg Detector"
        )
        .def("__repr__", [](const RKNNDetector&) {
            return "<RKNNDetector>";
        });
    
    // Version information
    m.attr("__version__") = "1.0.0";
}

