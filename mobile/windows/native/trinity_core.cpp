#include "trinity_core.hpp"
#include "sha256.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <numeric>
#include <stdexcept>

#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

namespace trinity {
namespace {

struct Decimal {
    std::string digits;
    int scale = 0;
};

Decimal decimal(double value) {
    std::string text = number(value);
    int exponent = 0;
    const auto marker = text.find_first_of("eE");
    if (marker != std::string::npos) {
        exponent = std::stoi(text.substr(marker + 1));
        text.resize(marker);
    }
    if (!text.empty() && text.front() == '-') text.erase(text.begin());
    const auto point = text.find('.');
    int fraction = 0;
    if (point != std::string::npos) {
        fraction = static_cast<int>(text.size() - point - 1);
        text.erase(point, 1);
    }
    const auto first = text.find_first_not_of('0');
    if (first == std::string::npos) return {"0", 0};
    text = text.substr(first);
    return {text, fraction - exponent};
}

std::string multiply(std::string digits, int factor) {
    int carry = 0;
    for (int index = static_cast<int>(digits.size()) - 1; index >= 0; --index) {
        const int value = (digits[index] - '0') * factor + carry;
        digits[index] = static_cast<char>('0' + value % 10);
        carry = value / 10;
    }
    while (carry) {
        digits.insert(digits.begin(), static_cast<char>('0' + carry % 10));
        carry /= 10;
    }
    return digits;
}

std::string left_pad(std::string value, std::size_t size) {
    if (value.size() < size) value.insert(value.begin(), size - value.size(), '0');
    return value;
}

std::pair<int, std::string> split(const Decimal& value) {
    auto digits = multiply(value.digits, scale);
    if (value.scale <= 0) {
        digits.append(static_cast<std::size_t>(-value.scale), '0');
        return {std::stoi(digits), "0"};
    }
    const auto precision = static_cast<std::size_t>(value.scale);
    if (digits.size() <= precision) {
        return {0, left_pad(std::move(digits), precision)};
    }
    const auto split_at = digits.size() - precision;
    return {std::stoi(digits.substr(0, split_at)), digits.substr(split_at)};
}

int compare_fraction(const std::pair<int, std::string>& left, int left_scale,
                     const std::pair<int, std::string>& right, int right_scale) {
    if (left_scale <= 0 && right_scale <= 0) return 0;
    auto a = left.second;
    auto b = right.second;
    const auto width = std::max(left_scale > 0 ? left_scale : 1, right_scale > 0 ? right_scale : 1);
    a = left_pad(std::move(a), static_cast<std::size_t>(left_scale > 0 ? left_scale : 1));
    b = left_pad(std::move(b), static_cast<std::size_t>(right_scale > 0 ? right_scale : 1));
    const auto target = static_cast<std::size_t>(width);
    a.append(target - a.size(), '0');
    b.append(target - b.size(), '0');
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
}

std::string hex(const std::vector<unsigned>& bytes) {
    static const char* digits = "0123456789ABCDEF";
    std::string result;
    result.reserve(bytes.size() * 2);
    for (const auto byte : bytes) {
        result.push_back(digits[(byte >> 4) & 15]);
        result.push_back(digits[byte & 15]);
    }
    return result;
}

void append_short(std::vector<unsigned>& bytes, int value) {
    bytes.push_back(static_cast<unsigned>((value >> 8) & 255));
    bytes.push_back(static_cast<unsigned>(value & 255));
}

Json counts_json(const Counts& counts) {
    return Json::Object{
        {"accessible", counts.accessible},
        {"complement", counts.complement},
        {"vocabularySize", counts.vocabulary_size},
        {"normalized", counts.normalized},
    };
}

void validate_counts(const Json& value, const Counts& counts) {
    if (value.at("accessible").integer() != counts.accessible
        || value.at("complement").integer() != counts.complement
        || value.at("vocabularySize").integer() != counts.vocabulary_size
        || std::abs(value.at("normalized").number() - counts.normalized) > 1e-15) {
        throw std::runtime_error("stored measurement counts do not match");
    }
}

}  // namespace

void validate_source(const std::string& source) {
    if (source != "android" && source != "apple" && source != "laptop") {
        throw std::runtime_error("source must be android, apple, or laptop");
    }
}

Measurement measure(const std::vector<double>& probabilities, double tau) {
    if (probabilities.empty() || probabilities.size() > max_probabilities) {
        throw std::runtime_error("distribution must contain 1 to 64 probabilities");
    }
    if (!std::isfinite(tau) || tau < 0 || tau > 1) throw std::runtime_error("tau must be between zero and one");
    double total = 0;
    std::vector<Decimal> decimals;
    decimals.reserve(probabilities.size());
    for (const double probability : probabilities) {
        if (!std::isfinite(probability) || probability < 0 || probability > 1) {
            throw std::runtime_error("probabilities must be finite values between zero and one");
        }
        total += probability;
        decimals.push_back(decimal(probability));
    }
    if (std::abs(total - 1.0) > 1e-8) throw std::runtime_error("probabilities must sum to one within 1e-8");

    std::vector<std::pair<int, std::string>> split_values;
    std::vector<int> units;
    split_values.reserve(decimals.size());
    units.reserve(decimals.size());
    int sum = 0;
    for (const auto& value : decimals) {
        auto parts = split(value);
        sum += parts.first;
        units.push_back(parts.first);
        split_values.push_back(std::move(parts));
    }
    const int remaining = scale - sum;
    if (remaining < 0 || remaining > static_cast<int>(units.size())) throw std::runtime_error("invalid Q0.15 allocation");
    std::vector<int> order(units.size());
    std::iota(order.begin(), order.end(), 0);
    std::stable_sort(order.begin(), order.end(), [&](int left, int right) {
        return compare_fraction(split_values[left], decimals[left].scale,
                                split_values[right], decimals[right].scale) > 0;
    });
    for (int index = 0; index < remaining; ++index) ++units[order[index]];

    auto threshold = split(decimal(tau));
    int tiny_tau = threshold.first;
    const auto threshold_scale = decimal(tau).scale;
    if (threshold_scale > 0) {
        std::string half = "5";
        half.append(static_cast<std::size_t>(threshold_scale - 1), '0');
        const auto comparison = compare_fraction(threshold, threshold_scale, {0, half}, threshold_scale);
        if (comparison > 0 || (comparison == 0 && (tiny_tau & 1))) ++tiny_tau;
    }

    Measurement result;
    result.probabilities = probabilities;
    result.tau = tau;
    result.zoe.vocabulary_size = static_cast<int>(probabilities.size());
    for (const double probability : probabilities) if (probability > tau) ++result.zoe.accessible;
    result.zoe.complement = result.zoe.vocabulary_size - result.zoe.accessible;
    result.zoe.normalized = static_cast<double>(result.zoe.accessible) / result.zoe.vocabulary_size;
    result.tiny.probabilities = units;
    result.tiny.tau = tiny_tau;
    result.tiny.counts.vocabulary_size = static_cast<int>(units.size());
    for (const int unit : units) if (unit > tiny_tau) ++result.tiny.counts.accessible;
    result.tiny.counts.complement = result.tiny.counts.vocabulary_size - result.tiny.counts.accessible;
    result.tiny.counts.normalized = static_cast<double>(result.tiny.counts.accessible) / units.size();
    std::vector<unsigned> request = {0x80, 0x02, 0, 0, static_cast<unsigned>(2 + units.size() * 2)};
    append_short(request, tiny_tau);
    for (const int unit : units) append_short(request, unit);
    result.tiny.request = hex(request);
    std::vector<unsigned> response;
    append_short(response, result.tiny.counts.accessible);
    append_short(response, result.tiny.counts.complement);
    append_short(response, result.tiny.counts.vocabulary_size);
    append_short(response, tiny_tau);
    response.push_back(0x90);
    response.push_back(0x00);
    result.tiny.response = hex(response);
    result.quantization_changed = result.zoe.accessible != result.tiny.counts.accessible
        || tiny_tau != static_cast<int>(tau * scale);
    return result;
}

Json measurement_json(const Measurement& value) {
    Json::Array probabilities;
    for (const double probability : value.probabilities) probabilities.emplace_back(probability);
    Json::Array units;
    for (const int unit : value.tiny.probabilities) units.emplace_back(unit);
    return Json::Object{
        {"probabilities", probabilities},
        {"tau", value.tau},
        {"zoe", counts_json(value.zoe)},
        {"tiny", Json::Object{
            {"probabilities", units},
            {"tau", value.tiny.tau},
            {"accessible", value.tiny.counts.accessible},
            {"complement", value.tiny.counts.complement},
            {"vocabularySize", value.tiny.counts.vocabulary_size},
            {"normalized", value.tiny.counts.normalized},
            {"request", value.tiny.request},
            {"response", value.tiny.response},
        }},
        {"quantizationChanged", value.quantization_changed},
    };
}

std::vector<double> probabilities_from_json(const Json& value) {
    const auto& items = value.array();
    if (items.empty() || items.size() > max_probabilities) throw std::runtime_error("invalid distribution size");
    std::vector<double> probabilities;
    probabilities.reserve(items.size());
    for (const auto& item : items) probabilities.push_back(item.number());
    return probabilities;
}

Measurement measurement_from_json(const Json& value) {
    auto result = measure(probabilities_from_json(value.at("probabilities")), value.at("tau").number());
    validate_counts(value.at("zoe"), result.zoe);
    const auto& tiny = value.at("tiny");
    if (probabilities_from_json(tiny.at("probabilities")).size() != result.tiny.probabilities.size()) {
        throw std::runtime_error("stored Tiny vector size differs");
    }
    const auto& units = tiny.at("probabilities").array();
    for (std::size_t index = 0; index < units.size(); ++index) {
        if (units[index].integer() != result.tiny.probabilities[index]) throw std::runtime_error("stored Tiny units differ");
    }
    if (tiny.at("tau").integer() != result.tiny.tau
        || tiny.at("request").string() != result.tiny.request
        || tiny.at("response").string() != result.tiny.response
        || value.at("quantizationChanged").boolean() != result.quantization_changed) {
        throw std::runtime_error("stored Tiny witness differs");
    }
    validate_counts(tiny, result.tiny.counts);
    return result;
}

std::string event_summary(const Event& event) {
    return "#" + std::to_string(event.ordinal) + " · " + event.source
        + " · Mobile " + std::to_string(event.measurement.zoe.accessible) + "/"
        + std::to_string(event.measurement.zoe.vocabulary_size)
        + " · Tiny " + std::to_string(event.measurement.tiny.counts.accessible) + "/"
        + std::to_string(event.measurement.tiny.counts.vocabulary_size);
}

Journal::Journal(std::filesystem::path path) : path_(std::move(path)) {
    if (std::filesystem::is_symlink(path_)) throw std::runtime_error("memory journal must not be a symbolic link");
    if (!std::filesystem::is_directory(path_.parent_path())) throw std::runtime_error("memory journal parent must exist");
    const bool existed = std::filesystem::exists(path_);
    if (existed && (!std::filesystem::is_regular_file(path_) || std::filesystem::file_size(path_) > 64 * 1024 * 1024)) {
        throw std::runtime_error("invalid or oversized memory journal");
    }
    file_ = std::fopen(path_.string().c_str(), "a+b");
    if (!file_) throw std::runtime_error("could not open memory journal");
    try {
#ifndef _WIN32
    if (!existed) std::filesystem::permissions(path_, std::filesystem::perms::owner_all, std::filesystem::perm_options::replace);
#endif
    std::ifstream input(path_);
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty()) continue;
        if (++records_ > 10'000 || line.size() > 65'536) throw std::runtime_error("memory journal bounds exceeded");
        auto record = Json::parse(line);
        auto body = record.object();
        const auto supplied_hash = body.at("hash").string();
        body.erase("hash");
        const Json canonical_body(body);
        if (supplied_hash != sha256(canonical_body.dump())) throw std::runtime_error("memory hash mismatch");
        if (canonical_body.at("sequence").integer() != static_cast<int>(records_)
            || canonical_body.at("revision").integer() != static_cast<int>(records_)
            || canonical_body.at("previous").string() != previous_) {
            throw std::runtime_error("memory sequence is edited or reordered");
        }
        const auto kind = canonical_body.at("kind").string();
        if (kind != "measure" && kind != "reset") throw std::runtime_error("unknown memory event kind");
        previous_ = supplied_hash;
        last_ = record;
        history_.push_back(record);
    }
    } catch (...) {
        std::fclose(file_);
        file_ = nullptr;
        throw;
    }
}

void Journal::append(const std::string& kind, const std::string& source,
                     const Measurement& active, const std::optional<Event>& event) {
    if (records_ >= 10'000 || std::filesystem::file_size(path_) >= 64 * 1024 * 1024) {
        throw std::runtime_error("memory journal is full");
    }
    const int sequence = static_cast<int>(records_) + 1;
    Json::Object body{
        {"sequence", sequence}, {"revision", sequence}, {"previous", previous_},
        {"kind", kind}, {"source", source}, {"active", measurement_json(active)}, {"event", nullptr},
    };
    if (event) {
        auto event_object = measurement_json(event->measurement).object();
        event_object["ordinal"] = event->ordinal;
        event_object["source"] = event->source;
        body["event"] = event_object;
    }
    const Json canonical_body(body);
    auto record = body;
    record["hash"] = sha256(canonical_body.dump());
    const auto payload = Json(record).dump() + "\n";
    if (payload.size() > 65'536 || std::filesystem::file_size(path_) + payload.size() > 64 * 1024 * 1024) {
        throw std::runtime_error("memory event exceeds journal bounds");
    }
    if (std::fwrite(payload.data(), 1, payload.size(), file_) != payload.size() || std::fflush(file_) != 0) {
        throw std::runtime_error("could not append memory journal");
    }
#ifdef _WIN32
    if (_commit(_fileno(file_)) != 0) throw std::runtime_error("could not commit memory journal");
#else
    if (fsync(fileno(file_)) != 0) throw std::runtime_error("could not commit memory journal");
#endif
    previous_ = record["hash"].string();
    last_ = Json(record);
    history_.push_back(last_);
    ++records_;
}

Journal::~Journal() {
    if (file_) std::fclose(file_);
}

State::State(Journal* journal) : journal_(journal), active_(trinity::measure({0.70, 0.20, 0.08, 0.02}, 0.05)) {
    if (!journal_) return;
    for (const auto& record : journal_->history()) {
        const auto& active = record.at("active");
        active_ = measurement_from_json(active);
        revision_ = record.at("revision").integer();
        const auto kind = record.at("kind").string();
        validate_source(record.at("source").string());
        if (kind == "reset") {
            events_.clear();
            continue;
        }
        Event event;
        event.ordinal = record.at("event").at("ordinal").integer();
        event.source = record.at("event").at("source").string();
        event.measurement = measurement_from_json(record.at("event"));
        if (event.ordinal != revision_ || event.source != record.at("source").string()) {
            throw std::runtime_error("memory event metadata differs");
        }
        events_.push_back(std::move(event));
        if (events_.size() > max_events) events_.erase(events_.begin());
    }
}

Json State::snapshot_unlocked() const {
    Json::Array events;
    for (const auto& event : events_) {
        auto item = measurement_json(event.measurement).object();
        item["ordinal"] = event.ordinal;
        item["source"] = event.source;
        events.emplace_back(item);
    }
    return Json::Object{
        {"protocol", 1}, {"name", "Zoe Trinity"}, {"revision", revision_},
        {"active", measurement_json(active_)}, {"events", events},
        {"creator", creator}, {"equation", equation},
        {"memory", Json::Object{
            {"enabled", journal_ != nullptr},
            {"records", static_cast<int>(journal_ ? journal_->size() : 0)},
            {"tamperEvidenceOnly", true},
        }},
    };
}

Json State::snapshot() const {
    std::lock_guard lock(mutex_);
    return snapshot_unlocked();
}

int State::revision() const {
    std::lock_guard lock(mutex_);
    return revision_;
}

Json State::measure(const std::string& source, const std::vector<double>& probabilities, double tau) {
    validate_source(source);
    auto result = trinity::measure(probabilities, tau);
    std::lock_guard lock(mutex_);
    Event event{revision_ + 1, source, result};
    if (journal_) journal_->append("measure", source, result, event);
    ++revision_;
    active_ = result;
    events_.push_back(std::move(event));
    if (events_.size() > max_events) events_.erase(events_.begin());
    return snapshot_unlocked();
}

Json State::reset(const std::string& source) {
    validate_source(source);
    auto active = trinity::measure({0.70, 0.20, 0.08, 0.02}, 0.05);
    std::lock_guard lock(mutex_);
    if (journal_) journal_->append("reset", source, active, std::nullopt);
    ++revision_;
    active_ = active;
    events_.clear();
    return snapshot_unlocked();
}

}  // namespace trinity
