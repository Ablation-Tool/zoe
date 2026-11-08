#pragma once

#include <map>
#include <string>
#include <variant>
#include <vector>

namespace trinity {

class Json {
public:
    using Array = std::vector<Json>;
    using Object = std::map<std::string, Json>;
    using Value = std::variant<std::nullptr_t, bool, double, std::string, Array, Object>;

    Json() : value(nullptr) {}
    Json(std::nullptr_t) : value(nullptr) {}
    Json(bool item) : value(item) {}
    Json(int item) : value(static_cast<double>(item)) {}
    Json(double item) : value(item) {}
    Json(const char* item) : value(std::string(item)) {}
    Json(std::string item) : value(std::move(item)) {}
    Json(Array item) : value(std::move(item)) {}
    Json(Object item) : value(std::move(item)) {}

    const Value& get() const { return value; }
    const Object& object() const;
    const Array& array() const;
    const std::string& string() const;
    double number() const;
    bool boolean() const;
    int integer() const;
    const Json& at(const std::string& key) const;
    bool contains(const std::string& key) const;
    std::string dump() const;
    static Json parse(const std::string& text);

private:
    Value value;
};

std::string number(double value);

}  // namespace trinity
