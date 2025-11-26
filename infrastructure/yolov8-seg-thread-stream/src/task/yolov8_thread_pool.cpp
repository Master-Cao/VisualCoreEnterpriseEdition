
#include "yolov8_thread_pool.h"
#include "draw/cv_draw.h"
// 构造函数
Yolov8ThreadPool::Yolov8ThreadPool() { stop = false; }

// 析构函数
Yolov8ThreadPool::~Yolov8ThreadPool()
{
    // stop all threads
    stop = true;
    cv_task.notify_all();
    for (auto &thread : threads)
    {
        if (thread.joinable())
        {
            thread.join();
        }
    }
}
// 初始化：加载模型，创建线程，参数：模型路径，线程数量
nn_error_e Yolov8ThreadPool::setUp(std::string &model_path, int num_threads,int model_type)
{
    modelType = model_type;
    // 遍历线程数量，创建模型实例，放入vector
    // 这些线程加载的模型是同一个
    for (size_t i = 0; i < num_threads; ++i)
    {
        std::shared_ptr<Yolov8Custom> Yolov8 = std::make_shared<Yolov8Custom>();
        Yolov8->LoadModel(model_path.c_str());
        Yolov8_instances.push_back(Yolov8);
    }
    // 遍历线程数量，创建线程
    for (size_t i = 0; i < num_threads; ++i)
    {
        threads.emplace_back(&Yolov8ThreadPool::worker, this, i);
    }
    return NN_SUCCESS;
}

// 初始化：加载模型，创建线程，参数：模型路径，线程数量，NMS阈值，检测框置信度,类别文件路径，类别数量
nn_error_e Yolov8ThreadPool::setUp(std::string &model_path, int num_threads, float NMS_threshold,float box_threshold, std::string model_labels_path,int obj_class_num,int model_type,int keypoint_num)
{
    modelType = model_type;
    // 遍历线程数量，创建模型实例，放入vector
    // 这些线程加载的模型是同一个
    for (size_t i = 0; i < num_threads; ++i)
    {
        std::shared_ptr<Yolov8Custom> Yolov8 = std::make_shared<Yolov8Custom>();
        Yolov8->LoadModel(model_path.c_str());
        Yolov8->setStaticParams(NMS_threshold,box_threshold,model_labels_path,obj_class_num,keypoint_num);
        Yolov8_instances.push_back(Yolov8);
    }
    // 遍历线程数量，创建线程
    for (size_t i = 0; i < num_threads; ++i)
    {
        threads.emplace_back(&Yolov8ThreadPool::worker, this, i);
    }
    return NN_SUCCESS;
}

// 线程函数。参数：线程id
void Yolov8ThreadPool::worker(int id)
{
    while (!stop)
    {
        std::pair<int, cv::Mat> task;
        std::shared_ptr<Yolov8Custom> instance = Yolov8_instances[id]; // 获取模型实例
        {
            // 获取任务
            std::unique_lock<std::mutex> lock(mtx1);
            cv_task.wait(lock, [&]
                         { return !tasks.empty() || stop; });

            if (stop)
            {
                return;
            }

            task = tasks.front();
            tasks.pop();
        }
        // 运行模型
        std::vector<Detection> detections;
        // 关键点
        std::vector<std::map<int, KeyPoint>> kps;
        // mask
        cv::Mat seg_mask;

        if (modelType == 1)
        {
           instance->RunObb(task.second, detections);
        }
        else if (modelType == 2)
        {
           instance->RunPose(task.second, detections, kps);
        }
        else if (modelType == 3)
        {
           instance->RunSeg(task.second, detections, seg_mask);
        }
        else
        {
           instance->Run(task.second, detections);
        }
        
        {
            // 保存结果
            std::lock_guard<std::mutex> lock(mtx2);
            results.insert({task.first, detections});
            kps_results.insert({task.first, kps});
            img_source.insert({task.first, task.second});
            seg_mask_results.insert({task.first, seg_mask});
            if(modelType == 1)
            {
                DrawDetectionsObb(task.second, detections);
            }
            else if (modelType == 2)
            {
                DrawDetections(task.second, detections);
                DrawCocoKps(task.second, kps);
            }
            else if (modelType == 3)
            {
                DrawDetections(task.second, detections);
                DrawSeg(task.second, seg_mask);
            }
            else
            {
                DrawDetections(task.second, detections);
            }
            img_results.insert({task.first, task.second});
            cv_task.notify_one();
        }
    }
}
// 提交任务，参数：图片，id（帧号）
nn_error_e Yolov8ThreadPool::submitTask(const cv::Mat &img, int id)
{
    // 如果任务队列中的任务数量大于10，等待，避免内存占用过多
    while (tasks.size() > 10)
    {
        // sleep 1ms
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    {
        // 保存任务
        std::lock_guard<std::mutex> lock(mtx1);
        tasks.push({id, img});
    }
    cv_task.notify_one();
    return NN_SUCCESS;
}

// 获取结果，参数：检测框，id（帧号）
nn_error_e Yolov8ThreadPool::getTargetResult(std::vector<Detection> &objects, int id)
{
    // 如果没有结果，等待
    while (results.find(id) == results.end())
    {
        // sleep 1ms
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::lock_guard<std::mutex> lock(mtx2);
    objects = results[id];
    // remove from map
    results.erase(id);
    kps_results.erase(id);
    img_source.erase(id);
    img_results.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}

// 获取结果（图片），参数：图片，id（帧号）
nn_error_e Yolov8ThreadPool::getTargetImgResult(cv::Mat &img, int id)
{
    int loop_cnt = 0;
    // 如果没有结果，等待
    while (img_results.find(id) == img_results.end())
    {
        // 等待 5ms x 1000 = 5s
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        loop_cnt++;
        if (loop_cnt > 1000)
        {
            NN_LOG_ERROR("getTargetImgResult timeout");
            return NN_TIMEOUT;
        }
    }
    std::lock_guard<std::mutex> lock(mtx2);
    img = img_results[id];
    // remove from map
    img_results.erase(id);
    results.erase(id);
    kps_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}

nn_error_e Yolov8ThreadPool::getTargetResultNonBlock(std::vector<Detection> &objects, int id)
{
    if (results.find(id) == results.end())
    {
        return NN_RESULT_NOT_READY;
    }
    std::lock_guard<std::mutex> lock(mtx2);
    objects = results[id];
    // remove from map
    results.erase(id);
    kps_results.erase(id);
    img_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}

// 获取结果（图片），参数：图片，id（帧号）
nn_error_e Yolov8ThreadPool::getTargetImgResultNonBlock(cv::Mat &img, int id)
{
    int loop_cnt = 0;
    // 如果没有结果，等待
    while (img_results.find(id) == img_results.end())
    {
        NN_LOG_WARNING(">>>>>>result end<<<<<<");
        return NN_RESULT_NOT_READY;
    }
    std::lock_guard<std::mutex> lock(mtx2);
    img = img_results[id];
    // remove from map
    img_results.erase(id);
    results.erase(id);
    kps_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}

nn_error_e Yolov8ThreadPool::getTargetResultNonBlockAndSourceImg(std::vector<Detection> &objects, cv::Mat &img, int id)
{
    if (results.find(id) == results.end())
    {
        return NN_RESULT_NOT_READY;
    }
    std::lock_guard<std::mutex> lock(mtx2);
    objects = results[id];
    img = img_source[id];
    // remove from map
    results.erase(id);
    kps_results.erase(id);
    img_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}

nn_error_e Yolov8ThreadPool::getTargetKeyPointResultNonBlockAndSourceImg(std::vector<Detection> &objects, std::vector<std::map<int, KeyPoint>> &keypoints, cv::Mat &img, int id)
{
    if (results.find(id) == results.end())
    {
        return NN_RESULT_NOT_READY;
    }
    std::lock_guard<std::mutex> lock(mtx2);
    objects = results[id];
    keypoints = kps_results[id];
    img = img_source[id];
    // remove from map
    results.erase(id);
    kps_results.erase(id);
    img_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}
nn_error_e Yolov8ThreadPool::getTargetKeyPointResultNonBlock(std::vector<Detection> &objects, std::vector<std::map<int, KeyPoint>> &keypoints, int id)
{
    if (results.find(id) == results.end())
    {
        return NN_RESULT_NOT_READY;
    }
    std::lock_guard<std::mutex> lock(mtx2);
    objects = results[id];
    keypoints = kps_results[id];
    // remove from map
    results.erase(id);
    kps_results.erase(id);
    img_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}

nn_error_e Yolov8ThreadPool::getTargetSegResultNonBlockAndSourceImg(std::vector<Detection> &objects, cv::Mat &seg_mask, cv::Mat &img, int id)
{
    if (results.find(id) == results.end())
    {
        return NN_RESULT_NOT_READY;
    }
    std::lock_guard<std::mutex> lock(mtx2);
    objects = results[id];
    seg_mask = seg_mask_results[id].clone();
    img = img_source[id];
    // remove from map
    results.erase(id);
    kps_results.erase(id);
    img_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}
nn_error_e Yolov8ThreadPool::getTargetSegResultNonBlock(std::vector<Detection> &objects, cv::Mat &seg_mask, int id)
{
    if (results.find(id) == results.end())
    {
        return NN_RESULT_NOT_READY;
    }
    std::lock_guard<std::mutex> lock(mtx2);
    objects = results[id];
    seg_mask = seg_mask_results[id].clone();

    // remove from map
    results.erase(id);
    kps_results.erase(id);
    img_results.erase(id);
    img_source.erase(id);
    seg_mask_results.erase(id);

    return NN_SUCCESS;
}

// 停止所有线程
void Yolov8ThreadPool::stopAll()
{
    stop = true;
    cv_task.notify_all();
}