#include <opencv2/opencv.hpp>

#include "task/yolov8_custom.h"
#include "utils/logging.h"

#include "task/yolov8_thread_pool.h"

static int g_frame_start_id = 0; // 读取视频帧的索引
static int g_frame_end_id = 0;   // 模型处理完的索引

// 创建线程池
static Yolov8ThreadPool *yolov8_thread_pool = nullptr;
bool end = false;

void get_results(bool record = false, int width = 1280, int height = 720, int fps = 30)
{
    // 记录开始时间
    auto start_all = std::chrono::high_resolution_clock::now();
    int frame_count = 0;
    std::string fps_str;
    std::string duration_str;

    cv::VideoWriter writer;
    if(record)
    {
        writer = cv::VideoWriter("thread_pool_demo.mp4", cv::VideoWriter::fourcc('a', 'v', 'c', '1'), fps, cv::Size(width, height));
    }
    // 开始计时
    auto start_1 = std::chrono::high_resolution_clock::now();

    while (true)
    {
        // 结果
        cv::Mat img;
        auto ret = yolov8_thread_pool->getTargetImgResult(img, g_frame_end_id++);
        // 如果读取完毕，且模型处理完毕，结束
        if (end && ret != NN_SUCCESS)
        {
            break;
        }
        frame_count++;
        // all end
        auto end_all = std::chrono::high_resolution_clock::now();
        auto elapsed_all_2 = std::chrono::duration_cast<std::chrono::microseconds>(end_all - start_all).count() / 1000.f;
        // 每隔1秒打印一次
        if (elapsed_all_2 > 1000)
        {
            NN_LOG_INFO("Method2 Time:%fms, FPS:%f, Frame Count:%d", elapsed_all_2, frame_count / (elapsed_all_2 / 1000.0f), frame_count);
            fps_str = std::to_string(frame_count) + "fps";
            frame_count = 0;
            start_all = std::chrono::high_resolution_clock::now();
        }
        
        if(record)
        {
            auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_all - start_1).count() / 1000.f;
            duration_str = std::to_string(duration) + "ms";
            cv::putText(img, fps_str , cv::Point(10, 30), cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(0, 0, 255), 2);
            cv::putText(img, duration_str, cv::Point(10, 50), cv::FONT_HERSHEY_PLAIN, 1.2, cv::Scalar(0xFF, 0xFF, 0xFF), 2);
            // 写入视频帧
            writer << img;
        }

    }
    // 结束所有线程
    yolov8_thread_pool->stopAll();
    if (writer.isOpened())
    {
        writer.release();
    }
    NN_LOG_INFO("Get results end.");
}
// 读取视频帧，提交任务
void read_stream(const char *video_file)
{
    // 读取视频
    cv::VideoCapture cap(video_file);
    if (!cap.isOpened())
    {
        NN_LOG_ERROR("Failed to open video file: %s", video_file);
    }
    // 获取视频尺寸、帧率
    int width = cap.get(cv::CAP_PROP_FRAME_WIDTH);
    int height = cap.get(cv::CAP_PROP_FRAME_HEIGHT);
    int fps = cap.get(cv::CAP_PROP_FPS);
    NN_LOG_INFO("Video size: %d x %d, fps: %d", width, height, fps);

    // 画面
    cv::Mat img;

    while (true)
    {

        // 读取视频帧
        cap >> img;
        if (img.empty())
        {
            NN_LOG_INFO("Video end.");
            // 等待一下没有处理结束的湖面
            std::this_thread::sleep_for(std::chrono::milliseconds(5000));
            end = true;
            break;
        }

        // 提交任务，这里使用clone，因为不这样数据在内存中可能不连续，导致绘制错误
        yolov8_thread_pool->submitTask(img.clone(), g_frame_start_id++);
    }
    // 释放资源
    cap.release();
}

int main(int argc, char **argv)
{
    // model file path
    std::string model_file = argv[1];
    // input video
    const char *video_file = argv[2];
    // 参数：是否录像、绘制文字
    const bool record = (argc > 3) ? atoi(argv[3]) : false;
    // 参数：线程池数量
    const int num_threads = (argc > 4) ? atoi(argv[4]) : 12;


    // 实例化线程池
    yolov8_thread_pool = new Yolov8ThreadPool();
    yolov8_thread_pool->setUp(model_file, num_threads, 0.65f, 0.7f,"coco_80_labels_list.txt", 80,3);

    // 读取视频
    std::thread read_stream_thread(read_stream, video_file);
    // 启动结果线程
    std::thread result_thread(get_results,record, 1280, 720, 30);

    // 等待线程结束
    read_stream_thread.join();
    result_thread.join();

    return 0;
}