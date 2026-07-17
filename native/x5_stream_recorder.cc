#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <camera/camera.h>
#include <camera/device_discovery.h>
#include <camera/photography_settings.h>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

std::atomic<bool> stop_requested{false};

int64_t unix_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

int64_t monotonic_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now().time_since_epoch()).count();
}

void handle_signal(int) { stop_requested = true; }

class RecordingDelegate final : public ins_camera::StreamDelegate {
public:
    RecordingDelegate(const fs::path& output_dir, const fs::path& stream0_fifo)
        : stream0_(output_dir / "x5_stream_0.h26x", std::ios::binary),
          stream1_(output_dir / "x5_stream_1.h26x", std::ios::binary),
          chunks_(output_dir / "x5_stream_chunks.csv"),
          gyro_(output_dir / "x5_gyro.csv"),
          exposure_(output_dir / "x5_exposure.csv") {
        if (!stream0_ || !stream1_ || !chunks_ || !gyro_ || !exposure_) {
            throw std::runtime_error("cannot create X5 output files");
        }
        if (!stream0_fifo.empty()) {
            stream0_fifo_.open(stream0_fifo, std::ios::binary);
            if (!stream0_fifo_) throw std::runtime_error("cannot open stream-0 FIFO");
        }
        chunks_ << "stream_index,camera_timestamp,host_unix_ns,host_monotonic_ns,bytes,offset\n";
        gyro_ << "camera_timestamp,host_unix_ns,host_monotonic_ns,ax,ay,az,gx,gy,gz\n";
        exposure_ << "camera_timestamp,host_unix_ns,host_monotonic_ns,exposure_time\n";
    }

    void OnAudioData(const uint8_t*, size_t, int64_t) override {}

    void OnVideoData(const uint8_t* data, size_t size, int64_t timestamp,
                     uint8_t, int stream_index) override {
        std::lock_guard<std::mutex> lock(mutex_);
        std::ofstream& stream = stream_index == 1 ? stream1_ : stream0_;
        int64_t& offset = stream_index == 1 ? offset1_ : offset0_;
        stream.write(reinterpret_cast<const char*>(data), static_cast<std::streamsize>(size));
        if (stream_index != 1 && stream0_fifo_) {
            stream0_fifo_.write(reinterpret_cast<const char*>(data), static_cast<std::streamsize>(size));
            stream0_fifo_.flush();
        }
        chunks_ << stream_index << ',' << timestamp << ',' << unix_ns() << ',' << monotonic_ns()
                << ',' << size << ',' << offset << '\n';
        offset += static_cast<int64_t>(size);
        ++chunks_written_;
        if (stream_index == 1) ++stream1_chunks_;
        else ++stream0_chunks_;
    }

    void OnGyroData(const std::vector<ins_camera::GyroData>& samples) override {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto wall = unix_ns();
        const auto mono = monotonic_ns();
        for (const auto& sample : samples) {
            gyro_ << sample.timestamp << ',' << wall << ',' << mono << ','
                  << sample.ax << ',' << sample.ay << ',' << sample.az << ','
                  << sample.gx << ',' << sample.gy << ',' << sample.gz << '\n';
        }
    }

    void OnExposureData(const ins_camera::ExposureData& sample) override {
        std::lock_guard<std::mutex> lock(mutex_);
        exposure_ << sample.timestamp << ',' << unix_ns() << ',' << monotonic_ns()
                  << ',' << sample.exposure_time << '\n';
    }

    int64_t chunks_written() const { return chunks_written_.load(); }
    int64_t stream0_chunks() const { return stream0_chunks_.load(); }
    int64_t stream1_chunks() const { return stream1_chunks_.load(); }

private:
    std::ofstream stream0_;
    std::ofstream stream1_;
    std::ofstream chunks_;
    std::ofstream gyro_;
    std::ofstream exposure_;
    std::ofstream stream0_fifo_;
    std::mutex mutex_;
    int64_t offset0_ = 0;
    int64_t offset1_ = 0;
    std::atomic<int64_t> chunks_written_{0};
    std::atomic<int64_t> stream0_chunks_{0};
    std::atomic<int64_t> stream1_chunks_{0};
};

int main(int argc, char** argv) {
    fs::path output_dir;
    double duration_sec = 0;
    bool stitched = false;
    fs::path stream0_fifo;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        if (argument == "--output" && i + 1 < argc) output_dir = argv[++i];
        else if (argument == "--duration" && i + 1 < argc) duration_sec = std::stod(argv[++i]);
        else if (argument == "--stitched") stitched = true;
        else if (argument == "--stream0-fifo" && i + 1 < argc) stream0_fifo = argv[++i];
        else {
            std::cerr << "usage: x5-stream-recorder --output DIR [--duration SEC] [--stitched]"
                         " [--stream0-fifo PATH]\n";
            return 2;
        }
    }
    if (output_dir.empty()) {
        std::cerr << "--output is required\n";
        return 2;
    }
    fs::create_directories(output_dir);
    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);
    ins_camera::SetLogLevel(ins_camera::LogLevel::ERR);

    ins_camera::DeviceDiscovery discovery;
    auto devices = discovery.GetAvailableDevices();
    const auto discovery_deadline = Clock::now() + std::chrono::seconds(15);
    while (devices.empty() && Clock::now() < discovery_deadline && !stop_requested) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        devices = discovery.GetAvailableDevices();
    }
    if (devices.empty()) {
        std::cerr << "no Insta360 camera found within 15 seconds\n";
        return 3;
    }
    const std::string serial = devices[0].serial_number;
    const std::string camera_name = devices[0].camera_name;
    const std::string firmware = devices[0].fw_version;
    const auto camera_type = devices[0].camera_type;
    auto camera = std::make_shared<ins_camera::Camera>(devices[0].info);
    if (!camera->Open()) {
        std::cerr << "failed to open Insta360 camera\n";
        return 4;
    }
    discovery.FreeDeviceDescriptors(devices);

    auto delegate_impl = std::make_shared<RecordingDelegate>(output_dir, stream0_fifo);
    std::shared_ptr<ins_camera::StreamDelegate> delegate = delegate_impl;
    camera->SetStreamDelegate(delegate);
    const std::time_t now = std::time(nullptr);
    std::tm local_time{};
    localtime_r(&now, &local_time);
    camera->SyncLocalTimeToCamera(now, timegm(&local_time) - now);
    if (camera_type >= ins_camera::CameraType::Insta360X4) {
        if (!camera->EnableInCameraStitching(stitched)) {
            std::cerr << "failed to configure in-camera stitching\n";
            camera->Close();
            return 5;
        }
        if (!camera->SetVideoSubMode(ins_camera::SubVideoMode::VIDEO_LIVEVIEW)) {
            std::cerr << "failed to enter X5 live-view mode\n";
            camera->Close();
            return 5;
        }
    }

    const auto resolution = ins_camera::VideoResolution::RES_3840_1920P30;
    ins_camera::RecordParams record_params;
    record_params.resolution = resolution;
    record_params.bitrate = 20 * 1024 * 1024;
    if (!camera->SetVideoCaptureParams(
            record_params, ins_camera::CameraFunctionMode::FUNCTION_MODE_LIVE_STREAM)) {
        std::cerr << "failed to set X5 preview parameters\n";
        camera->Close();
        return 5;
    }

    ins_camera::LiveStreamParam stream_params;
    stream_params.video_resolution = resolution;
    stream_params.lrv_video_resulution = ins_camera::VideoResolution::RES_1440_720P30;
    stream_params.video_bitrate = 20 * 1024 * 1024;
    stream_params.enable_audio = false;
    stream_params.using_lrv = false;
    if (!camera->StartLiveStreaming(stream_params)) {
        std::cerr << "failed to start X5 live stream\n";
        camera->Close();
        return 6;
    }

    const auto started = Clock::now();
    std::cout << "X5 recording started: " << camera_name << " serial=" << serial
              << " firmware=" << firmware << " stitched=" << stitched << std::endl;
    while (!stop_requested) {
        if (duration_sec > 0 && std::chrono::duration<double>(Clock::now() - started).count() >= duration_sec) break;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    const bool stopped = camera->StopLiveStreaming();
    camera->Close();
    std::ofstream metadata(output_dir / "x5_device.json");
    metadata << "{\n  \"camera_name\": \"" << camera_name << "\",\n"
             << "  \"serial\": \"" << serial << "\",\n"
             << "  \"firmware\": \"" << firmware << "\",\n"
             << "  \"stitched\": " << (stitched ? "true" : "false") << ",\n"
             << "  \"primary_stream_index\": 0,\n"
             << "  \"secondary_stream_optional\": true,\n"
             << "  \"stream_0_chunks\": " << delegate_impl->stream0_chunks() << ",\n"
             << "  \"stream_1_chunks\": " << delegate_impl->stream1_chunks() << ",\n"
             << "  \"chunks_written\": " << delegate_impl->chunks_written() << "\n}\n";
    // X5 CameraSDK 2.1.1 delivers its 3840x1920 dual-fisheye preview as
    // stream_index 0. A second stream is optional (for example an LRV), so an
    // empty stream_index 1 must not invalidate an otherwise complete capture.
    const bool streams_valid = delegate_impl->stream0_chunks() > 0;
    if (!stopped || !streams_valid) {
        std::cerr << "X5 stream stopped without valid primary-stream chunks\n";
        return 7;
    }
    std::cout << "X5 recording complete, chunks=" << delegate_impl->chunks_written() << std::endl;
    return 0;
}
