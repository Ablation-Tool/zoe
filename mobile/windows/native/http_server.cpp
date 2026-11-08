#include "http_server.hpp"

#include <winsock2.h>
#include <ws2tcpip.h>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstring>
#include <map>
#include <stdexcept>

namespace trinity {
namespace {

constexpr std::uintptr_t invalid_socket = static_cast<std::uintptr_t>(INVALID_SOCKET);

std::string lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char item) {
        return static_cast<char>(std::tolower(item));
    });
    return value;
}

std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t");
    if (first == std::string::npos) return "";
    const auto last = value.find_last_not_of(" \t");
    return value.substr(first, last - first + 1);
}

void send_all(SOCKET socket, const std::string& value) {
    std::size_t sent = 0;
    while (sent < value.size()) {
        const int count = send(socket, value.data() + sent, static_cast<int>(value.size() - sent), 0);
        if (count <= 0) return;
        sent += count;
    }
}

void response(SOCKET socket, int status, const Json& value) {
    const auto body = value.dump();
    const auto headers = "HTTP/1.1 " + std::to_string(status) + " OK\r\n"
        + "Content-Type: application/json; charset=utf-8\r\n"
        + "Content-Length: " + std::to_string(body.size()) + "\r\n"
        + "Cache-Control: no-store\r\n"
        + "X-Content-Type-Options: nosniff\r\n"
        + "Content-Security-Policy: default-src 'none'\r\n"
        + "Connection: close\r\n\r\n";
    send_all(socket, headers);
    send_all(socket, body);
}

bool local_authority(const std::string& value) {
    const auto colon = value.find(':');
    const auto host = lower(value.substr(0, colon));
    return host == "127.0.0.1" || host == "localhost";
}

std::string origin_host(const std::string& value) {
    const auto scheme = value.find("://");
    if (scheme == std::string::npos || lower(value.substr(0, scheme)) != "http") return "";
    auto rest = value.substr(scheme + 3);
    const auto slash = rest.find('/');
    if (slash != std::string::npos) rest.resize(slash);
    if (rest.find('@') != std::string::npos) return "";
    const auto colon = rest.find(':');
    return lower(rest.substr(0, colon));
}

struct Request {
    std::string method;
    std::string path;
    std::map<std::string, std::string> headers;
    std::string body;
};

Request read_request(SOCKET socket) {
    std::string data;
    char buffer[4096];
    std::size_t header_end = std::string::npos;
    while (header_end == std::string::npos) {
        const int count = recv(socket, buffer, sizeof(buffer), 0);
        if (count <= 0) throw std::runtime_error("incomplete HTTP request");
        data.append(buffer, count);
        if (data.size() > 20480) throw std::runtime_error("HTTP headers exceed bounds");
        header_end = data.find("\r\n\r\n");
    }
    const auto headers = data.substr(0, header_end);
    data = data.substr(header_end + 4);
    Request request;
    std::size_t position = 0;
    bool first = true;
    while (position < headers.size()) {
        auto end = headers.find("\r\n", position);
        if (end == std::string::npos) end = headers.size();
        const auto line = headers.substr(position, end - position);
        position = end + 2;
        if (first) {
            first = false;
            const auto method_end = line.find(' ');
            const auto path_end = line.find(' ', method_end + 1);
            if (method_end == std::string::npos || path_end == std::string::npos
                || line.substr(path_end + 1) != "HTTP/1.1") throw std::runtime_error("invalid HTTP request line");
            request.method = line.substr(0, method_end);
            request.path = line.substr(method_end + 1, path_end - method_end - 1);
            if (request.path.size() > 64) throw std::runtime_error("HTTP path exceeds bounds");
        } else {
            const auto colon = line.find(':');
            if (colon == std::string::npos) throw std::runtime_error("invalid HTTP header");
            request.headers[lower(trim(line.substr(0, colon)))] = trim(line.substr(colon + 1));
        }
    }
    if (request.headers.count("transfer-encoding")) throw std::runtime_error("chunked requests are not supported");
    std::size_t length = 0;
    if (request.headers.count("content-length")) {
        const auto text = request.headers["content-length"];
        if (text.empty() || !std::all_of(text.begin(), text.end(), [](unsigned char c) { return std::isdigit(c); })) {
            throw std::runtime_error("invalid Content-Length");
        }
        length = static_cast<std::size_t>(std::stoull(text));
    }
    if (length > 16384) throw std::runtime_error("JSON body exceeds 16384 bytes");
    if (data.size() > length) throw std::runtime_error("pipelined requests are not supported");
    while (data.size() < length) {
        const int count = recv(socket, buffer, std::min(sizeof(buffer), length - data.size()), 0);
        if (count <= 0) throw std::runtime_error("incomplete JSON body");
        data.append(buffer, count);
    }
    request.body = std::move(data);
    return request;
}

}  // namespace

bool constant_time_equal(const std::string& left, const std::string& right) {
    std::size_t difference = left.size() ^ right.size();
    const auto size = std::max(left.size(), right.size());
    for (std::size_t index = 0; index < size; ++index) {
        const unsigned char a = index < left.size() ? static_cast<unsigned char>(left[index]) : 0;
        const unsigned char b = index < right.size() ? static_cast<unsigned char>(right[index]) : 0;
        difference |= a ^ b;
    }
    return difference == 0;
}

bool private_ipv4(const std::string& host) {
    in_addr address{};
    if (InetPtonA(AF_INET, host.c_str(), &address) != 1) return false;
    const auto bytes = reinterpret_cast<const unsigned char*>(&address);
    return bytes[0] == 10 || (bytes[0] == 192 && bytes[1] == 168)
        || (bytes[0] == 172 && bytes[1] >= 16 && bytes[1] <= 31)
        || (bytes[0] == 169 && bytes[1] == 254);
}

HttpServer::HttpServer(State& state) : state_(state) {}
HttpServer::~HttpServer() { stop(); }

void HttpServer::start(const std::string& host, const std::string& pair_code, std::function<void()> on_update) {
    if (running_) return;
    if (host != "127.0.0.1" && (!private_ipv4(host) || pair_code.size() < 16)) {
        throw std::runtime_error("LAN mode requires a private IPv4 address and a pairing code of at least 16 characters");
    }
    host_ = host;
    pair_code_ = pair_code;
    on_update_ = std::move(on_update);
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) throw std::runtime_error("WSAStartup failed");
    addrinfo hints{};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;
    addrinfo* addresses = nullptr;
    if (getaddrinfo(host_.c_str(), "8767", &hints, &addresses) != 0) {
        WSACleanup();
        throw std::runtime_error("could not resolve the local listen address");
    }
    const auto socket = ::socket(addresses->ai_family, addresses->ai_socktype, addresses->ai_protocol);
    if (socket == invalid_socket) {
        freeaddrinfo(addresses);
        WSACleanup();
        throw std::runtime_error("could not create the local listener");
    }
    int enabled = 1;
    setsockopt(static_cast<SOCKET>(socket), SOL_SOCKET, SO_EXCLUSIVEADDRUSE,
               reinterpret_cast<const char*>(&enabled), sizeof(enabled));
    if (bind(static_cast<SOCKET>(socket), addresses->ai_addr, static_cast<int>(addresses->ai_addrlen)) != 0
        || listen(static_cast<SOCKET>(socket), 8) != 0) {
        closesocket(static_cast<SOCKET>(socket));
        freeaddrinfo(addresses);
        WSACleanup();
        throw std::runtime_error("could not bind port 8767");
    }
    freeaddrinfo(addresses);
    listener_ = socket;
    running_ = true;
    accept_thread_ = std::thread(&HttpServer::accept_loop, this);
}

void HttpServer::stop() {
    if (!running_) return;
    running_ = false;
    if (listener_) closesocket(static_cast<SOCKET>(listener_));
    listener_ = 0;
    if (accept_thread_.joinable()) accept_thread_.join();
    for (int attempt = 0; attempt < 50 && clients_ > 0; ++attempt) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    WSACleanup();
}

void HttpServer::accept_loop() {
    while (running_) {
        const auto socket = accept(static_cast<SOCKET>(listener_), nullptr, nullptr);
        if (socket == invalid_socket) break;
        if (clients_ >= 4) {
            response(static_cast<SOCKET>(socket), 503, Json::Object{{"error", "local client limit reached"}});
            closesocket(static_cast<SOCKET>(socket));
            continue;
        }
        ++clients_;
        std::thread(&HttpServer::client, this, static_cast<std::uintptr_t>(socket)).detach();
    }
}

void HttpServer::client(std::uintptr_t raw_socket) {
    const auto socket = static_cast<SOCKET>(raw_socket);
    DWORD timeout = 4000;
    setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    try {
        const auto request = read_request(socket);
        if (request.method == "GET" && request.path == "/api/health") {
            response(socket, 200, Json::Object{{"protocol", 1}, {"name", "Zoe Trinity"}, {"scope", "native-windows-local"}});
            closesocket(socket);
            --clients_;
            return;
        }
        if (request.method != "GET" && request.method != "POST") {
            response(socket, 405, Json::Object{{"error", "method not allowed"}});
            closesocket(socket);
            --clients_;
            return;
        }
        const bool mutation = request.method == "POST";
        if (host_ == "127.0.0.1" && !local_authority(request.headers.at("host"))) {
            response(socket, 403, Json::Object{{"error", "loopback Host header required"}});
            closesocket(socket);
            --clients_;
            return;
        }
        if (request.headers.count("origin")) {
            const auto origin = origin_host(request.headers.at("origin"));
            if (origin != "127.0.0.1" && origin != "localhost" && origin != lower(host_)) {
                response(socket, 403, Json::Object{{"error", "untrusted Origin"}});
                closesocket(socket);
                --clients_;
                return;
            }
        }
        if (!pair_code_.empty()) {
            const auto supplied = request.headers.count("x-zoe-pair") ? request.headers.at("x-zoe-pair") : "";
            if (!constant_time_equal(supplied, pair_code_)) {
                response(socket, 403, Json::Object{{"error", "valid pairing code required"}});
                closesocket(socket);
                --clients_;
                return;
            }
        }
        if (mutation && (!request.headers.count("x-zoe-protocol") || request.headers.at("x-zoe-protocol") != "1")) {
            response(socket, 403, Json::Object{{"error", "X-Zoe-Protocol: 1 required"}});
            closesocket(socket);
            --clients_;
            return;
        }
        if (request.method == "GET" && request.path == "/api/state") {
            response(socket, 200, state_.snapshot());
        } else if (request.method == "POST" && (request.path == "/api/measure" || request.path == "/api/reset")) {
            if (lower(request.headers.at("content-type")).find("application/json") != 0) {
                response(socket, 415, Json::Object{{"error", "application/json required"}});
            } else {
                const auto body = Json::parse(request.body);
                const auto source = body.at("source").string();
                const auto result = request.path == "/api/reset"
                    ? state_.reset(source)
                    : state_.measure(source, probabilities_from_json(body.at("probabilities")), body.at("tau").number());
                response(socket, 200, result);
                if (on_update_) on_update_();
            }
        } else {
            response(socket, 404, Json::Object{{"error", "not found"}});
        }
    } catch (const std::exception& error) {
        response(socket, 400, Json::Object{{"error", error.what()}});
    }
    closesocket(socket);
    --clients_;
}

}  // namespace trinity
