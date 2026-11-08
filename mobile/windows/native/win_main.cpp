#include "http_server.hpp"
#include "trinity_core.hpp"

#include <windows.h>
#include <commdlg.h>
#include <shellapi.h>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr COLORREF paper = RGB(243, 240, 233);
constexpr COLORREF ink = RGB(16, 16, 18);
constexpr COLORREF red = RGB(216, 51, 79);
constexpr COLORREF blue = RGB(20, 111, 124);
constexpr COLORREF white = RGB(255, 253, 248);
constexpr UINT update_message = WM_APP + 41;
constexpr int distribution_id = 100;
constexpr int tau_id = 101;
constexpr int measure_id = 102;
constexpr int reset_id = 103;
constexpr int link_id = 104;
constexpr int export_id = 105;
constexpr int status_id = 106;
constexpr int tiny_id = 107;
constexpr int mobile_id = 108;
constexpr int laptop_id = 109;
constexpr int history_id = 110;
constexpr int tiny_big_id = 111;
constexpr int mobile_big_id = 112;
constexpr int laptop_big_id = 113;

struct App {
    std::unique_ptr<trinity::Journal> journal;
    std::unique_ptr<trinity::State> state;
    std::unique_ptr<trinity::HttpServer> server;
    HWND window = nullptr;
    HWND distribution = nullptr;
    HWND tau = nullptr;
    HWND link = nullptr;
    HWND status = nullptr;
    HWND tiny = nullptr;
    HWND mobile = nullptr;
    HWND laptop = nullptr;
    HWND tiny_big = nullptr;
    HWND mobile_big = nullptr;
    HWND laptop_big = nullptr;
    HWND history = nullptr;
    HFONT body_font = nullptr;
    HFONT label_font = nullptr;
    HFONT big_font = nullptr;
    std::string host = "127.0.0.1";
    std::string pair;
};

App app;

std::string utf8(const std::wstring& value) {
    if (value.empty()) return "";
    const int size = WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    std::string result(size, '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), result.data(), size, nullptr, nullptr);
    return result;
}

std::wstring wide(const std::string& value) {
    if (value.empty()) return L"";
    const int size = MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0);
    std::wstring result(size, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), result.data(), size);
    return result;
}

std::wstring control_text(HWND control) {
    const int length = GetWindowTextLengthW(control);
    std::wstring value(length, L'\0');
    GetWindowTextW(control, value.data(), length + 1);
    return value;
}

void set_text(HWND control, const std::string& value) {
    SetWindowTextW(control, wide(value).c_str());
}

HWND create(DWORD style, const wchar_t* type, const wchar_t* text, int id = 0) {
    return CreateWindowExW(0, type, text, WS_CHILD | WS_VISIBLE | style,
                           0, 0, 0, 0, app.window, reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
                           GetModuleHandleW(nullptr), nullptr);
}

void font(HWND control, HFONT value) {
    SendMessageW(control, WM_SETFONT, reinterpret_cast<WPARAM>(value), TRUE);
}

void layout_control(HWND control, int x, int y, int width, int height) {
    MoveWindow(control, x, y, std::max(10, width), std::max(10, height), TRUE);
}

void refresh() {
    if (!app.state) return;
    const auto snapshot = app.state->snapshot();
    const auto& active = snapshot.at("active");
    const auto& zoe = active.at("zoe");
    const auto& tiny = active.at("tiny");
    const auto revision = snapshot.at("revision").integer();
    set_text(app.tiny_big, std::to_string(tiny.at("accessible").integer()) + " / "
        + std::to_string(tiny.at("vocabularySize").integer()));
    set_text(app.mobile_big, std::to_string(zoe.at("accessible").integer()) + " / "
        + std::to_string(zoe.at("vocabularySize").integer()));
    set_text(app.laptop_big, "R" + std::to_string(revision));
    set_text(app.tiny, "Complement " + std::to_string(tiny.at("complement").integer())
        + " · Q0.15 tau " + std::to_string(tiny.at("tau").integer()) + "/32768\n"
        + (active.at("quantizationChanged").boolean() ? "Quantization changed the representation or count" : "Quantized count agrees with mobile")
        + "\nAPDU " + tiny.at("request").string() + "\nReply " + tiny.at("response").string());
    set_text(app.mobile, "Complement " + std::to_string(zoe.at("complement").integer())
        + " · strict p > " + trinity::number(active.at("tau").number())
        + "\nNormalized accessible volume " + trinity::number(zoe.at("normalized").number())
        + "\nEquality excluded · no action authorized");
    set_text(app.laptop, std::to_string(snapshot.at("events").array().size()) + " retained live observations\n"
        + (snapshot.at("memory").at("enabled").boolean()
            ? std::to_string(snapshot.at("memory").at("records").integer()) + " journal events · verified on load\nTamper evidence, not authentication"
            : "Memory only · use --memory PATH for a verified journal\nNo camera or microphone is used"));
    std::string notes;
    const auto& events = snapshot.at("events").array();
    for (auto item = events.rbegin(); item != events.rend(); ++item) {
        notes += "#" + std::to_string(item->at("ordinal").integer()) + " · " + item->at("source").string()
            + " · tau " + trinity::number(item->at("tau").number()) + "\r\nMobile A "
            + std::to_string(item->at("zoe").at("accessible").integer()) + "/"
            + std::to_string(item->at("zoe").at("vocabularySize").integer()) + " · Tiny A "
            + std::to_string(item->at("tiny").at("accessible").integer()) + "/"
            + std::to_string(item->at("tiny").at("vocabularySize").integer()) + "\r\n";
    }
    set_text(app.history, notes.empty() ? "No shared measurements yet. Make the first mark." : notes);
}

void measure() {
    try {
        auto text = utf8(control_text(app.distribution));
        if (text.empty() || text.size() > 4096) throw std::runtime_error("Enter 1 to 64 probabilities");
        for (char& item : text) if (item == ',') item = ' ';
        std::vector<double> values;
        std::size_t position = 0;
        while (position < text.size()) {
            while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position]))) ++position;
            if (position >= text.size()) break;
            char* end = nullptr;
            const double value = std::strtod(text.c_str() + position, &end);
            if (end == text.c_str() + position) throw std::runtime_error("Invalid probability distribution");
            values.push_back(value);
            if (values.size() > trinity::max_probabilities) throw std::runtime_error("At most 64 probabilities");
            position = static_cast<std::size_t>(end - text.c_str());
        }
        const auto tau_text = utf8(control_text(app.tau));
        if (tau_text.empty() || tau_text.size() > 64) throw std::runtime_error("Invalid threshold text");
        char* end = nullptr;
        const double tau = std::strtod(tau_text.c_str(), &end);
        if (end != tau_text.c_str() + tau_text.size()) throw std::runtime_error("Invalid threshold");
        app.state->measure("laptop", values, tau);
        set_text(app.status, "Measured together across all three planes. Revision " + std::to_string(app.state->revision()) + ".");
        refresh();
    } catch (const std::exception& error) {
        set_text(app.status, std::string("Experiment rejected: ") + error.what());
    }
}

void toggle_server() {
    try {
        if (app.server->running()) {
            app.server->stop();
            set_text(app.link, "Start local link");
            set_text(app.status, "Local link stopped. No further phone requests will be accepted.");
            return;
        }
        app.server->start(app.host, app.pair, [] {
            if (app.window) PostMessageW(app.window, update_message, 0, 0);
        });
        set_text(app.link, "Stop local link");
        set_text(app.status, "Native local link active on " + app.host + ":8767. Android: adb reverse tcp:8767 tcp:8767. No cloud relay.");
    } catch (const std::exception& error) {
        set_text(app.status, std::string("Local link failed: ") + error.what());
    }
}

void reset() {
    if (MessageBoxW(app.window, L"Start a fresh shared view? An enabled journal preserves all earlier events.",
                    L"Zoe Trinity", MB_YESNO | MB_ICONQUESTION) != IDYES) return;
    app.state->reset("laptop");
    set_text(app.distribution, "0.70, 0.20, 0.08, 0.02");
    set_text(app.tau, "0.05");
    set_text(app.status, "Fresh shared view started. No external action was authorized.");
    refresh();
}

void export_state() {
    wchar_t path[MAX_PATH] = L"zoe-trinity.json";
    OPENFILENAMEW dialog{};
    dialog.lStructSize = sizeof(dialog);
    dialog.hwndOwner = app.window;
    dialog.lpstrFilter = L"JSON files\0*.json\0All files\0*.*\0";
    dialog.lpstrFile = path;
    dialog.nMaxFile = MAX_PATH;
    dialog.lpstrDefExt = L"json";
    dialog.Flags = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST;
    if (!GetSaveFileNameW(&dialog)) return;
    try {
        std::ofstream output(path, std::ios::binary | std::ios::trunc);
        if (!output) throw std::runtime_error("could not open export");
        output << app.state->snapshot().dump() << '\n';
        output.close();
        if (!output) throw std::runtime_error("could not finish export");
        set_text(app.status, "Exported the current local state. Zoe did not upload it.");
    } catch (const std::exception& error) {
        set_text(app.status, std::string("Export failed: ") + error.what());
    }
}

void layout() {
    RECT bounds;
    GetClientRect(app.window, &bounds);
    const int width = bounds.right - bounds.left;
    const int height = bounds.bottom - bounds.top;
    const int margin = 24;
    const int content = width - margin * 2;
    layout_control(app.distribution, margin, 152, std::max(300, content * 2 / 3), 54);
    layout_control(app.tau, margin, 224, 180, 32);
    MoveWindow(GetDlgItem(app.window, measure_id), margin + 196, 222, 176, 40, TRUE);
    MoveWindow(GetDlgItem(app.window, reset_id), margin + 384, 222, 160, 40, TRUE);
    MoveWindow(GetDlgItem(app.window, link_id), margin + 556, 222, 170, 40, TRUE);
    MoveWindow(GetDlgItem(app.window, export_id), margin + 738, 222, 130, 40, TRUE);
    layout_control(app.status, margin, 274, content, 42);
    const int gap = 12;
    const int columns = std::max(240, (content - gap * 2) / 3);
    const int plane_height = std::max(230, height - 600);
    for (int index = 0; index < 3; ++index) {
        const int x = margin + index * (columns + gap);
        HWND big = index == 0 ? app.tiny_big : index == 1 ? app.mobile_big : app.laptop_big;
        HWND detail = index == 0 ? app.tiny : index == 1 ? app.mobile : app.laptop;
        layout_control(big, x + 18, 398, columns - 36, 70);
        layout_control(detail, x + 18, 474, columns - 36, plane_height - 166);
    }
    layout_control(app.history, margin, height - 174, content, 136);
    InvalidateRect(app.window, nullptr, TRUE);
}

LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    switch (message) {
        case WM_CREATE: {
            app.window = window;
            app.body_font = CreateFontW(-17, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Consolas");
            app.label_font = CreateFontW(-13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Consolas");
            app.big_font = CreateFontW(-54, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Georgia");
            app.distribution = create(WS_BORDER | ES_AUTOHSCROLL, L"EDIT", L"0.70, 0.20, 0.08, 0.02", distribution_id);
            app.tau = create(WS_BORDER | ES_AUTOHSCROLL, L"EDIT", L"0.05", tau_id);
            app.status = create(SS_LEFT, L"STATIC", L"Native Windows · local link is off. Measure locally or start the link explicitly.", status_id);
            app.tiny = create(SS_LEFT, L"STATIC", L"", tiny_id);
            app.mobile = create(SS_LEFT, L"STATIC", L"", mobile_id);
            app.laptop = create(SS_LEFT, L"STATIC", L"", laptop_id);
            app.tiny_big = create(SS_LEFT, L"STATIC", L"", tiny_big_id);
            app.mobile_big = create(SS_LEFT, L"STATIC", L"", mobile_big_id);
            app.laptop_big = create(SS_LEFT, L"STATIC", L"", laptop_big_id);
            app.history = create(WS_BORDER | ES_MULTILINE | ES_READONLY | WS_VSCROLL, L"EDIT", L"", history_id);
            app.link = create(BS_PUSHBUTTON, L"BUTTON", L"Start local link", link_id);
            create(BS_PUSHBUTTON, L"BUTTON", L"Measure together", measure_id);
            create(BS_PUSHBUTTON, L"BUTTON", L"Fresh view", reset_id);
            create(BS_PUSHBUTTON, L"BUTTON", L"Export JSON", export_id);
            for (int id = distribution_id; id <= laptop_big_id; ++id) {
                HWND control = GetDlgItem(window, id);
                if (control) font(control, app.body_font);
            }
            font(app.tiny_big, app.big_font);
            font(app.mobile_big, app.big_font);
            font(app.laptop_big, app.big_font);
            SendMessageW(app.distribution, EM_SETLIMITTEXT, 4096, 0);
            SendMessageW(app.tau, EM_SETLIMITTEXT, 64, 0);
            refresh();
            layout();
            return 0;
        }
        case WM_SIZE: layout(); return 0;
        case WM_COMMAND:
            switch (LOWORD(wparam)) {
                case measure_id: measure(); return 0;
                case reset_id: reset(); return 0;
                case link_id: toggle_server(); return 0;
                case export_id: export_state(); return 0;
            }
            return 0;
        case update_message: refresh(); return 0;
        case WM_CTLCOLORSTATIC: {
            const auto context = reinterpret_cast<HDC>(wparam);
            const auto control = reinterpret_cast<HWND>(lparam);
            SetBkMode(context, TRANSPARENT);
            if (control == app.mobile || control == app.mobile_big) {
                SetTextColor(context, white);
                return reinterpret_cast<LRESULT>(GetStockObject(NULL_BRUSH));
            }
            SetTextColor(context, control == app.status ? blue : ink);
            return reinterpret_cast<LRESULT>(GetStockObject(NULL_BRUSH));
        }
        case WM_PAINT: {
            PAINTSTRUCT paint;
            const auto context = BeginPaint(window, &paint);
            RECT bounds;
            GetClientRect(window, &bounds);
            const auto background = CreateSolidBrush(paper);
            FillRect(context, &bounds, background);
            DeleteObject(background);
            const auto title = CreateFontW(-48, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Georgia");
            const auto old = SelectObject(context, title);
            SetBkMode(context, TRANSPARENT);
            SetTextColor(context, ink);
            TextOutW(context, 24, 28, L"ZOE", 3);
            SetTextColor(context, red);
            TextOutW(context, 130, 28, L"TRINITY", 7);
            SelectObject(context, old);
            DeleteObject(title);
            SelectObject(context, app.label_font);
            SetTextColor(context, ink);
            const std::wstring eyebrow = L"NUCLIDE RESEARCH  /  THREE PLANES  /  ONE SHARED FIELD";
            TextOutW(context, 26, 4, eyebrow.c_str(), static_cast<int>(eyebrow.size()));
            const std::wstring places = L"PLAY · LEARN · ADAPT · CREATE · EXPLORE · SHARE";
            SetTextColor(context, red);
            TextOutW(context, 26, 94, places.c_str(), static_cast<int>(places.size()));
            SetTextColor(context, blue);
            const std::wstring signature = L"SMALL OBSERVATIONS. STRANGE IDEAS. CAREFUL EVIDENCE.";
            TextOutW(context, 26, 112, signature.c_str(), static_cast<int>(signature.size()));
            SetTextColor(context, ink);
            const std::wstring probabilities = L"PROBABILITY DISTRIBUTION";
            TextOutW(context, 26, 134, probabilities.c_str(), static_cast<int>(probabilities.size()));
            const std::wstring threshold = L"THRESHOLD TAU";
            TextOutW(context, 26, 208, threshold.c_str(), static_cast<int>(threshold.size()));
            const std::wstring history = L"FIELD NOTES / NEWEST FIRST";
            TextOutW(context, 26, bounds.bottom - 204, history.c_str(), static_cast<int>(history.size()));
            const int columns = std::max(240, static_cast<int>((bounds.right - bounds.left - 48 - 24) / 3));
            const int plane_height = std::max(230, static_cast<int>(bounds.bottom - bounds.top - 600));
            const wchar_t* names[] = {L"01  TINY ZOE / CELL PLANE", L"02  ZOE MOBILE / NATIVE PLANE", L"03  LAPTOP ZOE / FIELD PLANE"};
            for (int index = 0; index < 3; ++index) {
                RECT panel{24 + index * (columns + 12), 326, 24 + index * (columns + 12) + columns, 326 + plane_height};
                HBRUSH brush = CreateSolidBrush(index == 1 ? ink : white);
                FillRect(context, &panel, brush);
                DeleteObject(brush);
                SetTextColor(context, index == 1 ? white : ink);
                TextOutW(context, panel.left + 18, panel.top + 18, names[index], static_cast<int>(wcslen(names[index])));
            }
            const int eye_x = bounds.right - 142;
            const int eye_y = 28;
            HPEN orbit_pen = CreatePen(PS_SOLID, 2, ink);
            HGDIOBJ old_pen = SelectObject(context, orbit_pen);
            Ellipse(context, eye_x, eye_y, eye_x + 96, eye_y + 64);
            DeleteObject(orbit_pen);
            orbit_pen = CreatePen(PS_SOLID, 2, red);
            SelectObject(context, orbit_pen);
            Ellipse(context, eye_x - 12, eye_y + 16, eye_x + 108, eye_y + 48);
            DeleteObject(orbit_pen);
            orbit_pen = CreatePen(PS_SOLID, 2, blue);
            SelectObject(context, orbit_pen);
            Ellipse(context, eye_x + 32, eye_y - 14, eye_x + 64, eye_y + 78);
            DeleteObject(orbit_pen);
            HBRUSH iris = CreateSolidBrush(red);
            HGDIOBJ old_brush = SelectObject(context, iris);
            Ellipse(context, eye_x + 43, eye_y + 27, eye_x + 53, eye_y + 37);
            SelectObject(context, old_brush);
            DeleteObject(iris);
            SelectObject(context, old_pen);
            const int cup_x = bounds.right - 72;
            POINT upper[] = {{cup_x - 22, 108}, {cup_x + 22, 108}, {cup_x, 134}};
            POINT lower[] = {{cup_x, 134}, {cup_x - 22, 160}, {cup_x + 22, 160}};
            HBRUSH cup = CreateSolidBrush(red);
            old_brush = SelectObject(context, cup);
            Polygon(context, upper, 3);
            SelectObject(context, old_brush);
            DeleteObject(cup);
            cup = CreateSolidBrush(blue);
            old_brush = SelectObject(context, cup);
            Polygon(context, lower, 3);
            SelectObject(context, old_brush);
            DeleteObject(cup);
            EndPaint(window, &paint);
            return 0;
        }
        case WM_DESTROY:
            if (app.server) app.server->stop();
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProcW(window, message, wparam, lparam);
}

std::vector<std::string> arguments() {
    int count = 0;
    const auto values = CommandLineToArgvW(GetCommandLineW(), &count);
    std::vector<std::string> result;
    for (int index = 1; index < count; ++index) result.push_back(utf8(values[index]));
    LocalFree(values);
    return result;
}

int run() {
    bool headless = false;
    bool start_server = false;
    int duration = 0;
    std::string memory;
    const auto args = arguments();
    for (std::size_t index = 0; index < args.size(); ++index) {
        if (args[index] == "--headless") headless = true;
        else if (args[index] == "--start-server") start_server = true;
        else if (args[index] == "--duration" && index + 1 < args.size()) duration = std::stoi(args[++index]);
        else if (args[index] == "--memory" && index + 1 < args.size()) memory = args[++index];
        else if (args[index] == "--lan" && index + 1 < args.size()) app.host = args[++index];
        else throw std::runtime_error("unknown or incomplete argument: " + args[index]);
    }
    if (const char* pair = std::getenv("ZOE_TRINITY_PAIR")) app.pair = pair;
    if (!memory.empty()) app.journal = std::make_unique<trinity::Journal>(memory);
    app.state = std::make_unique<trinity::State>(app.journal.get());
    app.server = std::make_unique<trinity::HttpServer>(*app.state);
    if (headless || start_server) app.server->start(app.host, app.pair, [] {});
    if (headless) {
        if (duration > 0) std::this_thread::sleep_for(std::chrono::seconds(duration));
        else while (true) std::this_thread::sleep_for(std::chrono::hours(24));
        app.server->stop();
        return 0;
    }
    SetProcessDPIAware();
    WNDCLASSW window_class{};
    window_class.lpfnWndProc = window_proc;
    window_class.hInstance = GetModuleHandleW(nullptr);
    window_class.lpszClassName = L"ZoeTrinityNative";
    window_class.hCursor = LoadCursor(nullptr, IDC_ARROW);
    window_class.hIcon = LoadIcon(nullptr, IDI_APPLICATION);
    if (!RegisterClassW(&window_class)) throw std::runtime_error("could not register native window");
    const auto window = CreateWindowExW(0, window_class.lpszClassName, L"Zoe Trinity · NuClide Research",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_THICKFRAME | WS_MAXIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 1220, 900, nullptr, nullptr, window_class.hInstance, nullptr);
    if (!window) throw std::runtime_error("could not create native window");
    ShowWindow(window, SW_SHOW);
    UpdateWindow(window);
    MSG message;
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    return static_cast<int>(message.wParam);
}

}  // namespace

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    try {
        return run();
    } catch (const std::exception& error) {
        MessageBoxA(nullptr, error.what(), "Zoe Trinity could not start", MB_OK | MB_ICONERROR);
        return 1;
    }
}
