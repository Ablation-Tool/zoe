#pragma once

#include "trinity_core.hpp"

#include <atomic>
#include <functional>
#include <string>
#include <thread>

namespace trinity {

class HttpServer {
public:
    explicit HttpServer(State& state);
    ~HttpServer();
    void start(const std::string& host, const std::string& pair_code, std::function<void()> on_update);
    void stop();
    bool running() const { return running_; }
    std::string host() const { return host_; }

private:
    void accept_loop();
    void client(std::uintptr_t socket);
    State& state_;
    std::string host_;
    std::string pair_code_;
    std::function<void()> on_update_;
    std::uintptr_t listener_ = 0;
    std::thread accept_thread_;
    std::atomic<bool> running_{false};
    std::atomic<int> clients_{0};
};

bool private_ipv4(const std::string& host);
bool constant_time_equal(const std::string& left, const std::string& right);

}  // namespace trinity
