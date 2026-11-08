#include "sha256.hpp"
#include "trinity_core.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <vector>

using namespace trinity;

namespace {

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void measurements() {
    check(sha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "SHA-256 mismatch");
    const auto parsed = Json::parse("{\"a\":[1,true,null,\"zoe\"]}");
    check(parsed.at("a").array().size() == 4, "JSON parser mismatch");
    check(Json::parse(parsed.dump()).dump() == parsed.dump(), "JSON roundtrip mismatch");
    const auto example = measure({0.70, 0.20, 0.08, 0.02}, 0.05);
    check(example.zoe.accessible == 3 && example.tiny.counts.accessible == 3, "worked example mismatch");
    check(example.tiny.request == "800200000A0666599A199A0A3D028F", "Tiny request mismatch");
    check(example.tiny.response == "00030001000406669000", "Tiny response mismatch");
    check(measure({0.70, 0.20, 0.08, 0.02}, 0.20).zoe.accessible == 1, "strict equality mismatch");
    check(measure({0.25, 0.25, 0.25, 0.25}, 1).zoe.accessible == 0, "tau one mismatch");
    check(measure({1, 0, 0}, 0).zoe.accessible == 1, "zero probabilities mismatch");
    const auto restored = measurement_from_json(measurement_json(example));
    check(restored.tiny.request == example.tiny.request, "measurement roundtrip mismatch");
    bool rejected = false;
    try { measure({0.5, 0.4}, 0.05); } catch (const std::exception&) { rejected = true; }
    check(rejected, "invalid sum was accepted");
    std::vector<double> uniform(64, 1.0 / 64);
    check(measure(uniform, 0).tiny.request.size() == 270, "maximum request mismatch");
    check(measure(uniform, 0).tiny.response == "00400000004000009000", "uniform witness mismatch");
    check(measure({0.1, 0.2, 0.3, 0.4}, 0.2).tiny.request == "800200000A199A0CCD199A26663333", "mixed decimal witness mismatch");
    check(measure({0.25, 0.25, 0.25, 0.25}, 0.25).tiny.response == "00000004000420009000", "threshold equality witness mismatch");
    check(measure({0.00001, 0.99999}, 0.00001).tiny.request == "8002000006000000008000", "small decimal witness mismatch");
    check(measure({0.3333333333333333, 0.3333333333333333, 0.3333333333333334}, 0.3333333333333333).tiny.request
        == "80020000082AAB2AAB2AAA2AAB", "large-remainder witness mismatch");
}

void shared_state() {
    State state;
    state.measure("android", {0.70, 0.20, 0.08, 0.02}, 0.05);
    state.measure("laptop", {0.70, 0.20, 0.08, 0.02}, 0.20);
    auto snapshot = state.snapshot();
    check(snapshot.at("revision").integer() == 2, "shared revision mismatch");
    check(snapshot.at("events").array().size() == 2, "shared events mismatch");
    check(snapshot.at("active").at("zoe").at("accessible").integer() == 1, "active result mismatch");
    state.reset("apple");
    check(state.snapshot().at("events").array().empty(), "reset did not clear live view");
}

void concurrent_state() {
    State state;
    std::vector<std::thread> workers;
    for (int index = 0; index < 24; ++index) {
        workers.emplace_back([&, index] {
            state.measure(index % 2 ? "android" : "laptop", {1.0}, 0.0);
        });
    }
    for (auto& worker : workers) worker.join();
    auto snapshot = state.snapshot();
    check(snapshot.at("revision").integer() == 24, "concurrent revision mismatch");
    const auto& events = snapshot.at("events").array();
    for (std::size_t index = 0; index < events.size(); ++index) {
        check(events[index].at("ordinal").integer() == static_cast<int>(index + 1), "concurrent order mismatch");
    }
}

void journal() {
    const auto directory = std::filesystem::temp_directory_path() / "zoe-native-journal-test";
    std::filesystem::remove_all(directory);
    std::filesystem::create_directory(directory);
    const auto path = directory / "memory.jsonl";
    {
        Journal journal(path);
        State state(&journal);
        state.measure("android", {0.70, 0.20, 0.08, 0.02}, 0.05);
        state.reset("laptop");
        state.measure("apple", {0.25, 0.25, 0.25, 0.25}, 0.25);
        check(journal.size() == 3, "journal size mismatch");
    }
    {
        Journal journal(path);
        State state(&journal);
        check(state.revision() == 3, "journal revision mismatch");
        check(state.snapshot().at("events").array().size() == 1, "journal live history mismatch");
        check(state.snapshot().at("active").at("zoe").at("accessible").integer() == 0, "journal measurement mismatch");
    }
    {
        std::fstream file(path, std::ios::in | std::ios::out | std::ios::binary);
        std::string line;
        std::getline(file, line);
        file.seekp(0);
        line[0] = line[0] == 'X' ? 'Y' : 'X';
        file << line;
    }
    bool rejected = false;
    try { Journal edited(path); } catch (const std::exception&) { rejected = true; }
    check(rejected, "edited journal was accepted");
    std::filesystem::remove_all(directory);
}

}  // namespace

int main() {
    try {
        measurements();
        shared_state();
        concurrent_state();
        journal();
        std::cout << "Native Trinity core: 4 suites passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Native Trinity test failed: " << error.what() << '\n';
        return 1;
    }
}
