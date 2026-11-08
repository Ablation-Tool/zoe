#include "json.hpp"

#include <charconv>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace trinity {

std::string number(double value) {
    if (!std::isfinite(value)) throw std::runtime_error("non-finite JSON number");
    char buffer[64];
    const auto result = std::to_chars(buffer, buffer + sizeof(buffer), value, std::chars_format::general);
    if (result.ec != std::errc()) throw std::runtime_error("could not format JSON number");
    return std::string(buffer, result.ptr);
}

const Json::Object& Json::object() const {
    if (!std::holds_alternative<Object>(value)) throw std::runtime_error("JSON value is not an object");
    return std::get<Object>(value);
}

const Json::Array& Json::array() const {
    if (!std::holds_alternative<Array>(value)) throw std::runtime_error("JSON value is not an array");
    return std::get<Array>(value);
}

const std::string& Json::string() const {
    if (!std::holds_alternative<std::string>(value)) throw std::runtime_error("JSON value is not a string");
    return std::get<std::string>(value);
}

double Json::number() const {
    if (!std::holds_alternative<double>(value)) throw std::runtime_error("JSON value is not a number");
    return std::get<double>(value);
}

bool Json::boolean() const {
    if (!std::holds_alternative<bool>(value)) throw std::runtime_error("JSON value is not a boolean");
    return std::get<bool>(value);
}

int Json::integer() const {
    const double item = number();
    if (item < std::numeric_limits<int>::min() || item > std::numeric_limits<int>::max()
        || item != static_cast<int>(item)) throw std::runtime_error("JSON value is not an integer");
    return static_cast<int>(item);
}

const Json& Json::at(const std::string& key) const {
    const auto& values = object();
    const auto found = values.find(key);
    if (found == values.end()) throw std::runtime_error("missing JSON key: " + key);
    return found->second;
}

bool Json::contains(const std::string& key) const {
    const auto& values = object();
    return values.find(key) != values.end();
}

namespace {

void dump_string(const std::string& value, std::string& output) {
    static const char* digits = "0123456789abcdef";
    output.push_back('"');
    for (const unsigned char byte : value) {
        switch (byte) {
            case '"': output += "\\\""; break;
            case '\\': output += "\\\\"; break;
            case '\b': output += "\\b"; break;
            case '\f': output += "\\f"; break;
            case '\n': output += "\\n"; break;
            case '\r': output += "\\r"; break;
            case '\t': output += "\\t"; break;
            default:
                if (byte < 0x20) {
                    output += "\\u00";
                    output.push_back(digits[byte >> 4]);
                    output.push_back(digits[byte & 15]);
                } else {
                    output.push_back(static_cast<char>(byte));
                }
        }
    }
    output.push_back('"');
}

void dump_value(const Json& value, std::string& output) {
    const auto& raw = value.get();
    if (std::holds_alternative<std::nullptr_t>(raw)) {
        output += "null";
    } else if (const auto* item = std::get_if<bool>(&raw)) {
        output += *item ? "true" : "false";
    } else if (const auto* item = std::get_if<double>(&raw)) {
        output += trinity::number(*item);
    } else if (const auto* item = std::get_if<std::string>(&raw)) {
        dump_string(*item, output);
    } else if (const auto* items = std::get_if<Json::Array>(&raw)) {
        output.push_back('[');
        for (std::size_t index = 0; index < items->size(); ++index) {
            if (index) output.push_back(',');
            dump_value((*items)[index], output);
        }
        output.push_back(']');
    } else {
        const auto& members = std::get<Json::Object>(raw);
        output.push_back('{');
        bool first = true;
        for (const auto& [key, item] : members) {
            if (!first) output.push_back(',');
            first = false;
            dump_string(key, output);
            output.push_back(':');
            dump_value(item, output);
        }
        output.push_back('}');
    }
}

void append_utf8(unsigned value, std::string& output) {
    if (value <= 0x7f) {
        output.push_back(static_cast<char>(value));
    } else if (value <= 0x7ff) {
        output.push_back(static_cast<char>(0xc0 | (value >> 6)));
        output.push_back(static_cast<char>(0x80 | (value & 63)));
    } else {
        output.push_back(static_cast<char>(0xe0 | (value >> 12)));
        output.push_back(static_cast<char>(0x80 | ((value >> 6) & 63)));
        output.push_back(static_cast<char>(0x80 | (value & 63)));
    }
}

class Parser {
public:
    explicit Parser(const std::string& input) : input_(input) {
        if (input.size() > 1048576) throw std::runtime_error("JSON input exceeds 1 MiB");
    }

    Json run() {
        space();
        auto result = value(0);
        space();
        if (position_ != input_.size()) throw std::runtime_error("trailing JSON data");
        return result;
    }

private:
    const std::string& input_;
    std::size_t position_ = 0;

    void space() {
        while (position_ < input_.size()) {
            const char item = input_[position_];
            if (item != ' ' && item != '\n' && item != '\r' && item != '\t') break;
            ++position_;
        }
    }

    char take() {
        if (position_ >= input_.size()) throw std::runtime_error("unexpected end of JSON");
        return input_[position_++];
    }

    bool consume(char expected) {
        if (position_ < input_.size() && input_[position_] == expected) {
            ++position_;
            return true;
        }
        return false;
    }

    void literal(const char* expected) {
        while (*expected) {
            if (take() != *expected++) throw std::runtime_error("invalid JSON literal");
        }
    }

    Json value(int depth) {
        if (depth > 32) throw std::runtime_error("JSON nesting exceeds 32 levels");
        if (position_ >= input_.size()) throw std::runtime_error("missing JSON value");
        switch (input_[position_]) {
            case '{': return object_value(depth);
            case '[': return array_value(depth);
            case '"': take(); return Json(string_value());
            case 't': literal("true"); return Json(true);
            case 'f': literal("false"); return Json(false);
            case 'n': literal("null"); return Json(nullptr);
            default: return Json(number_value());
        }
    }

    Json object_value(int depth) {
        take();
        Json::Object result;
        space();
        if (consume('}')) return result;
        while (true) {
            space();
            if (!consume('"')) throw std::runtime_error("object key must be a string");
            auto key = string_value();
            space();
            if (!consume(':')) throw std::runtime_error("missing object colon");
            space();
            result[std::move(key)] = value(depth + 1);
            space();
            if (consume('}')) break;
            if (!consume(',')) throw std::runtime_error("missing object comma");
        }
        return result;
    }

    Json array_value(int depth) {
        take();
        Json::Array result;
        space();
        if (consume(']')) return result;
        while (true) {
            space();
            result.push_back(value(depth + 1));
            space();
            if (consume(']')) break;
            if (!consume(',')) throw std::runtime_error("missing array comma");
        }
        return result;
    }

    std::string string_value() {
        std::string result;
        while (true) {
            const unsigned char item = static_cast<unsigned char>(take());
            if (item == '"') break;
            if (item < 0x20) throw std::runtime_error("control character in JSON string");
            if (item != '\\') {
                result.push_back(static_cast<char>(item));
                continue;
            }
            switch (take()) {
                case '"': result.push_back('"'); break;
                case '\\': result.push_back('\\'); break;
                case '/': result.push_back('/'); break;
                case 'b': result.push_back('\b'); break;
                case 'f': result.push_back('\f'); break;
                case 'n': result.push_back('\n'); break;
                case 'r': result.push_back('\r'); break;
                case 't': result.push_back('\t'); break;
                case 'u': {
                    unsigned code = 0;
                    for (int index = 0; index < 4; ++index) {
                        const char digit = take();
                        code *= 16;
                        if (digit >= '0' && digit <= '9') code += digit - '0';
                        else if (digit >= 'a' && digit <= 'f') code += digit - 'a' + 10;
                        else if (digit >= 'A' && digit <= 'F') code += digit - 'A' + 10;
                        else throw std::runtime_error("invalid Unicode escape");
                    }
                    if (code >= 0xd800 && code <= 0xdfff) throw std::runtime_error("unsupported surrogate escape");
                    append_utf8(code, result);
                    break;
                }
                default: throw std::runtime_error("invalid JSON escape");
            }
        }
        return result;
    }

    double number_value() {
        const auto start = position_;
        consume('-');
        if (consume('0')) {
        } else {
            if (position_ >= input_.size() || input_[position_] < '1' || input_[position_] > '9')
                throw std::runtime_error("invalid JSON number");
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') ++position_;
        }
        if (consume('.')) {
            const auto before = position_;
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') ++position_;
            if (before == position_) throw std::runtime_error("invalid JSON fraction");
        }
        if (position_ < input_.size() && (input_[position_] == 'e' || input_[position_] == 'E')) {
            ++position_;
            if (position_ < input_.size() && (input_[position_] == '+' || input_[position_] == '-')) ++position_;
            const auto before = position_;
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') ++position_;
            if (before == position_) throw std::runtime_error("invalid JSON exponent");
        }
        const auto text = input_.substr(start, position_ - start);
        char* end = nullptr;
        const double result = std::strtod(text.c_str(), &end);
        if (!std::isfinite(result) || end != text.c_str() + text.size()) throw std::runtime_error("invalid JSON number");
        return result;
    }
};

}  // namespace

std::string Json::dump() const {
    std::string output;
    dump_value(*this, output);
    return output;
}

Json Json::parse(const std::string& text) {
    return Parser(text).run();
}

}  // namespace trinity
