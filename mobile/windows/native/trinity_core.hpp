#pragma once

#include "json.hpp"

#include <cstdio>
#include <filesystem>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace trinity {

inline constexpr int scale = 32768;
inline constexpr int max_probabilities = 64;
inline constexpr int max_events = 24;
inline constexpr const char* creator = "Nicholas Michael Kloster alone, March 6, 2026";
inline constexpr const char* equation = "A_tau(S) = sum 1[P(a | h_T(S)) > tau]";

struct Counts {
    int accessible = 0;
    int complement = 0;
    int vocabulary_size = 0;
    double normalized = 0;
};

struct Tiny {
    std::vector<int> probabilities;
    int tau = 0;
    Counts counts;
    std::string request;
    std::string response;
};

struct Measurement {
    std::vector<double> probabilities;
    double tau = 0;
    Counts zoe;
    Tiny tiny;
    bool quantization_changed = false;
};

struct Event {
    int ordinal = 0;
    std::string source;
    Measurement measurement;
};

Measurement measure(const std::vector<double>& probabilities, double tau);
Json measurement_json(const Measurement& value);
Measurement measurement_from_json(const Json& value);
std::vector<double> probabilities_from_json(const Json& value);
std::string event_summary(const Event& event);

class Journal {
public:
    explicit Journal(std::filesystem::path path);
    ~Journal();
    void append(const std::string& kind, const std::string& source,
                const Measurement& active, const std::optional<Event>& event);
    std::size_t size() const { return records_; }
    int revision() const { return records_; }
    const Json& last() const { return last_; }
    const std::vector<Json>& history() const { return history_; }

private:
    std::filesystem::path path_;
    std::FILE* file_ = nullptr;
    std::size_t records_ = 0;
    std::string previous_ = std::string(64, '0');
    Json last_;
    std::vector<Json> history_;
};

class State {
public:
    explicit State(Journal* journal = nullptr);
    Json snapshot() const;
    Json measure(const std::string& source, const std::vector<double>& probabilities, double tau);
    Json reset(const std::string& source);
    int revision() const;

private:
    Json snapshot_unlocked() const;
    mutable std::mutex mutex_;
    Journal* journal_;
    int revision_ = 0;
    Measurement active_;
    std::vector<Event> events_;
};

void validate_source(const std::string& source);

}  // namespace trinity
