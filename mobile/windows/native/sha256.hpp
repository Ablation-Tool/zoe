#pragma once

#include <array>
#include <cstdint>
#include <string>

namespace trinity {

class Sha256 {
public:
    Sha256();
    void update(const std::uint8_t* data, std::size_t size);
    std::array<std::uint8_t, 32> finish();

private:
    void transform(const std::uint8_t* block);
    std::array<std::uint32_t, 8> state_;
    std::array<std::uint8_t, 64> buffer_{};
    std::uint64_t bits_ = 0;
    std::size_t used_ = 0;
};

std::string sha256(const std::string& input);

}  // namespace trinity
