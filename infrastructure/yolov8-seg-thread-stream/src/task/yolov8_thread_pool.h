

#ifndef RK3588_DEMO_Yolov8_THREAD_POOL_H
#define RK3588_DEMO_Yolov8_THREAD_POOL_H

#include "yolov8_custom.h"

#include <iostream>
#include <vector>
#include <queue>
#include <map>
#include <thread>
#include <mutex>
#include <condition_variable>

class Yolov8ThreadPool
{
private:
    std::queue<std::pair<int, cv::Mat>> tasks;                   // <id, img>用来存放任务
    std::vector<std::shared_ptr<Yolov8Custom>> Yolov8_instances; // 模型实例
    std::map<int, std::vector<Detection>> results;               // <id, objects>用来存放结果（检测框）
    std::map<int, std::vector<std::map<int, KeyPoint>>> kps_results;
    std::map<int, cv::Mat> seg_mask_results;                     // seg_maks_results
    std::map<int, cv::Mat> img_results;                          // <id, img>用来存放结果（图片）
    std::map<int, cv::Mat> img_source;                          // <id, img>用来存放原始（图片）
    std::vector<std::thread> threads;                            // 线程池
    std::mutex mtx1;
    std::mutex mtx2;
    std::condition_variable cv_task;
    bool stop;

    int modelType = 0; //0:分类 1:obb

    void worker(int id);

public:
    Yolov8ThreadPool();  // 构造函数
    ~Yolov8ThreadPool(); // 析构函数

    nn_error_e setUp(std::string &model_path, int num_threads = 12,int model_type = 0);             // 初始化
    nn_error_e setUp(std::string &model_path, int num_threads, float NMS_threshold,float box_threshold, std::string model_labels_path,int obj_class_num,int model_type = 0, int keypoint_num = 0); // 初始化
    nn_error_e submitTask(const cv::Mat &img, int id);                           // 提交任务
    nn_error_e getTargetResult(std::vector<Detection> &objects, int id);         // 获取结果（检测框）
    nn_error_e getTargetImgResult(cv::Mat &img, int id);                         // 获取结果（图片）
    nn_error_e getTargetResultNonBlock(std::vector<Detection> &objects, int id); // 获取结果（检测框）非阻塞
    nn_error_e getTargetImgResultNonBlock(cv::Mat &img, int id);// 获取结果（图片）非阻塞
    nn_error_e getTargetResultNonBlockAndSourceImg(std::vector<Detection> &objects, cv::Mat &img, int id);// 获取结果（检测框）和原始图片非阻塞

    //pose
    nn_error_e getTargetKeyPointResultNonBlockAndSourceImg(std::vector<Detection> &objects, std::vector<std::map<int, KeyPoint>> &keypoints, cv::Mat &img, int id);// 获取结果（关键点）和原始图片非阻塞, cv::Mat &img, int id);
    nn_error_e getTargetKeyPointResultNonBlock(std::vector<Detection> &objects, std::vector<std::map<int, KeyPoint>> &keypoints, int id); 

    // seg
    nn_error_e getTargetSegResultNonBlockAndSourceImg(std::vector<Detection> &objects, cv::Mat &seg_mask, cv::Mat &img, int id);
    nn_error_e getTargetSegResultNonBlock(std::vector<Detection> &objects, cv::Mat &seg_mask, int id);

    void stopAll();                                                              // 停止所有线程
};

#endif // RK3588_DEMO_Yolov8_THREAD_POOL_H
