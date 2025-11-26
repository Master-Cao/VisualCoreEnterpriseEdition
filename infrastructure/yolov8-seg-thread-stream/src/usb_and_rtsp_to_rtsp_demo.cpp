/*-------------------------------------------
                Includes
-------------------------------------------*/
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <opencv2/opencv.hpp>

#include "im2d.h"
#include "rga.h"
#include "RgaUtils.h"

#include "rknn_api.h"

#include "rkmedia/utils/mpp_decoder.h"
#include "rkmedia/utils/mpp_encoder.h"

#include "mk_mediakit.h"
#include "task/yolov8_custom.h"
#include "draw/cv_draw.h"
#include "task/yolov8_thread_pool.h"

#include "reconfig/ReConfig.h"

typedef struct
{
    MppDecoder *decoder;
    MppEncoder *encoder;
    mk_media media;
    mk_pusher pusher;
    const char *push_url;
    uint64_t pts;
    uint64_t dts;

    // 文件参数
    //0:分类 1:obb 2:pose
    int model_type = 0;
    // 如果model_type ==2 必须设置keypoint_num
    int keypoint_num = 0;
    // 记录一下自己的视频流地址
    const char *stream_url;
    // 记录一些配置参数
    int source_frame_rate;
    // 记录264还是265
    int source_video_type;
    // 是否启用RTSP
    int enable_rtsp;
    // RTSP的推流端口
    int push_rtsp_port;
    //zlmediakit配置文件路径
    std::string mk_file_path;
    // 推流路径第一位
    std::string push_path_first;
    // 推流路径第二位
    std::string push_path_second;
    // 是否启用推理图像，运动画面推荐开启，非运动画面推荐关闭
    int enable_push_image;
    // 设定的抽帧数量，0为不抽帧
    int step_frame_num = 0;

    // 记录一下我player不用重新初始化创建
    mk_player player;

    // 用来计算FPS
    int frame_count = 0;
    std::chrono::_V2::system_clock::time_point start_all = std::chrono::high_resolution_clock::now();
    float out_fps = 0;

    // 用来存放检测结果
    std::vector<Detection> objects;
    // pose时候存放关键点
    std::vector<std::map<int, KeyPoint>> keypoint_objects;
    // seg使用
    cv::Mat seg_mask;
    // 用来统计跳针的参数
    int step_frame_fps = 0;


} rknn_app_context_t;


static Yolov8Custom *yolov8 = nullptr;                 // 模型
static Yolov8ThreadPool *yolov8_thread_pool = nullptr; // 线程池

void release_media(mk_media *ptr)
{
    if (ptr && *ptr)
    {
        mk_media_release(*ptr);
        *ptr = NULL;
    }
}

void release_pusher(mk_pusher *ptr)
{
    if (ptr && *ptr)
    {
        mk_pusher_release(*ptr);
        *ptr = NULL;
    }
}

// 函数定义  
int padToMultipleOf16(int number) {  
    // 如果number已经是16的倍数，则直接返回  
    if (number % 16 == 0) {  
        return number;  
    }  
    // 否则，计算需要添加的额外量（即16 - (number % 16)）  
    // 这等价于找到比number大的最小16的倍数，并减去number  
    int extra = 16 - (number % 16);  
    // 返回扩充后的数  
    return number + extra;  
}

// 解码后的数据回调函数
void mpp_decoder_frame_callback(void *userdata, int width_stride, int height_stride, int width, int height, int format, int fd, void *data)
{

    // printf("mpp_decoder_frame_callback\n");
    rknn_app_context_t *ctx = (rknn_app_context_t *)userdata;

    int ret = 0;
    // 帧画面计数
    static int frame_index = 0;
    frame_index++;

    void *mpp_frame = NULL;
    int mpp_frame_fd = 0;
    void *mpp_frame_addr = NULL;
    int enc_data_size;

    // rga原始数据aiqiyi
    rga_buffer_t origin;
    rga_buffer_t src;

    // 编码器准备
    if (ctx->encoder == NULL)
    {
        MppEncoder *mpp_encoder = new MppEncoder();
        MppEncoderParams enc_params;
        memset(&enc_params, 0, sizeof(MppEncoderParams));
        enc_params.width = width;
        enc_params.height = height;
        enc_params.hor_stride = width_stride;
        enc_params.ver_stride = height_stride;
        enc_params.fmt = MPP_FMT_YUV420SP;
        enc_params.type = MPP_VIDEO_CodingAVC;
        mpp_encoder->Init(enc_params, NULL);
 
        ctx->encoder = mpp_encoder;
    }

    // 编码
    int enc_buf_size = ctx->encoder->GetFrameSize();
    char *enc_data = (char *)malloc(enc_buf_size);

    // 获取解码后的帧
    mpp_frame = ctx->encoder->GetInputFrameBuffer();
    // 获取解码后的帧fd
    mpp_frame_fd = ctx->encoder->GetInputFrameBufferFd(mpp_frame);
    // 获取解码后的帧地址
    mpp_frame_addr = ctx->encoder->GetInputFrameBufferAddr(mpp_frame);

    // 复制到另一个缓冲区，避免修改mpp解码器缓冲区
    // 使用的是RK RGA的格式转换：YUV420SP -> RGB888
    origin = wrapbuffer_fd(fd, width, height, RK_FORMAT_YCbCr_420_SP, width_stride, height_stride);
    // 这个是写入解码器的对象和颜色转换没有关系
    src = wrapbuffer_fd(mpp_frame_fd, width, height, RK_FORMAT_YCbCr_420_SP, width_stride, height_stride);
    // 创建一个等宽高的空对象
    cv::Mat origin_mat = cv::Mat::zeros(height, width, CV_8UC3);
    rga_buffer_t rgb_img = wrapbuffer_virtualaddr((void *)origin_mat.data, width, height, RK_FORMAT_RGB_888);
    imcopy(origin, rgb_img);

    static int job_cnt = 0;
    static int result_cnt = 0;

    ctx->step_frame_fps++;
    if(ctx->step_frame_fps == (ctx->step_frame_num+1))
    {
        // 提交推理任务给线程池
        yolov8_thread_pool->submitTask(origin_mat, job_cnt++);
        ctx->step_frame_fps = 0;
    }
    cv::Mat source_mat = cv::Mat::zeros(height, width, CV_8UC3);

    nn_error_e ret_code;
    if (ctx->enable_push_image==1)
    {
        // 获取推理结果和原始图片用来覆盖推送到推理部分的图片
        // 因为推理需要时间，他会用过去的推理结果放到现在的图片上
        // 图片获取后需要重新和rgb图片进行绑定，因为之间使用指针联系的，这样就不会出现问题
        ret_code = yolov8_thread_pool->getTargetSegResultNonBlockAndSourceImg(ctx->objects,ctx->seg_mask, origin_mat, result_cnt);
        // 后续的图像处理是基于推理任务重的图片进行的
        rgb_img = wrapbuffer_virtualaddr((void *)origin_mat.data, width, height, RK_FORMAT_RGB_888);
        // printf("\n=================================>>>>>>>>>>>>>>>>>> job_cnt:%d, result_cnt:%d, target:%d\n",job_cnt,result_cnt,(job_cnt-result_cnt));
    }
    else
    {   
        // 由于提交任务和结果任务不同步问题，会导致有有5-6帧画面的偏差，但是这个不影响具体的使用。
        ret_code = yolov8_thread_pool->getTargetSegResultNonBlock(ctx->objects,ctx->seg_mask, result_cnt);
    }

    /**
     * 计算FPS开始
     */
    // 结束计时
    auto end_time = std::chrono::high_resolution_clock::now();

    // 将当前时间点转换为毫秒级别的时间戳
    auto millis = std::chrono::time_point_cast<std::chrono::milliseconds>(end_time).time_since_epoch().count();

    ctx->frame_count++;
    auto elapsed_all_time = std::chrono::duration_cast<std::chrono::microseconds>(end_time - ctx->start_all).count() / 1000.f;
    // 每隔1秒打印一次
    if (elapsed_all_time > 1000)
    {
        ctx->out_fps = (ctx->frame_count / (elapsed_all_time / 1000.0f));
        // LOG
        printf("=================================>>>>>>>>>>>>>>>>>> Time:%fms, FPS:%f, Frame Count:%d\n", elapsed_all_time, ctx->out_fps, ctx->frame_count);
        ctx->frame_count = 0;
        ctx->start_all = std::chrono::high_resolution_clock::now();
    }
    // 在画面上写上fps结果标记在画面右上角
    char fps_str[64] = {0};
    /**
     * 计算FPS结束
     */
    if (ret_code == NN_SUCCESS)
    {
        result_cnt++;
    }
  
    if(ctx->model_type == 1)
    {
        DrawDetectionsObb(origin_mat, ctx->objects);
    }
    else if(ctx->model_type == 2)
    {
        DrawDetections(origin_mat, ctx->objects);
        DrawCocoKps(origin_mat, ctx->keypoint_objects);
    }
    else if(ctx->model_type == 3)
    {
        DrawDetections(origin_mat, ctx->objects);
        DrawSeg(origin_mat, ctx->seg_mask);
    }
    else
    {
        DrawDetections(origin_mat, ctx->objects);
    }

    imcopy(rgb_img, src);

    // 推流
    memset(enc_data, 0, enc_buf_size);
    enc_data_size = ctx->encoder->Encode(mpp_frame, enc_data, enc_buf_size);
    ret = mk_media_input_h264(ctx->media, enc_data, enc_data_size, millis, millis);
    if (ret != 1)
    {
        printf("mk_media_input_frame failed\n");
    }

    if (enc_data != nullptr)
    {
        free(enc_data);
    }
}

void API_CALL on_track_frame_out(void *user_data, mk_frame frame)
{
    rknn_app_context_t *ctx = (rknn_app_context_t *)user_data;
    const char *data = mk_frame_get_data(frame);
    ctx->dts = mk_frame_get_dts(frame);
    ctx->pts = mk_frame_get_pts(frame);
    size_t size = mk_frame_get_data_size(frame);
    ctx->decoder->Decode((uint8_t *)data, size, 0);
    //    mk_media_input_frame(ctx->media, frame);
}

void API_CALL on_mk_push_event_func(void *user_data, int err_code, const char *err_msg)
{
    rknn_app_context_t *ctx = (rknn_app_context_t *)user_data;
    if (err_code == 0)
    {
        // push success
        log_info("push %s success!", ctx->push_url);
        printf("push %s success!\n", ctx->push_url);
    }
    else
    {
        log_warn("push %s failed:%d %s", ctx->push_url, err_code, err_msg);
        printf("push %s failed:%d %s\n", ctx->push_url, err_code, err_msg);
        release_pusher(&(ctx->pusher));
    }
}

void API_CALL on_mk_media_source_regist_func(void *user_data, mk_media_source sender, int regist)
{
    printf("mk_media_source:%x\n", sender);
    rknn_app_context_t *ctx = (rknn_app_context_t *)user_data;
    const char *schema = mk_media_source_get_schema(sender);
    if (strncmp(schema, ctx->push_url, strlen(schema)) == 0)
    {
        // 判断是否为推流协议相关的流注册或注销事件
        printf("schema: %s\n", schema);
        release_pusher(&(ctx->pusher));
        if (regist)
        {
            ctx->pusher = mk_pusher_create_src(sender);
            mk_pusher_set_on_result(ctx->pusher, on_mk_push_event_func, ctx);
            mk_pusher_set_on_shutdown(ctx->pusher, on_mk_push_event_func, ctx);
            log_info("push started!");
            printf("push started!\n");
        }
        else
        {
            log_info("push stoped!");
            printf("push stoped!\n");
        }
        printf("push_url:%s\n", ctx->push_url);
    }
    else
    {
        printf("unknown schema:%s\n", schema);
    }
}

void API_CALL on_mk_play_event_func(void *user_data, int err_code, const char *err_msg, mk_track tracks[],
                                    int track_count)
{
    rknn_app_context_t *ctx = (rknn_app_context_t *)user_data;
    if (err_code == 0)
    {
        // success
        printf("play success!");
        int i;
        ctx->push_url = "rtmp://localhost/live/stream";
        ctx->media = mk_media_create("__defaultVhost__", ctx->push_path_first.c_str(), ctx->push_path_second.c_str(), 0, 0, 0);
        for (i = 0; i < track_count; ++i)
        {
            if (mk_track_is_video(tracks[i]))
            {
                log_info("got video track: %s", mk_track_codec_name(tracks[i]));
                // 监听track数据回调
                mk_media_init_track(ctx->media, tracks[i]);
                mk_track_add_delegate(tracks[i], on_track_frame_out, user_data);
            }
        }
        mk_media_init_complete(ctx->media);
        mk_media_set_on_regist(ctx->media, on_mk_media_source_regist_func, ctx);
        //      codec_args v_args = {0};
        //      mk_track v_track = mk_track_create(MKCodecH264, &v_args);
        //      mk_media_init_track(ctx->media, v_track);
        //      mk_media_init_complete(ctx->media);
        //      mk_track_unref(v_track);
    }
    else
    {
        printf("play failed: %d %s", err_code, err_msg);
    }
}

void API_CALL on_mk_shutdown_func(void *user_data, int err_code, const char *err_msg, mk_track tracks[], int track_count)
{
    printf("play interrupted: %d %s", err_code, err_msg);
}

int process_video_rtsp(rknn_app_context_t *ctx, const char *url)
{

    // MPP 解码器
    if (ctx->decoder == NULL)
    {
        MppDecoder *decoder = new MppDecoder();           // 创建解码器
        decoder->Init(ctx->source_video_type, ctx->source_frame_rate, ctx);          // 初始化解码器
        decoder->SetCallback(mpp_decoder_frame_callback); // 设置回调函数，用来处理解码后的数据
        ctx->decoder = decoder;                        // 将解码器赋值给上下文
    }

    // mk_config config;
    // memset(&config, 0, sizeof(mk_config));
    // config.log_mask = LOG_CONSOLE;
    // mk_env_init(&config);
    // mk_rtsp_server_start(554, 0);
    // mk_rtmp_server_start(1935, 0);

    mk_player player = mk_player_create();
    ctx->player = player;
    mk_player_set_on_result(player, on_mk_play_event_func, ctx);
    mk_player_set_on_shutdown(player, on_mk_shutdown_func, ctx);
    mk_player_play(player, url);

    printf("enter any key to exit\n");
    getchar();

    if (player)
    {
        mk_player_release(player);
    }
    return 0;
}


// 读取vieo并提交任务，此方法用线程控制启动
int process_video_file(rknn_app_context_t *ctx)
{
    // 读取视频
    cv::VideoCapture cap(ctx->stream_url);
    
    if (!cap.isOpened())
    {
        NN_LOG_ERROR("Failed to open video file: %s", ctx->stream_url);
        return 0;
    }
    // 使用前需要使用v4l2-ctl --device=/dev/video0 --list-formats-ext检查一下设备支持范围
    cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
    //set width
    cap.set(cv::CAP_PROP_FRAME_WIDTH, 1920);
    //set height
    cap.set(cv::CAP_PROP_FRAME_HEIGHT, 1080);
    // set fps
    cap.set(cv::CAP_PROP_FPS,30);

    // 获取视频尺寸、帧率
    int cap_width = cap.get(cv::CAP_PROP_FRAME_WIDTH);
    int cap_height = cap.get(cv::CAP_PROP_FRAME_HEIGHT);
    int fps = cap.get(cv::CAP_PROP_FPS);
    NN_LOG_INFO("Video size: %d x %d, fps: %d", cap_width, cap_height, fps);


    // 创建编码器，在结果处理时候需要用到
    if(ctx->encoder == NULL){
        // 初始化编码器
        MppEncoder *mpp_encoder = new MppEncoder();
        MppEncoderParams enc_params;
        memset(&enc_params, 0, sizeof(MppEncoderParams));
        enc_params.width = cap_width;
        enc_params.height = cap_height;
        enc_params.hor_stride = padToMultipleOf16(cap_width);
        enc_params.ver_stride = padToMultipleOf16(cap_height);
        // enc_params.fps_in_flex = 1;
        // enc_params.fps_out_flex = 1;
        enc_params.fmt = MPP_FMT_YUV420SP;
        enc_params.type = MPP_VIDEO_CodingAVC;
        mpp_encoder->Init(enc_params, ctx);
        ctx->encoder = mpp_encoder;
        NN_LOG_INFO("encoder init success\n");
    }

    // 初始化media
    if(ctx->media == NULL){
        ctx->push_url = "rtsp://localhost/live/stream";
        ctx->media = mk_media_create("__defaultVhost__", ctx->push_path_first.c_str(), ctx->push_path_second.c_str(), 0, 0, 0);
        codec_args v_args = {0};
        mk_track v_track = mk_track_create(MKCodecH264, &v_args);
        mk_media_init_track(ctx->media, v_track);
        mk_media_init_complete(ctx->media);
        mk_media_set_on_regist(ctx->media, on_mk_media_source_regist_func, ctx);
    }
     // 画面
    cv::Mat img;

    // mpp编码配置
    void *mpp_frame = NULL;
    int mpp_frame_fd = 0;
    void *mpp_frame_addr = NULL;
    int enc_data_size;
    
    int ret = 0;

    static int job_cnt = 0;
    static int result_cnt = 0;

    while (true)
    {
        // 读取视频帧
        cap >> img;
        if (img.empty())
        {
            NN_LOG_INFO("Video end.");
            yolov8_thread_pool->stopAll();
            break;
        }
        ctx->step_frame_fps++;
        if(ctx->step_frame_fps == (ctx->step_frame_num+1))
        {
            // 提交任务，这里使用clone，因为不这样数据在内存中可能不连续，导致绘制错误
            yolov8_thread_pool->submitTask(img.clone(), job_cnt++);
            ctx->step_frame_fps = 0;
        }

        nn_error_e ret_code;
        if (ctx->enable_push_image==1)
        {
            ret_code = yolov8_thread_pool->getTargetSegResultNonBlockAndSourceImg(ctx->objects, ctx->seg_mask, img, result_cnt);
        }
        else
        {
             // 由于提交任务和结果任务不同步问题，会导致有有5-6帧画面的偏差，但是这个不影响具体的使用。
            ret_code = yolov8_thread_pool->getTargetSegResultNonBlock(ctx->objects, ctx->seg_mask, result_cnt);
        }

        // 如果读取完毕，且模型处理完毕，结束
        if(ret_code == NN_SUCCESS){
            result_cnt++;
        }
        if(ctx->model_type == 1)
        {
            DrawDetectionsObb(img, ctx->objects);
        }
        else if(ctx->model_type == 2)
        {
            DrawDetections(img, ctx->objects);
            DrawCocoKps(img, ctx->keypoint_objects);
        }
        else if(ctx->model_type == 3)
        {
            DrawDetections(img, ctx->objects);
            DrawSeg(img, ctx->seg_mask);
        }
        else
        {
            DrawDetections(img, ctx->objects);
        }
        // 结束计时
        auto end_time = std::chrono::high_resolution_clock::now();
        // 将当前时间点转换为毫秒级别的时间戳
        auto millis = std::chrono::time_point_cast<std::chrono::milliseconds>(end_time).time_since_epoch().count();

        ctx->frame_count++;
        auto elapsed_all_time = std::chrono::duration_cast<std::chrono::microseconds>(end_time - ctx->start_all).count() / 1000.f;
        // 每隔1秒打印一次
        if (elapsed_all_time > 1000)
        {
            ctx->out_fps = (ctx->frame_count / (elapsed_all_time / 1000.0f));
            // LOG
            // printf("=================================>>>>>>>>>>>>>>>>>> Time:%fms, FPS:%f, Frame Count:%d\n", elapsed_all_time, ctx->out_fps, ctx->frame_count);
            ctx->frame_count = 0;
            ctx->start_all = std::chrono::high_resolution_clock::now();

        }
        // 在画面上写上fps结果标记在画面右上角
        char fps_str[64] = {0};
        snprintf(fps_str, sizeof(fps_str), "FPS: %.2f", ctx->out_fps, 0);
        cv::putText(img, fps_str, cv::Point(10, 30), cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(0, 0, 255), 2);
        
        
        // 获取解码后的帧
        mpp_frame = ctx->encoder->GetInputFrameBuffer();
        // 获取解码后的帧fd
        mpp_frame_fd = ctx->encoder->GetInputFrameBufferFd(mpp_frame);
        // 获取解码后的帧地址
        mpp_frame_addr = ctx->encoder->GetInputFrameBufferAddr(mpp_frame);

        rga_buffer_t src = wrapbuffer_fd(mpp_frame_fd, cap_width, cap_height, RK_FORMAT_YCbCr_420_SP,padToMultipleOf16(cap_width),padToMultipleOf16(cap_height));

        int enc_buf_size = ctx->encoder->GetFrameSize();

        char *enc_data = (char *)malloc(enc_buf_size);

        rga_buffer_t rgb_img = wrapbuffer_virtualaddr((void *)img.data, cap_width, cap_height, RK_FORMAT_BGR_888);
        // 将RGB图像复制到src中
        ret = imcopy(rgb_img, src);
        if (ret != IM_STATUS_SUCCESS) {
            NN_LOG_ERROR("%s running failed, %s\n", "imcopy(rgb_img, src)", imStrError((IM_STATUS)ret));
            goto release_buffer;
        }

        if (job_cnt == 1)
        {
            enc_data_size = ctx->encoder->GetHeader(enc_data, enc_buf_size);
        }
        // 内存初始化
        memset(enc_data, 0, enc_buf_size);
        
        enc_data_size = ctx->encoder->Encode(mpp_frame, enc_data, enc_buf_size);

        if (!enc_data)
        {
            NN_LOG_WARNING("enc_data data error\n");
            goto release_buffer;
        }
        if (!ctx->media)
        {
            NN_LOG_WARNING("ctx->media data error\n");
            goto release_buffer;
        }
        if (enc_data_size<=0)
        {
            NN_LOG_WARNING("enc_data_size size error\n");
            goto release_buffer;
        }
        ret = mk_media_input_h264(ctx->media, enc_data, enc_data_size, millis, millis);
        if (ret != 1)
        {
            printf("mk_media_input_frame failed\n");
        }
    release_buffer:
        if (enc_data != nullptr)
        {
            free(enc_data);
            enc_data = nullptr;
        }
    }
    // 释放资源
    cap.release();
    
}


int main(int argc, char **argv)
{
    int status = 0;
    int ret;

    rknn_app_context_t app_ctx;                      // 创建上下文
    memset(&app_ctx, 0, sizeof(rknn_app_context_t)); // 初始化上下文

    if (argc != 2)
    {
        printf("Usage: %s <ini_path> \n", argv[0]);
        return -1;
    }

    rr::RrConfig config;
    bool config_ret = config.ReadConfig(argv[1]);
    if (config_ret == false)
    {
        printf("ReadConfig is Error,Cfg=%s", "yunyan_config.ini");
        return -1;
    }
    // 获取参数中的模型位置
    std::string model_path = config.ReadString("YUNYAN", "ModelPath", "");
    if (model_path == "")
    {
        printf("ModelPath not found!\n");
        return -1;
    }
    app_ctx.model_type = config.ReadInt("YUNYAN", "ModelType", 0);
    // 如果model_type == 2 必须设置keypoint_num
    app_ctx.keypoint_num = config.ReadInt("YUNYAN", "KeypointNum", 0);
    // NMSIOU
    float NMS_threshold = config.ReadFloat("YUNYAN", "NMSThreshold", 0.45);
    // 置信度
    float box_threshold = config.ReadFloat("YUNYAN", "BoxThreshold", 0.4);
    // 获取参数中的模型标签
    std::string model_label_file_path = config.ReadString("YUNYAN", "ModelLabelsFilePath", "");
    if (model_label_file_path == "")
    {
        printf("ModelLabelsFilePath not found!\n");
        return -1;
    }
    int obj_class_num = config.ReadInt("YUNYAN", "ObjClassNum", 80);
    // 获取参数中的视频流地址
    std::string stream_url_str = config.ReadString("YUNYAN", "StreamUrl", "");
    if (stream_url_str == "")
    {
        printf("StreamUrl not found!\n");
        return -1;
    }
    // 将string格式转换成char *
    char *stream_url = new char[strlen(stream_url_str.c_str()) + 1];
    strcpy(stream_url, stream_url_str.c_str());
    app_ctx.stream_url = stream_url;
    // 获取参数中的视频流类型
    int video_type = config.ReadInt("YUNYAN", "VideoType", 264);
    app_ctx.source_video_type = video_type;
    // 获取识别线程数量
    int num_threads = config.ReadInt("YUNYAN", "NumThreads", 12);
    app_ctx.source_frame_rate = config.ReadInt("YUNYAN", "SourceFrameRate", 25);
    app_ctx.enable_rtsp = config.ReadInt("YUNYAN", "EnableRtsp", 0);
    app_ctx.push_rtsp_port = config.ReadInt("YUNYAN", "PushRtspPort", 554);
    std::string push_pash_first_str = config.ReadString("YUNYAN", "PushPathFirst", "yunyan-live");
    app_ctx.push_path_first = push_pash_first_str;
    std::string push_pash_second_str = config.ReadString("YUNYAN", "PushPathSecond", "test");
    app_ctx.push_path_second = push_pash_second_str;
    app_ctx.enable_push_image = config.ReadInt("YUNYAN", "EnablePushImage", 0);
    app_ctx.step_frame_num = config.ReadInt("YUNYAN", "StepFrameNum", 0);


    printf("===============配置文件读取完毕===============\n");

    yolov8_thread_pool = new Yolov8ThreadPool(); // 创建线程池
    yolov8_thread_pool->setUp(model_path, num_threads, NMS_threshold,box_threshold,model_label_file_path,obj_class_num,app_ctx.model_type,app_ctx.keypoint_num); 

    // 初始化流媒体
    mk_config mk_config;
    memset(&mk_config, 0, sizeof(mk_config));
    mk_config.log_mask = LOG_CONSOLE;
    mk_env_init(&mk_config);
    mk_rtsp_server_start(app_ctx.push_rtsp_port, 0);

    if (strncmp(stream_url, "rtsp", 4) == 0)
    {
        // 读取视频流
        process_video_rtsp(&app_ctx, stream_url);
    }
    else
    {
        // 读取视频
        process_video_file(&app_ctx);
    }

    printf("waiting finish\n");
    usleep(3 * 1000 * 1000);

    if (app_ctx.decoder != nullptr)
    {
        delete (app_ctx.decoder);
        app_ctx.decoder = nullptr;
    }
    if (app_ctx.encoder != nullptr)
    {
        delete (app_ctx.encoder);
        app_ctx.encoder = nullptr;
    }

    return 0;
}