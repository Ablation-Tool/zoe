/*
 * zoe_gem_fb.c — Interactive Hardware /dev/fb0 Digital Research GEM Desktop.
 *
 * Compiles statically (`gcc -O2 -Wall -Wextra -Werror -static zoe_gem_fb.c -lm`)
 * with zero X11, zero Wayland, zero SDL.
 * Features:
 *   - KD_GRAPHICS active VT isolation (/dev/tty0 -> KD_TEXT restored on exit)
 *     with CLOCK_MONOTONIC 50ms VT ESC sequence state machine & hardened termios.
 *   - Unified EV_SYN-coalesced evdev input (EV_ABS, Type-B ABS_MT_* multitouch,
 *     EV_REL, BTN_LEFT/BTN_TOUCH/BTN_RIGHT), SYN_DROPPED recovery, ENODEV removal,
 *     ~1s /dev/input/event0..31 hotplug rescan, and dynamic /dev/input/mice fallback.
 *   - Responsive 3-mode layout (LANDSCAPE / PORTRAIT / MICRO-HUD <=400px) with
 *     width-clipped FONT5X7 rendering, live [O] 90-deg CCW rotation + inverse
 *     pointer mapping, and clamped modal click-through guards.
 *   - Hardware Observation Diagnostic HUD + [H] modal, live ~1s polled /mnt/uma
 *     & PCI ivshmem BAR2 (0x1af4:0x1110) ZO3 slots 0..3, non-blocking [G] toggle.
 *   - Artline 2.0 SVG persistence (atomic save + startup reload), [Z] undo group,
 *     [B] thickness (1/3/5px), [R] 16-fold radial mandala, multi-note Nick Drawer,
 *     7-Strand Sovereign DNA (ViewMAX/3 DRAW3D bevels, BeOS compact colored tabs,
 *     10 live [V] VMCOLOUR themes, Nick x Zoe HFBC crest), and LUT + horizontal-
 *     bloom 1985 P3 Amber Phosphor CRT mode [A].
 */

#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <linux/kd.h>
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#ifndef SYN_REPORT
#define SYN_REPORT 0
#endif
#ifndef SYN_DROPPED
#define SYN_DROPPED 3
#endif
#ifndef ABS_MT_SLOT
#define ABS_MT_SLOT 0x2f
#endif
#ifndef ABS_MT_POSITION_X
#define ABS_MT_POSITION_X 0x35
#endif
#ifndef ABS_MT_POSITION_Y
#define ABS_MT_POSITION_Y 0x36
#endif
#ifndef ABS_MT_TRACKING_ID
#define ABS_MT_TRACKING_ID 0x39
#endif
#ifndef BTN_TOUCH
#define BTN_TOUCH 0x14a
#endif

#define MAX_STROKES      4096
#define MAX_UNDO         512
#define MAX_EVDEVS       32
#define MAX_DRAWER_NOTES      32
#define MAX_MENU_ITEMS        12
#define MAX_TOUCH_KEYS        44
#define SOVEREIGN_THEME_COUNT 10

#define UMA_SHM_MAGIC    "ZOE-UMA1"
#define UMA_META_MAGIC   "UMA2"
#define UMA_META_OFF     4080
#define UMA_HDR_MAX      3840
#define UMA_SLOT_STRIDE  4096

#define TEST_BIT(arr, bit) \
    (((arr)[(size_t)(bit) / (8u * sizeof(unsigned long))] >> ((size_t)(bit) % (8u * sizeof(unsigned long)))) & 1UL)

#define ZOE_MIN(a, b) ((a) < (b) ? (a) : (b))
#define ZOE_MAX(a, b) ((a) > (b) ? (a) : (b))
#define ZOE_CLAMP(v, lo, hi) ((v) < (lo) ? (lo) : ((v) > (hi) ? (hi) : (v)))

typedef enum {
    MODE_LANDSCAPE = 0,
    MODE_PORTRAIT  = 1,
    MODE_MICRO     = 2
} LayoutMode;

typedef struct {
    int x, y, w, h;
} Rect;

typedef struct {
    uint32_t *pix;
    int w;
    int h;
    int stride;
    int bgr;
} Canvas;

typedef struct {
    int x0, y0, x1, y1;
    int color_idx;
    int thick;
} Stroke;

typedef struct {
    int boot;
    char author[32];
    char text[128];
} DrawerNote;

typedef struct {
    char status[16];
    char detail[64];
} HwGate;

typedef struct {
    char profile[48];
    char safety_overall[24];
    char summary[96];
    char orientation[24];
    char zo3_budget[16];
    HwGate cpu_arch;
    HwGate ram_headroom;
    HwGate persistent_storage;
    HwGate display_fb;
    HwGate input_devices;
    HwGate network;
    HwGate hardware_uma;
    char recommendation[96];
} HwObsInfo;

typedef struct {
    int fd;
    dev_t rdev;
    int idx;
    int has_rel;
    int has_abs;
    int has_mt;
    int abs_min_x, abs_max_x;
    int abs_min_y, abs_max_y;
    int mt_min_x, mt_max_x;
    int mt_min_y, mt_max_y;
    int pkt_mt_slot;
    int pkt_has_abs_x, pkt_has_abs_y;
    int pkt_abs_x, pkt_abs_y;
    int pkt_has_mt_x, pkt_has_mt_y;
    int pkt_mt_x, pkt_mt_y;
    int pkt_has_mt_track, pkt_mt_down;
    int pkt_rel_dx, pkt_rel_dy;
    int pkt_has_btn, pkt_btn_val;
    int pkt_btn_right;
} EvDev;

typedef struct {
    const char *label;
    int x0, y0, x1, y1;
    int scale;
    int action; /* 0=Desk,1=Mirror,2=Clear,3=Save,4=Drawer,5=HW,6=Flip,7=Shell,8=Power */
} MenuItem;

typedef struct {
    char boot_count[32];
    char restored[32];
    char kernel[96];
    char cpu[96];
    char ram_mb[32];
    char ip_addr[64];
    char nic[32];
    char disk[64];
    char chain_sha[48];
    char prev_sha[48];
    char drawer_count[16];
    char drawer_latest[128];
    char artline_files[32];
    char artline_sha[32];
    char rsc_bytes[32];
    char uma_gate[32];
    char uma_shm[48];
    char uma_9p[16];
    char uma_shm_ok[16];
    char uma_nick_allow[16];
    char uma_zoe_allow[16];
    char node_id[16];
    char theme[24];
    char hw_profile[48];
    char hw_safety_overall[24];
    char hw_summary[96];
    char hw_orientation[24];
    char hw_zo3_budget[16];
    char zo3_slot[16];
    char zo3_peers[16];
    char clinical_action_authorized[16];
    char flight_control_authorized[16];
    char sentience_claimed[16];
    char tokens_used[16];
} BootState;

typedef struct {
    uint32_t amber_lut[2][256];
    uint8_t *lum_buf;
    uint8_t *bloom_row;
    size_t cap_pixels;
    size_t cap_row;
    int bgr;
} RenderScratch;

typedef struct {
    uint8_t r, g, b;
} Rgb;

typedef struct {
    const char *key;
    const char *name;
    Rgb bg_a, bg_b;
    int fill_mode; /* 0=2x2 GEM dither, 1=16px grid, 2=solid/micro-grain, 3=4x4 weave */
    Rgb win_bg;
    Rgb win_ink;
    Rgb win_shadow;
    Rgb win_muted;
    Rgb tab_act_bg;
    Rgb tab_act_fg;
    Rgb tab_inact_bg;
    Rgb tab_inact_fg;
    Rgb bevel_hi;
    Rgb bevel_lo;
    Rgb menu_bg;
    Rgb menu_fg;
    Rgb accent;
    Rgb accent2;
    Rgb dark_panel;
    Rgb dark_fg;
    Rgb card_bg;
    Rgb foot_bg;
    Rgb foot_fg;
} GemTheme;

typedef struct {
    Rect r;
    char ch;
    char lbl[8];
} TouchKey;

typedef struct {
    int phys_w, phys_h;
    int log_w, log_h;
    int orient_rot; /* 0=normal, 1=90deg CCW logical->physical */
    int phys_mx, phys_my;
    int mx, my;
    int left_down;
    int prev_left;
    int draw_prev_x, draw_prev_y;
    int drawing_active;
    int active_color;
    int pen_thick;
    int mirror_on;
    int amber_crt;
    int theme_idx;
    int stroke_count;
    int strokes_full;
    Stroke strokes[MAX_STROKES];
    int undo_stack[MAX_UNDO];
    int undo_top;
    int about_modal;
    int hw_modal;
    int drawer_modal;
    int modal_dismiss_hold;
    char drawer_buf[96];
    int drawer_len;
    int drawer_scroll;
    DrawerNote notes[MAX_DRAWER_NOTES];
    int note_count;
    HwObsInfo hw_obs;
    int zo3_alive[4];
    int zo3_intact[4];
    int zo3_boot[4];
    pid_t uma_toggle_pid;
    char status_msg[140];
    int request_exit; /* 1=shell, 2=reboot, 3=poweroff */
    LayoutMode mode;
    int menu_h, foot_h;
    int sw_x[8], sw_y[8], sw_w, sw_h;
    int vx, vy, vw, vh;
    Rect uma_btn;
    Rect amber_btn;
    Rect theme_btn;
    Rect hw_row_btn;
    Rect drawer_card;
    Rect art_tools[6]; /* M, R, Z, B, S, C */
    Rect thick_btns[3]; /* 1px, 3px, 5px */
    Rect modal_rect;
    Rect modal_save_btn;
    Rect modal_cancel_btn;
    Rect kbd_rect;
    TouchKey kbd_keys[MAX_TOUCH_KEYS];
    int kbd_count;
    int kbd_shift;
    MenuItem menus[MAX_MENU_ITEMS];
    int menu_count;
    int bg_dirty;
} DesktopApp;

typedef enum {
    VT_GROUND = 0,
    VT_ESC,
    VT_CSI,
    VT_CSI_LINUX,
    VT_SS3
} VtEscState;

typedef enum {
    VKEY_NONE = 0,
    VKEY_CHAR,
    VKEY_CTRL_C,
    VKEY_CTRL_R,
    VKEY_ESC,
    VKEY_ENTER,
    VKEY_BACKSPACE,
    VKEY_UP,
    VKEY_DOWN,
    VKEY_LEFT,
    VKEY_RIGHT,
    VKEY_HOME,
    VKEY_END,
    VKEY_DEL,
    VKEY_PGUP,
    VKEY_PGDN,
    VKEY_FN
} VtKeyKind;

typedef struct {
    VtKeyKind kind;
    char ch;
} VtKeyEvent;

typedef struct {
    VtEscState state;
    struct timespec state_ts;
    char csi_buf[32];
    int csi_len;
} VtEscParser;

static const uint8_t FONT5X7[95][7] = {
    {0,0,0,0,0,0,0},{4,4,4,4,4,0,4},{10,10,0,0,0,0,0},{10,31,10,10,31,10,0},
    {4,15,20,14,5,30,4},{24,25,2,4,8,19,3},{12,18,20,8,21,18,13},{4,4,0,0,0,0,0},
    {2,4,8,8,8,4,2},{8,4,2,2,2,4,8},{0,4,21,14,21,4,0},{0,4,4,31,4,4,0},
    {0,0,0,0,0,4,8},{0,0,0,31,0,0,0},{0,0,0,0,0,6,6},{0,1,2,4,8,16,0},
    {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},{31,2,4,2,1,17,14},
    {2,6,10,18,31,2,2},{31,16,30,1,1,17,14},{6,8,16,30,17,17,14},{31,1,2,4,8,8,8},
    {14,17,17,14,17,17,14},{14,17,17,15,1,2,12},{0,6,6,0,6,6,0},{0,6,6,0,6,4,8},
    {2,4,8,16,8,4,2},{0,0,31,0,31,0,0},{8,4,2,1,2,4,8},{14,17,1,2,4,0,4},
    {14,17,23,21,23,16,14},{14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},
    {28,18,17,17,17,18,28},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},{14,17,16,23,17,17,15},
    {17,17,17,31,17,17,17},{14,4,4,4,4,4,14},{7,2,2,2,2,18,12},{17,18,20,24,20,18,17},
    {16,16,16,16,16,16,31},{17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
    {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},{15,16,16,14,1,1,30},
    {31,4,4,4,4,4,4},{17,17,17,17,17,17,14},{17,17,17,17,17,10,4},{17,17,17,21,21,27,17},
    {17,17,10,4,10,17,17},{17,17,10,4,4,4,4},{31,1,2,4,8,16,31},{14,8,8,8,8,8,14},
    {0,16,8,4,2,1,0},{14,2,2,2,2,2,14},{4,10,17,0,0,0,0},{0,0,0,0,0,0,31},
    {8,4,0,0,0,0,0},{0,0,14,1,15,17,15},{16,16,22,25,17,17,30},{0,0,14,16,16,17,14},
    {1,1,13,19,17,17,15},{0,0,14,17,31,16,14},{6,9,8,28,8,8,8},{0,15,17,17,15,1,14},
    {16,16,22,25,17,17,17},{4,0,12,4,4,4,14},{2,0,6,2,2,18,12},{16,16,18,20,24,20,18},
    {12,4,4,4,4,4,14},{0,0,26,21,21,17,17},{0,0,22,25,17,17,17},{0,0,14,17,17,17,14},
    {0,0,30,17,30,16,16},{0,0,13,19,15,1,1},{0,0,22,25,16,16,16},{0,0,14,16,14,1,30},
    {8,8,28,8,8,9,6},{0,0,17,17,17,19,13},{0,0,17,17,17,10,4},{0,0,17,17,21,21,10},
    {0,0,17,10,4,10,17},{0,0,17,17,15,1,14},{0,0,31,2,4,8,31},{2,4,4,8,4,4,2},
    {4,4,4,4,4,4,4},{8,4,4,2,4,4,8},{0,0,8,21,2,0,0},
};

static const char *ZOE_CURSOR[16] = {
    "XX..............", "XOX.............", "XOOX............", "XOOOX...........",
    "XOOOOX..........", "XOOOOOX.........", "XOOOOOOX........", "XOOOOOOOX.......",
    "XOOOOOOOOX......", "XOOOOOXXXX......", "XOOXOOX.........", "XOX.XOOX........",
    "XX..XOOX........", ".....XOOX.......", ".....XOOX.......", "......XX........",
};

static const uint8_t PAL_RGB[8][3] = {
    {250, 248, 242}, { 18,  22,  30}, {230,  57,  86}, { 34, 197,  94},
    { 59, 130, 246}, { 92, 225, 230}, {245, 158,  11}, {217,  70, 239},
};

static const char *PAL_HEX[8] = {
    "#faf8f2", "#12161e", "#e63956", "#22c55e",
    "#3b82f6", "#5ce1e6", "#f59e0b", "#d946ef"
};

static inline int rect_hit(Rect r, int x, int y) {
    return x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h;
}

static inline uint32_t pack_rgb(const Canvas *c, uint8_t r, uint8_t g, uint8_t b) {
    if (c->bgr) {
        return (0xFFu << 24) | ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
    }
    return (0xFFu << 24) | ((uint32_t)b << 16) | ((uint32_t)g << 8) | (uint32_t)r;
}

static inline uint32_t pal_col(const Canvas *c, int idx) {
    if (idx < 0 || idx > 7) {
        idx = 5;
    }
    return pack_rgb(c, PAL_RGB[idx][0], PAL_RGB[idx][1], PAL_RGB[idx][2]);
}

static inline uint32_t pal_col_artline(const Canvas *c, int idx, int amber_crt) {
    if (idx < 0 || idx > 7) {
        idx = 5;
    }
    if (amber_crt && idx == 1) {
        return pack_rgb(c, 255, 224, 140);
    }
    if (amber_crt) {
        uint8_t r = PAL_RGB[idx][0];
        uint8_t g = PAL_RGB[idx][1];
        uint8_t b = PAL_RGB[idx][2];
        int lum = (r * 77 + g * 150 + b * 29) >> 8;
        if (lum < 150) {
            r = (uint8_t)ZOE_MIN(255, (int)r + 95);
            g = (uint8_t)ZOE_MIN(255, (int)g + 85);
            b = (uint8_t)ZOE_MIN(255, (int)b + 45);
        }
        return pack_rgb(c, r, g, b);
    }
    return pack_rgb(c, PAL_RGB[idx][0], PAL_RGB[idx][1], PAL_RGB[idx][2]);
}

static inline void put_px(Canvas *c, int x, int y, uint32_t col) {
    if (x >= 0 && x < c->w && y >= 0 && y < c->h) {
        c->pix[y * c->stride + x] = col;
    }
}

static void fill_rect(Canvas *c, int x, int y, int w, int h, uint32_t col) {
    if (w <= 0 || h <= 0) {
        return;
    }
    int x0 = x < 0 ? 0 : x;
    int y0 = y < 0 ? 0 : y;
    int x1 = (x + w) > c->w ? c->w : (x + w);
    int y1 = (y + h) > c->h ? c->h : (y + h);
    for (int py = y0; py < y1; py++) {
        uint32_t *row = c->pix + py * c->stride;
        for (int px = x0; px < x1; px++) {
            row[px] = col;
        }
    }
}

static void draw_rect(Canvas *c, int x, int y, int w, int h, uint32_t col, int t) {
    if (w <= 0 || h <= 0 || t <= 0) {
        return;
    }
    fill_rect(c, x, y, w, t, col);
    fill_rect(c, x, y + h - t, w, t, col);
    fill_rect(c, x, y, t, h, col);
    fill_rect(c, x + w - t, y, t, h, col);
}

static void draw_line(Canvas *c, int x0, int y0, int x1, int y1, uint32_t col, int thick) {
    int dx = abs(x1 - x0);
    int sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0);
    int sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    for (;;) {
        if (thick <= 1) {
            put_px(c, x0, y0, col);
        } else {
            fill_rect(c, x0 - thick / 2, y0 - thick / 2, thick, thick, col);
        }
        if (x0 == x1 && y0 == y1) {
            break;
        }
        int e2 = 2 * err;
        if (e2 >= dy) {
            err += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            err += dx;
            y0 += sy;
        }
    }
}

static void fill_tri(Canvas *c, int x0, int y0, int x1, int y1, int x2, int y2, uint32_t col) {
    int minx = x0 < x1 ? (x0 < x2 ? x0 : x2) : (x1 < x2 ? x1 : x2);
    int maxx = x0 > x1 ? (x0 > x2 ? x0 : x2) : (x1 > x2 ? x1 : x2);
    int miny = y0 < y1 ? (y0 < y2 ? y0 : y2) : (y1 < y2 ? y1 : y2);
    int maxy = y0 > y1 ? (y0 > y2 ? y0 : y2) : (y1 > y2 ? y1 : y2);
    if (minx < 0) {
        minx = 0;
    }
    if (miny < 0) {
        miny = 0;
    }
    if (maxx >= c->w) {
        maxx = c->w - 1;
    }
    if (maxy >= c->h) {
        maxy = c->h - 1;
    }
    for (int py = miny; py <= maxy; py++) {
        for (int px = minx; px <= maxx; px++) {
            int w0 = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0);
            int w1 = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1);
            int w2 = (x0 - x2) * (py - y2) - (y0 - y2) * (px - x2);
            if ((w0 >= 0 && w1 >= 0 && w2 >= 0) || (w0 <= 0 && w1 <= 0 && w2 <= 0)) {
                put_px(c, px, py, col);
            }
        }
    }
}

static void draw_text(Canvas *c, int x, int y, const char *s, uint32_t col, int scale) {
    if (!s || scale <= 0) {
        return;
    }
    int cx = x;
    for (; *s; s++) {
        unsigned char ch = (unsigned char)*s;
        if (ch < 32 || ch > 126) {
            ch = '?';
        }
        const uint8_t *glyph = FONT5X7[ch - 32];
        for (int row = 0; row < 7; row++) {
            uint8_t bits = glyph[row];
            for (int col_i = 0; col_i < 5; col_i++) {
                if ((bits >> (4 - col_i)) & 1) {
                    fill_rect(c, cx + col_i * scale, y + row * scale, scale, scale, col);
                }
            }
        }
        cx += 6 * scale;
    }
}

static void draw_text_clipped(Canvas *c, int x, int y, const char *s, uint32_t col, int scale, int max_w) {
    if (!s || max_w <= 0 || scale <= 0) {
        return;
    }
    int adv = 6 * scale;
    int max_ch = max_w / adv;
    if (max_ch <= 0) {
        return;
    }
    size_t len = strlen(s);
    if ((int)len <= max_ch) {
        draw_text(c, x, y, s, col, scale);
        return;
    }
    char buf[256];
    int cap = ZOE_MIN(max_ch, (int)sizeof(buf) - 1);
    if (cap >= 4) {
        int keep = cap - 2;
        memcpy(buf, s, (size_t)keep);
        buf[keep] = '.';
        buf[keep + 1] = '.';
        buf[keep + 2] = 0;
    } else {
        memcpy(buf, s, (size_t)cap);
        buf[cap] = 0;
    }
    draw_text(c, x, y, buf, col, scale);
}

static void draw_text_tail(Canvas *c, int x, int y, const char *s, uint32_t col, int scale, int max_w) {
    if (!s || max_w <= 0 || scale <= 0) {
        return;
    }
    int adv = 6 * scale;
    int max_ch = max_w / adv;
    if (max_ch <= 0) {
        return;
    }
    size_t len = strlen(s);
    if ((int)len <= max_ch) {
        draw_text(c, x, y, s, col, scale);
        return;
    }
    const char *tail = s + (len - (size_t)max_ch);
    draw_text(c, x, y, tail, col, scale);
}

static const GemTheme SOVEREIGN_THEMES[SOVEREIGN_THEME_COUNT] = {
    {
        "classic", "VIEWMAX/3 SOVEREIGN",
        {202, 208, 218}, {224, 228, 235}, 0,
        {250, 248, 242}, {18, 22, 30}, {52, 58, 72}, {80, 90, 110},
        {247, 202, 62}, {18, 22, 30}, {210, 216, 228}, {18, 22, 30},
        {254, 252, 247}, {148, 154, 168},
        {246, 244, 238}, {18, 22, 30},
        {230, 57, 86}, {92, 225, 230},
        {15, 16, 32}, {247, 242, 228},
        {255, 250, 236}, {15, 16, 32}, {247, 242, 228},
    },
    {
        "gemma", "GEM/3 SWISS DRAFTING",
        {214, 220, 230}, {234, 238, 244}, 1,
        {255, 255, 255}, {20, 24, 34}, {66, 74, 92}, {92, 100, 120},
        {200, 30, 58}, {255, 255, 255}, {222, 228, 238}, {20, 24, 34},
        {252, 253, 255}, {156, 164, 180},
        {248, 250, 252}, {20, 24, 34},
        {200, 30, 58}, {37, 99, 235},
        {20, 26, 42}, {250, 250, 252},
        {244, 247, 252}, {20, 24, 34}, {248, 250, 252},
    },
    {
        "atari", "TOSI ATARI ST EMERALD",
        {0, 122, 68}, {0, 146, 82}, 0,
        {248, 250, 245}, {14, 26, 20}, {6, 58, 34}, {56, 86, 70},
        {245, 158, 11}, {14, 26, 20}, {198, 232, 212}, {14, 26, 20},
        {251, 255, 252}, {122, 158, 138},
        {242, 248, 244}, {14, 26, 20},
        {217, 80, 24}, {0, 168, 107},
        {10, 34, 24}, {244, 250, 240},
        {236, 248, 238}, {8, 32, 22}, {242, 250, 242},
    },
    {
        "mono", "MONO SM124 1-BIT HI-RES",
        {42, 42, 42}, {238, 238, 234}, 0,
        {250, 250, 246}, {14, 14, 14}, {24, 24, 24}, {68, 68, 68},
        {14, 14, 14}, {250, 250, 246}, {218, 218, 212}, {14, 14, 14},
        {254, 253, 249}, {120, 120, 120},
        {244, 244, 240}, {14, 14, 14},
        {18, 18, 18}, {80, 80, 80},
        {14, 14, 14}, {250, 250, 246},
        {238, 238, 232}, {14, 14, 14}, {250, 250, 246},
    },
    {
        "cyan", "TETRA GEM/2 SPLIT CYAN",
        {12, 58, 72}, {18, 78, 94}, 1,
        {238, 249, 252}, {10, 34, 42}, {6, 32, 40}, {48, 92, 108},
        {34, 211, 238}, {6, 32, 40}, {186, 232, 242}, {10, 34, 42},
        {248, 253, 255}, {110, 164, 178},
        {228, 246, 250}, {10, 34, 42},
        {2, 132, 199}, {6, 182, 212},
        {7, 28, 36}, {234, 250, 254},
        {220, 244, 250}, {6, 26, 34}, {234, 250, 254},
    },
    {
        "p31", "ELIZA P31 GREEN x MAGENTA",
        {4, 10, 6}, {12, 32, 18}, 1,
        {8, 18, 12}, {56, 255, 122}, {2, 6, 3}, {34, 172, 86},
        {255, 46, 230}, {8, 14, 10}, {16, 44, 26}, {56, 255, 122},
        {46, 214, 104}, {4, 10, 6},
        {6, 16, 10}, {56, 255, 122},
        {255, 46, 230}, {88, 166, 255},
        {4, 10, 6}, {56, 255, 122},
        {12, 28, 18}, {4, 10, 6}, {56, 255, 122},
    },
    {
        "sage", "SAGE GEM/4 ILLUMINATED",
        {26, 36, 56}, {36, 48, 72}, 3,
        {247, 241, 225}, {26, 29, 42}, {12, 18, 30}, {92, 88, 76},
        {234, 179, 8}, {26, 29, 42}, {222, 212, 188}, {26, 29, 42},
        {255, 252, 242}, {154, 144, 122},
        {242, 235, 216}, {26, 29, 42},
        {180, 83, 9}, {37, 99, 235},
        {20, 27, 45}, {248, 242, 226},
        {255, 248, 230}, {18, 24, 40}, {248, 242, 226},
    },
    {
        "flora", "FLORA STOWERS 650NM RED",
        {18, 8, 12}, {28, 12, 18}, 2,
        {26, 12, 18}, {246, 194, 206}, {8, 3, 5}, {178, 114, 130},
        {164, 20, 62}, {255, 240, 244}, {54, 20, 32}, {232, 168, 184},
        {120, 38, 64}, {10, 4, 6},
        {22, 10, 15}, {246, 194, 206},
        {94, 242, 160}, {56, 189, 248},
        {14, 6, 9}, {248, 206, 216},
        {38, 16, 25}, {16, 6, 10}, {246, 194, 206},
    },
    {
        "lumen", "LUMEN VIEWMAX/2 PRISM",
        {20, 16, 44}, {32, 24, 68}, 1,
        {246, 244, 255}, {26, 20, 52}, {12, 8, 32}, {94, 84, 136},
        {124, 58, 237}, {255, 255, 255}, {221, 214, 254}, {26, 20, 52},
        {253, 251, 255}, {154, 144, 198},
        {240, 236, 254}, {26, 20, 52},
        {217, 70, 239}, {6, 182, 212},
        {18, 13, 38}, {246, 242, 255},
        {236, 232, 254}, {18, 13, 38}, {246, 242, 255},
    },
    {
        "beos", "BEOS R5 GOLDEN TAB",
        {51, 102, 152}, {58, 110, 162}, 2,
        {232, 232, 232}, {20, 20, 20}, {24, 52, 80}, {78, 78, 78},
        {255, 208, 56}, {20, 20, 20}, {200, 200, 200}, {36, 36, 36},
        {254, 253, 250}, {132, 132, 132},
        {220, 220, 220}, {20, 20, 20},
        {217, 119, 6}, {37, 99, 235},
        {22, 32, 48}, {246, 244, 236},
        {246, 242, 224}, {32, 38, 50}, {246, 244, 236},
    },
};

static inline uint32_t pack_c(const Canvas *c, Rgb col) {
    return pack_rgb(c, col.r, col.g, col.b);
}

static inline const GemTheme *active_theme(const DesktopApp *app) {
    int idx = app ? app->theme_idx : 0;
    if (idx < 0 || idx >= SOVEREIGN_THEME_COUNT) {
        idx = 0;
    }
    return &SOVEREIGN_THEMES[idx];
}

static inline int is_dark_theme(const GemTheme *th) {
    return ((int)th->win_bg.r + (int)th->win_bg.g + (int)th->win_bg.b) < 320;
}

static inline uint32_t theme_ok_green(const Canvas *c, const GemTheme *th) {
    return is_dark_theme(th) ? pack_rgb(c, 74, 248, 138) : pack_rgb(c, 22, 148, 78);
}

static inline uint32_t theme_warn_amber(const Canvas *c, const GemTheme *th) {
    return is_dark_theme(th) ? pack_rgb(c, 255, 196, 46) : pack_rgb(c, 208, 128, 10);
}

static inline uint32_t theme_err_red(const Canvas *c, const GemTheme *th) {
    return is_dark_theme(th) ? pack_rgb(c, 255, 92, 138) : pack_rgb(c, 230, 57, 86);
}

static int eq_ci(const char *a, const char *b) {
    if (!a || !b) {
        return 0;
    }
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) {
            return 0;
        }
        a++;
        b++;
    }
    return *a == 0 && *b == 0;
}

static int resolve_theme_arg(const char *s) {
    if (!s || !s[0]) {
        return -1;
    }
    if (s[0] >= '0' && s[0] <= '9' && s[1] == 0) {
        return s[0] - '0';
    }
    for (int i = 0; i < SOVEREIGN_THEME_COUNT; i++) {
        if (eq_ci(s, SOVEREIGN_THEMES[i].key)) {
            return i;
        }
    }
    if (eq_ci(s, "viewmax") || eq_ci(s, "viewmax3") || eq_ci(s, "gem") ||
        eq_ci(s, "sovereign") || eq_ci(s, "default")) {
        return 0;
    }
    if (eq_ci(s, "gem3") || eq_ci(s, "swiss")) {
        return 1;
    }
    if (eq_ci(s, "tosi") || eq_ci(s, "emerald") || eq_ci(s, "st")) {
        return 2;
    }
    if (eq_ci(s, "sm124") || eq_ci(s, "1bit") || eq_ci(s, "apricot")) {
        return 3;
    }
    if (eq_ci(s, "tetra") || eq_ci(s, "gem2")) {
        return 4;
    }
    if (eq_ci(s, "eliza") || eq_ci(s, "green") || eq_ci(s, "magenta") ||
        eq_ci(s, "hacker") || eq_ci(s, "dos")) {
        return 5;
    }
    if (eq_ci(s, "gem4") || eq_ci(s, "study") || eq_ci(s, "navy")) {
        return 6;
    }
    if (eq_ci(s, "darkroom") || eq_ci(s, "650nm") || eq_ci(s, "stowers") || eq_ci(s, "red")) {
        return 7;
    }
    if (eq_ci(s, "prism") || eq_ci(s, "viewmax2") || eq_ci(s, "violet")) {
        return 8;
    }
    if (eq_ci(s, "gold") || eq_ci(s, "golden") || eq_ci(s, "yellow") || eq_ci(s, "r5")) {
        return 9;
    }
    return -1;
}

static void cycle_sovereign_theme(DesktopApp *app) {
    app->theme_idx = (app->theme_idx + 1) % SOVEREIGN_THEME_COUNT;
    app->bg_dirty = 1;
    const GemTheme *th = active_theme(app);
    snprintf(app->status_msg, sizeof(app->status_msg),
             "VMCOLOUR [%02d/10]: %s ([V] NEXT, [A] AMBER)",
             app->theme_idx + 1, th->name);
}

static void draw_bevel_box(Canvas *c, const GemTheme *th, int x, int y, int w, int h,
                           uint32_t fill, uint32_t border, int pressed) {
    if (w <= 0 || h <= 0) {
        return;
    }
    uint32_t hi = pack_c(c, pressed ? th->bevel_lo : th->bevel_hi);
    uint32_t lo = pack_c(c, pressed ? th->bevel_hi : th->bevel_lo);
    fill_rect(c, x, y, w, h, fill);
    draw_rect(c, x, y, w, h, border, 1);
    if (w >= 4 && h >= 4) {
        fill_rect(c, x + 1, y + 1, w - 2, 1, hi);
        fill_rect(c, x + 1, y + 1, 1, h - 2, hi);
        fill_rect(c, x + 1, y + h - 2, w - 2, 1, lo);
        fill_rect(c, x + w - 2, y + 1, 1, h - 2, lo);
    }
}

static void draw_zoe_flower_mini(Canvas *c, int cx, int cy, int r, uint32_t fg) {
    if (r < 3) {
        return;
    }
    /* Minimalist 4-stroke Zoe flower-smile-voice icon */
    draw_line(c, cx, cy - r / 5, cx, cy + r, fg, 1);
    draw_line(c, cx - (r * 2) / 3, cy - (r * 2) / 3, cx, cy - r / 5, fg, 1);
    draw_line(c, cx + (r * 2) / 3, cy - (r * 2) / 3, cx, cy - r / 5, fg, 1);
    fill_rect(c, cx - 1, cy - (r * 4) / 5, 3, 2, fg);
    draw_line(c, cx, cy + r / 2, cx - (r * 3) / 5, cy + r / 6, fg, 1);
    draw_line(c, cx, cy + r / 2, cx + (r * 3) / 5, cy + r / 6, fg, 1);
}

static void draw_nick_florette_mini(Canvas *c, int cx, int cy, int r, uint32_t petal_col, uint32_t core_col) {
    if (r < 4) {
        return;
    }
    /* 5-petal White Florette + center diamond */
    for (int i = 0; i < 5; i++) {
        double ang = -1.5707963267948966 + 2.0 * 3.14159265358979323846 * i / 5.0;
        int px = cx + (int)(cos(ang) * (r * 0.62));
        int py = cy + (int)(sin(ang) * (r * 0.62));
        int pr = ZOE_MAX(2, r / 3);
        fill_rect(c, px - pr / 2, py - pr / 2, pr, pr, petal_col);
    }
    fill_rect(c, cx - 1, cy - 1, 3, 3, core_col);
}

static void draw_gem_window_themed(Canvas *c, const GemTheme *th, int x, int y, int w, int h,
                                   const char *title, int active, int compact) {
    if (w < 64) {
        w = 64;
    }
    if (h < 32) {
        h = 32;
    }
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t win_bg = pack_c(c, th->win_bg);
    uint32_t shadow = pack_c(c, th->win_shadow);
    uint32_t tab_bg = pack_c(c, active ? th->tab_act_bg : th->tab_inact_bg);
    uint32_t tab_fg = pack_c(c, active ? th->tab_act_fg : th->tab_inact_fg);
    uint32_t hi = pack_c(c, th->bevel_hi);
    uint32_t lo = pack_c(c, th->bevel_lo);
    int tbh = compact ? 20 : 26;
    int btn = compact ? 12 : 16;
    int pad = compact ? 4 : 5;
    int sh_off = compact ? 4 : 6;

    /* BeOS compact colored tab sizing: only as wide as title + gadgets need */
    int max_tab_w = w;
    int len = (int)strlen(title);
    int chrome = 2 * (pad + btn + 6);
    int ts = (!compact && len * 12 + chrome <= w - 42) ? 2 : 1;
    int want_tab_w = len * 6 * ts + chrome + 4;
    int min_tab_w = ZOE_MIN(w, compact ? 96 : 136);
    int tab_w = ZOE_CLAMP(want_tab_w, min_tab_w, max_tab_w);
    if (w - tab_w < 18) {
        tab_w = w;
    }

    /* Drop shadow for sculpted BeOS tab + window body */
    fill_rect(c, x + sh_off, y + tbh + sh_off, w, h - tbh, shadow);
    fill_rect(c, x + sh_off, y + sh_off, tab_w, tbh, shadow);

    /* Window body with ViewMAX/3 DRAW3D inner highlight/shadow bevel */
    fill_rect(c, x, y + tbh, w, h - tbh, win_bg);
    draw_rect(c, x, y + tbh, w, h - tbh, ink, 2);
    if (w >= 10 && h - tbh >= 10) {
        fill_rect(c, x + 2, y + tbh + 2, w - 4, 1, hi);
        fill_rect(c, x + 2, y + tbh + 2, 1, h - tbh - 4, hi);
        fill_rect(c, x + 2, y + h - 3, w - 4, 1, lo);
        fill_rect(c, x + w - 3, y + tbh + 2, 1, h - tbh - 4, lo);
    }

    /* Sculpted BeOS window tab joined cleanly onto top edge */
    fill_rect(c, x, y, tab_w, tbh + 1, tab_bg);
    fill_rect(c, x, y, tab_w, 2, ink);
    fill_rect(c, x, y, 2, tbh + 2, ink);
    fill_rect(c, x + tab_w - 2, y, 2, tbh + 2, ink);
    fill_rect(c, x + 2, y + 2, tab_w - 4, 1, hi);
    fill_rect(c, x + 2, y + 2, 1, tbh - 2, hi);
    fill_rect(c, x + tab_w - 3, y + 2, 1, tbh - 2, lo);
    fill_rect(c, x + 2, y + tbh, tab_w - 4, 1, ink);

    /* Close gadget (left) with ViewMAX/3 3D bevel */
    draw_bevel_box(c, th, x + pad, y + pad, btn, btn, win_bg, ink, 0);
    draw_line(c, x + pad + 3, y + pad + 3, x + pad + btn - 4, y + pad + btn - 4, ink, 1);
    draw_line(c, x + pad + btn - 4, y + pad + 3, x + pad + 3, y + pad + btn - 4, ink, 1);

    /* Zoom gadget (right of tab) with ViewMAX/3 3D bevel */
    int zx = x + tab_w - pad - btn;
    draw_bevel_box(c, th, zx, y + pad, btn, btn, win_bg, ink, 0);
    if (btn >= 12) {
        draw_rect(c, zx + 4, y + pad + 4, btn - 8, btn - 8, ink, 1);
    }

    int tx = x + pad + btn + 6;
    int avail = tab_w - 2 * (pad + btn + 6);
    int ty = y + (tbh - 7 * ts) / 2;
    draw_text_clipped(c, tx, ty, title, tab_fg, ts, avail);
}

static void draw_zoe_ruby(Canvas *c, int cx, int cy, int r) {
    uint32_t dark = pack_rgb(c, 18, 20, 32);
    uint32_t ruby_hi = pack_rgb(c, 255, 118, 146);
    uint32_t ruby_mid = pack_rgb(c, 230, 57, 86);
    uint32_t ruby_deep = pack_rgb(c, 152, 22, 54);
    uint32_t cream = pack_rgb(c, 248, 244, 234);
    int xL = cx - r, xR = cx + r;
    int xTL = cx - (r * 58) / 100, xTR = cx + (r * 58) / 100;
    int yTop = cy - (r * 76) / 100, yBelt = cy - (r * 12) / 100, yBot = cy + (r * 92) / 100;
    int yTab = cy - (r * 44) / 100;
    fill_tri(c, xTL, yTop, xTR, yTop, cx, yTab, ruby_hi);
    fill_tri(c, xL, yBelt, xTL, yTop, cx, yTab, ruby_mid);
    fill_tri(c, xR, yBelt, xTR, yTop, cx, yTab, ruby_deep);
    fill_tri(c, xL, yBelt, cx, yTab, xR, yBelt, ruby_mid);
    fill_tri(c, xL, yBelt, cx, yBot, cx, yBelt, ruby_mid);
    fill_tri(c, xR, yBelt, cx, yBot, cx, yBelt, ruby_deep);
    draw_line(c, xTL, yTop, xTR, yTop, dark, 2);
    draw_line(c, xTR, yTop, xR, yBelt, dark, 2);
    draw_line(c, xR, yBelt, cx, yBot, dark, 2);
    draw_line(c, cx, yBot, xL, yBelt, dark, 2);
    draw_line(c, xL, yBelt, xTL, yTop, dark, 2);
    draw_line(c, xL, yBelt, xR, yBelt, dark, 1);

    int ey = yBelt + (r * 14) / 100;
    int ex = (r * 28) / 100;
    int ew = ZOE_MAX(3, (r * 16) / 100);
    int eh = ZOE_MAX(2, (r * 11) / 100);
    int em = ZOE_MAX(1, (r * 7) / 100);
    int ft = (r <= 20) ? 1 : 2;
    draw_line(c, cx - ex - ew, ey, cx - ex - em, ey - eh, cream, ft);
    draw_line(c, cx - ex - em, ey - eh, cx - ex + em, ey - eh, cream, ft);
    draw_line(c, cx - ex + em, ey - eh, cx - ex + ew, ey, cream, ft);
    draw_line(c, cx + ex - ew, ey, cx + ex - em, ey - eh, cream, ft);
    draw_line(c, cx + ex - em, ey - eh, cx + ex + em, ey - eh, cream, ft);
    draw_line(c, cx + ex + em, ey - eh, cx + ex + ew, ey, cream, ft);

    int my = ey + (r * 18) / 100;
    int mw = ZOE_MAX(3, (r * 18) / 100);
    int mm = ZOE_MAX(1, (r * 7) / 100);
    draw_line(c, cx - mw, my - 2, cx - mm, my + 2, cream, ft);
    draw_line(c, cx - mm, my + 2, cx + mm, my + 2, cream, ft);
    draw_line(c, cx + mm, my + 2, cx + mw, my - 2, cream, ft);
}

static void draw_cursor_oriented(Canvas *c, int mx, int my, uint32_t accent, int amber_crt, int orient_rot) {
    uint32_t ink = amber_crt ? pack_rgb(c, 8, 4, 0) : pack_rgb(c, 12, 14, 22);
    uint32_t fg = amber_crt ? pack_rgb(c, 255, 248, 220) : accent;
    for (int r = 0; r < 16; r++) {
        for (int col = 0; col < 16; col++) {
            char ch = ZOE_CURSOR[r][col];
            if (ch != 'X' && ch != 'O') {
                continue;
            }
            int px = orient_rot ? (mx + r) : (mx + col);
            int py = orient_rot ? (my - col) : (my + r);
            put_px(c, px, py, (ch == 'X') ? ink : fg);
        }
    }
}

static void draw_cursor(Canvas *c, int mx, int my, uint32_t accent, int amber_crt) {
    draw_cursor_oriented(c, mx, my, accent, amber_crt, 0);
}

/* ---------------- Depth-Aware JSON Scanner & Escaper ---------------- */

static const char *skip_json_ws(const char *p) {
    while (p && (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')) {
        p++;
    }
    return p;
}

static int hex_val(char c) {
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f') {
        return 10 + (c - 'a');
    }
    if (c >= 'A' && c <= 'F') {
        return 10 + (c - 'A');
    }
    return -1;
}

static const char *parse_json_quoted(const char *p, char *out, size_t cap, int store) {
    if (!p || *p != '"') {
        if (store && out && cap > 0) {
            out[0] = 0;
        }
        return p;
    }
    p++;
    size_t i = 0;
    while (*p && *p != '"') {
        unsigned char c = (unsigned char)*p;
        if (c == '\\' && p[1]) {
            p++;
            char esc = *p;
            char decoded = esc;
            if (esc == 'n') {
                decoded = '\n';
            } else if (esc == 'r') {
                decoded = '\r';
            } else if (esc == 't') {
                decoded = '\t';
            } else if (esc == 'b') {
                decoded = '\b';
            } else if (esc == 'f') {
                decoded = '\f';
            } else if (esc == 'u' && p[1] && p[2] && p[3] && p[4]) {
                int h0 = hex_val(p[1]), h1 = hex_val(p[2]), h2 = hex_val(p[3]), h3 = hex_val(p[4]);
                if (h0 >= 0 && h1 >= 0 && h2 >= 0 && h3 >= 0) {
                    int cp = (h0 << 12) | (h1 << 8) | (h2 << 4) | h3;
                    decoded = (cp >= 32 && cp <= 126) ? (char)cp : '?';
                    p += 4;
                }
            }
            if (store && out && i + 1 < cap) {
                out[i++] = decoded;
            }
            p++;
        } else {
            if (store && out && i + 1 < cap) {
                out[i++] = (char)c;
            }
            p++;
        }
    }
    if (*p == '"') {
        p++;
    }
    if (store && out && cap > 0) {
        out[i] = 0;
    }
    return p;
}

static const char *skip_json_value(const char *p) {
    p = skip_json_ws(p);
    if (!p || !*p) {
        return p;
    }
    if (*p == '"') {
        return parse_json_quoted(p, NULL, 0, 0);
    }
    if (*p == '{' || *p == '[') {
        int depth = 0;
        while (*p) {
            if (*p == '"') {
                p = parse_json_quoted(p, NULL, 0, 0);
                continue;
            }
            if (*p == '{' || *p == '[') {
                depth++;
            } else if (*p == '}' || *p == ']') {
                depth--;
                p++;
                if (depth <= 0) {
                    break;
                }
                continue;
            }
            p++;
        }
        return p;
    }
    while (*p && *p != ',' && *p != '}' && *p != ']' && !isspace((unsigned char)*p)) {
        p++;
    }
    return p;
}

static const char *find_json_key_val_ptr(const char *obj_buf, const char *key) {
    if (!obj_buf || !key) {
        return NULL;
    }
    const char *p = skip_json_ws(obj_buf);
    if (*p != '{') {
        return NULL;
    }
    p++;
    while (*p) {
        p = skip_json_ws(p);
        if (*p == '}') {
            return NULL;
        }
        if (*p == ',') {
            p++;
            continue;
        }
        if (*p != '"') {
            p = skip_json_value(p);
            continue;
        }
        char kbuf[96];
        p = parse_json_quoted(p, kbuf, sizeof(kbuf), 1);
        p = skip_json_ws(p);
        if (*p != ':') {
            continue;
        }
        p = skip_json_ws(p + 1);
        if (strcmp(kbuf, key) == 0) {
            return p;
        }
        p = skip_json_value(p);
    }
    return NULL;
}

static int extract_json_scalar(const char *p, char *out, size_t cap) {
    if (!p || !out || cap == 0) {
        return 0;
    }
    p = skip_json_ws(p);
    if (!*p) {
        return 0;
    }
    if (*p == '"') {
        parse_json_quoted(p, out, cap, 1);
        return 1;
    }
    if (*p == '{' || *p == '[') {
        return 0;
    }
    size_t i = 0;
    while (*p && *p != ',' && *p != '}' && *p != ']' && !isspace((unsigned char)*p) && i + 1 < cap) {
        out[i++] = *p++;
    }
    out[i] = 0;
    return i > 0 ? 1 : 0;
}

static int parse_json_key_in_obj(const char *obj_buf, const char *key, char *out, size_t cap) {
    const char *vp = find_json_key_val_ptr(obj_buf, key);
    if (!vp) {
        return 0;
    }
    return extract_json_scalar(vp, out, cap);
}

static int parse_json_path(const char *buf, const char *k1, const char *k2, const char *k3, char *out, size_t cap) {
    const char *vp = find_json_key_val_ptr(buf, k1);
    if (!vp) {
        return 0;
    }
    if (!k2) {
        return extract_json_scalar(vp, out, cap);
    }
    vp = skip_json_ws(vp);
    if (*vp != '{') {
        return 0;
    }
    vp = find_json_key_val_ptr(vp, k2);
    if (!vp) {
        return 0;
    }
    if (!k3) {
        return extract_json_scalar(vp, out, cap);
    }
    vp = skip_json_ws(vp);
    if (*vp != '{') {
        return 0;
    }
    vp = find_json_key_val_ptr(vp, k3);
    if (!vp) {
        return 0;
    }
    return extract_json_scalar(vp, out, cap);
}

static void json_escape(const char *src, char *dst, size_t cap) {
    size_t k = 0;
    if (!src || !dst || cap == 0) {
        return;
    }
    for (size_t i = 0; src[i] && k + 3 < cap; i++) {
        unsigned char c = (unsigned char)src[i];
        if (c == '"') {
            dst[k++] = '\\';
            dst[k++] = '"';
        } else if (c == '\\') {
            dst[k++] = '\\';
            dst[k++] = '\\';
        } else if (c == '\n') {
            dst[k++] = '\\';
            dst[k++] = 'n';
        } else if (c == '\r') {
            dst[k++] = '\\';
            dst[k++] = 'r';
        } else if (c == '\t') {
            dst[k++] = '\\';
            dst[k++] = 't';
        } else if (c < 0x20 || c == 0x7f) {
            continue;
        } else {
            dst[k++] = (char)c;
        }
    }
    dst[k] = 0;
}

/* ---------------- Bounded File Readers & State Lock Helpers ---------------- */

static char *read_fd_alloc_bounded(int fd, size_t max_bytes, size_t *out_len) {
    struct stat sb;
    if (fstat(fd, &sb) == 0 && sb.st_size > 0) {
        size_t target = (size_t)sb.st_size;
        if (target > max_bytes) {
            target = max_bytes;
        }
        char *buf = (char *)malloc(target + 1);
        if (!buf) {
            return NULL;
        }
        size_t n = 0;
        while (n < target) {
            ssize_t r = read(fd, buf + n, target - n);
            if (r < 0) {
                if (errno == EINTR) {
                    continue;
                }
                break;
            }
            if (r == 0) {
                break;
            }
            n += (size_t)r;
        }
        buf[n] = 0;
        if (out_len) {
            *out_len = n;
        }
        return buf;
    }
    size_t cap = 4096;
    if (cap > max_bytes) {
        cap = max_bytes;
    }
    char *buf = (char *)malloc(cap + 1);
    if (!buf) {
        return NULL;
    }
    size_t n = 0;
    for (;;) {
        if (n >= max_bytes) {
            break;
        }
        if (n == cap) {
            size_t next_cap = cap * 2;
            if (next_cap > max_bytes) {
                next_cap = max_bytes;
            }
            if (next_cap <= cap) {
                break;
            }
            char *nb = (char *)realloc(buf, next_cap + 1);
            if (!nb) {
                break;
            }
            buf = nb;
            cap = next_cap;
        }
        ssize_t r = read(fd, buf + n, cap - n);
        if (r < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }
        if (r == 0) {
            break;
        }
        n += (size_t)r;
    }
    buf[n] = 0;
    if (out_len) {
        *out_len = n;
    }
    return buf;
}

static char *read_file_alloc_bounded(const char *path, size_t max_bytes, size_t *out_len) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        return NULL;
    }
    char *buf = read_fd_alloc_bounded(fd, max_bytes, out_len);
    close(fd);
    return buf;
}

static void derive_state_lock_path(const char *path, char *out, size_t cap) {
    if (!out || cap == 0) {
        return;
    }
    const char *slash = path ? strrchr(path, '/') : NULL;
    const char *suffix = "/.state.lock";
    size_t slen = strlen(suffix);
    if (!slash) {
        snprintf(out, cap, "%s", ".state.lock");
        return;
    }
    size_t dir_len = (size_t)(slash - path);
    if (dir_len == 0) {
        snprintf(out, cap, "%s", "/.state.lock");
        return;
    }
    if (dir_len + slen + 1 > cap) {
        dir_len = (cap > slen + 1) ? (cap - slen - 1) : 0;
    }
    memcpy(out, path, dir_len);
    memcpy(out + dir_len, suffix, slen + 1);
}

static int acquire_state_lock(const char *target_path, int shared) {
    char lock_path[PATH_MAX];
    derive_state_lock_path(target_path, lock_path, sizeof(lock_path));
    int fd = open(lock_path, O_RDWR | O_CREAT, 0644);
    if (fd >= 0) {
        flock(fd, shared ? LOCK_SH : LOCK_EX);
    }
    return fd;
}

static void release_state_lock(int fd) {
    if (fd >= 0) {
        flock(fd, LOCK_UN);
        close(fd);
    }
}

/* ---------------- Drawer Notes & Artline SVG Persistence ---------------- */

static void load_drawer_notes_unlocked(DesktopApp *app, BootState *st, const char *path) {
    app->note_count = 0;
    char *buf = read_file_alloc_bounded(path, 4u * 1024u * 1024u, NULL);
    if (!buf) {
        return;
    }

    int total = 0;
    const char *p = skip_json_ws(buf);
    if (*p == '[') {
        p++;
        while (*p) {
            p = skip_json_ws(p);
            if (*p == ']') {
                break;
            }
            if (*p == ',') {
                p++;
                continue;
            }
            if (*p == '{') {
                DrawerNote dn;
                memset(&dn, 0, sizeof(dn));
                dn.boot = 1;
                snprintf(dn.author, sizeof(dn.author), "%s", "Nicholas");
                char bstr[16] = {0};
                if (parse_json_key_in_obj(p, "boot", bstr, sizeof(bstr))) {
                    int bv = atoi(bstr);
                    if (bv > 0) {
                        dn.boot = bv;
                    }
                }
                parse_json_key_in_obj(p, "author", dn.author, sizeof(dn.author));
                parse_json_key_in_obj(p, "text", dn.text, sizeof(dn.text));
                if (app->note_count < MAX_DRAWER_NOTES) {
                    app->notes[app->note_count++] = dn;
                } else {
                    memmove(&app->notes[0], &app->notes[1], sizeof(DrawerNote) * (MAX_DRAWER_NOTES - 1));
                    app->notes[MAX_DRAWER_NOTES - 1] = dn;
                }
                total++;
                p = skip_json_value(p);
            } else {
                p = skip_json_value(p);
            }
        }
    }
    free(buf);
    if (total > 0) {
        snprintf(st->drawer_count, sizeof(st->drawer_count), "%d", total);
        snprintf(st->drawer_latest, sizeof(st->drawer_latest), "%s", app->notes[app->note_count - 1].text);
    } else {
        snprintf(st->drawer_count, sizeof(st->drawer_count), "0");
        snprintf(st->drawer_latest, sizeof(st->drawer_latest), "%s", "(empty)");
    }
}

static void load_drawer_notes_path(DesktopApp *app, BootState *st, const char *path) {
    int lock_fd = acquire_state_lock(path, 1);
    load_drawer_notes_unlocked(app, st, path);
    release_state_lock(lock_fd);
}

static char *find_outer_json_array_end(char *buf) {
    if (!buf) {
        return NULL;
    }
    char *p = (char *)skip_json_ws(buf);
    if (*p != '[') {
        return NULL;
    }
    int depth = 1;
    int in_str = 0;
    p++;
    while (*p) {
        if (in_str) {
            if (*p == '\\' && p[1]) {
                p += 2;
                continue;
            }
            if (*p == '"') {
                in_str = 0;
            }
            p++;
            continue;
        }
        if (*p == '"') {
            in_str = 1;
            p++;
        } else if (*p == '[') {
            depth++;
            p++;
        } else if (*p == ']') {
            depth--;
            if (depth == 0) {
                return p;
            }
            p++;
        } else {
            p++;
        }
    }
    return NULL;
}

static void append_drawer_note_path(DesktopApp *app, BootState *st, const char *path, const char *text) {
    char esc[256];
    json_escape(text, esc, sizeof(esc));
    if (!esc[0]) {
        return;
    }
    int boot_num = atoi(st->boot_count);
    if (boot_num <= 0) {
        boot_num = 1;
    }

    int lock_fd = acquire_state_lock(path, 0);
    char *buf = read_file_alloc_bounded(path, 4u * 1024u * 1024u, NULL);
    if (!buf) {
        buf = (char *)calloc(1, 1);
        if (!buf) {
            release_state_lock(lock_fd);
            return;
        }
    }

    char *end = find_outer_json_array_end(buf);
    int has_items = 0;
    if (end) {
        char *scan = end - 1;
        while (scan >= buf && isspace((unsigned char)*scan)) {
            scan--;
        }
        if (scan >= buf && *scan != '[') {
            has_items = 1;
        }
        *end = 0;
    }

    char tmp_path[PATH_MAX + 64];
    snprintf(tmp_path, sizeof(tmp_path), "%s.tmp.%ld", path, (long)getpid());
    FILE *w = fopen(tmp_path, "w");
    if (w) {
        if (end && has_items) {
            fprintf(w, "%s,\n  {\"boot\": %d, \"author\": \"Nicholas\", \"text\": \"%s\"}\n]\n",
                    buf, boot_num, esc);
        } else {
            fprintf(w, "[\n  {\"boot\": %d, \"author\": \"Nicholas\", \"text\": \"%s\"}\n]\n",
                    boot_num, esc);
        }
        fflush(w);
        fsync(fileno(w));
        fclose(w);
        if (rename(tmp_path, path) != 0) {
            unlink(tmp_path);
        }
    }
    free(buf);
    load_drawer_notes_unlocked(app, st, path);
    release_state_lock(lock_fd);
}

static int find_svg_attr_range(const char *tag, const char *end, const char *attr,
                               const char **val_start, size_t *val_len) {
    if (!tag || !end || !attr || tag >= end) {
        return 0;
    }
    size_t attr_len = strlen(attr);
    const char *p = tag;
    if (*p == '<') {
        p++;
        while (p < end && !isspace((unsigned char)*p) && *p != '>' && *p != '/') {
            p++;
        }
    }
    while (p < end) {
        while (p < end && isspace((unsigned char)*p)) {
            p++;
        }
        if (p >= end || *p == '>' || *p == '/') {
            break;
        }
        const char *ns = p;
        while (p < end && !isspace((unsigned char)*p) && *p != '=' && *p != '>' && *p != '/') {
            p++;
        }
        size_t nl = (size_t)(p - ns);
        while (p < end && isspace((unsigned char)*p)) {
            p++;
        }
        if (p < end && *p == '=') {
            p++;
            while (p < end && isspace((unsigned char)*p)) {
                p++;
            }
            if (p < end && (*p == '"' || *p == '\'')) {
                char q = *p++;
                const char *vs = p;
                while (p < end && *p != q) {
                    p++;
                }
                size_t vl = (size_t)(p - vs);
                if (p < end && *p == q) {
                    p++;
                }
                if (nl == attr_len && strncmp(ns, attr, nl) == 0) {
                    *val_start = vs;
                    *val_len = vl;
                    return 1;
                }
            } else {
                while (p < end && !isspace((unsigned char)*p) && *p != '>' && *p != '/') {
                    p++;
                }
            }
        } else if (nl == 0) {
            p++;
        }
    }
    return 0;
}

static long long parse_svg_ll_attr_range(const char *tag, const char *end, const char *attr, long long def_val) {
    const char *vs = NULL;
    size_t vl = 0;
    if (!find_svg_attr_range(tag, end, attr, &vs, &vl) || vl == 0) {
        return def_val;
    }
    char num[48];
    size_t copy_n = ZOE_MIN(vl, sizeof(num) - 1);
    memcpy(num, vs, copy_n);
    num[copy_n] = 0;
    char *ep = NULL;
    long long v = strtoll(num, &ep, 10);
    if (ep == num) {
        return def_val;
    }
    return v;
}

static int parse_svg_str_attr_range(const char *tag, const char *end, const char *attr, char *out, size_t cap) {
    if (!out || cap == 0) {
        return 0;
    }
    out[0] = 0;
    const char *vs = NULL;
    size_t vl = 0;
    if (!find_svg_attr_range(tag, end, attr, &vs, &vl) || vl == 0) {
        return 0;
    }
    size_t copy_n = ZOE_MIN(vl, cap - 1);
    memcpy(out, vs, copy_n);
    out[copy_n] = 0;
    return copy_n > 0 ? 1 : 0;
}

static int color_idx_from_hex(const char *hex) {
    if (!hex || !hex[0]) {
        return 5;
    }
    for (int i = 0; i < 8; i++) {
        int match = 1;
        for (size_t k = 0; PAL_HEX[i][k] || hex[k]; k++) {
            if (tolower((unsigned char)PAL_HEX[i][k]) != tolower((unsigned char)hex[k])) {
                match = 0;
                break;
            }
        }
        if (match) {
            return i;
        }
    }
    return 5;
}

static void save_live_canvas_svg(const DesktopApp *app, const char *path) {
    char tmp_path[PATH_MAX + 64];
    snprintf(tmp_path, sizeof(tmp_path), "%s.tmp.%ld", path, (long)getpid());
    FILE *f = fopen(tmp_path, "w");
    if (!f) {
        f = fopen(path, "w");
        if (!f) {
            return;
        }
        tmp_path[0] = 0;
    }
    int vw = ZOE_MAX(1, app->vw);
    int vh = ZOE_MAX(1, app->vh);
    fprintf(f, "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"%d\" height=\"%d\" viewBox=\"0 0 %d %d\">\n",
            vw, vh, vw, vh);
    fprintf(f, "  <rect x=\"0\" y=\"0\" width=\"%d\" height=\"%d\" fill=\"#0f1020\"/>\n", vw, vh);
    fprintf(f, "  <line x1=\"%d\" y1=\"0\" x2=\"%d\" y2=\"%d\" stroke=\"#e63956\" stroke-dasharray=\"4 4\"/>\n",
            vw / 2, vw / 2, vh);
    for (int i = 0; i < app->stroke_count; i++) {
        const Stroke *sk = &app->strokes[i];
        int thick = (sk->thick >= 1 && sk->thick <= 5) ? sk->thick : 2;
        fprintf(f, "  <line x1=\"%d\" y1=\"%d\" x2=\"%d\" y2=\"%d\" stroke=\"%s\" stroke-width=\"%d\"/>\n",
                sk->x0, sk->y0, sk->x1, sk->y1, PAL_HEX[sk->color_idx & 7], thick);
    }
    fprintf(f, "</svg>\n");
    fflush(f);
    fsync(fileno(f));
    fclose(f);
    if (tmp_path[0]) {
        if (rename(tmp_path, path) != 0) {
            unlink(tmp_path);
        }
    }
}

static int clamp_svg_coord(long long raw, long long svg_dim, int dst_dim) {
    if (dst_dim <= 1) {
        return 0;
    }
    double val = (svg_dim > 0 && svg_dim != dst_dim)
        ? ((double)raw * (double)dst_dim / (double)svg_dim)
        : (double)raw;
    if (val < 0.0) {
        return 0;
    }
    if (val > (double)(dst_dim - 1)) {
        return dst_dim - 1;
    }
    return (int)val;
}

static void load_live_canvas_svg(DesktopApp *app, const char *path) {
    char *buf = read_file_alloc_bounded(path, 4u * 1024u * 1024u, NULL);
    if (!buf) {
        return;
    }
    long long svg_w = 0, svg_h = 0;
    const char *p = buf;
    while ((p = strchr(p, '<')) != NULL) {
        const char *gt = strchr(p, '>');
        if (!gt) {
            break;
        }
        if (strncmp(p, "<svg", 4) == 0 && (isspace((unsigned char)p[4]) || p[4] == '>' || p[4] == '/')) {
            char vbuf[64] = {0};
            if (parse_svg_str_attr_range(p, gt, "viewBox", vbuf, sizeof(vbuf))) {
                long long vx0 = 0, vy0 = 0, vw0 = 0, vh0 = 0;
                if (sscanf(vbuf, "%lld %lld %lld %lld", &vx0, &vy0, &vw0, &vh0) == 4 && vw0 > 0 && vh0 > 0) {
                    svg_w = vw0;
                    svg_h = vh0;
                }
            }
            if (svg_w <= 0) {
                svg_w = parse_svg_ll_attr_range(p, gt, "width", 0);
                svg_h = parse_svg_ll_attr_range(p, gt, "height", 0);
            }
        } else if (strncmp(p, "<line", 5) == 0 && (isspace((unsigned char)p[5]) || p[5] == '>' || p[5] == '/')) {
            const char *dv = NULL;
            size_t dl = 0;
            if (find_svg_attr_range(p, gt, "stroke-dasharray", &dv, &dl)) {
                p = gt + 1;
                continue;
            }
            long long x1 = parse_svg_ll_attr_range(p, gt, "x1", -1);
            long long y1 = parse_svg_ll_attr_range(p, gt, "y1", -1);
            long long x2 = parse_svg_ll_attr_range(p, gt, "x2", -1);
            long long y2 = parse_svg_ll_attr_range(p, gt, "y2", -1);
            if (x1 < 0 || y1 < 0 || x2 < 0 || y2 < 0) {
                p = gt + 1;
                continue;
            }
            int cx1 = (app->vw > 0) ? clamp_svg_coord(x1, svg_w, app->vw) : (int)ZOE_CLAMP(x1, 0, INT_MAX);
            int cx2 = (app->vw > 0) ? clamp_svg_coord(x2, svg_w, app->vw) : (int)ZOE_CLAMP(x2, 0, INT_MAX);
            int cy1 = (app->vh > 0) ? clamp_svg_coord(y1, svg_h, app->vh) : (int)ZOE_CLAMP(y1, 0, INT_MAX);
            int cy2 = (app->vh > 0) ? clamp_svg_coord(y2, svg_h, app->vh) : (int)ZOE_CLAMP(y2, 0, INT_MAX);
            char scol[24] = {0};
            parse_svg_str_attr_range(p, gt, "stroke", scol, sizeof(scol));
            int cidx = color_idx_from_hex(scol);
            long long thick_ll = parse_svg_ll_attr_range(p, gt, "stroke-width", 2);
            int thick = (int)ZOE_CLAMP(thick_ll, 1, 5);
            if (app->stroke_count < MAX_STROKES) {
                app->strokes[app->stroke_count++] = (Stroke){cx1, cy1, cx2, cy2, cidx, thick};
            } else {
                app->strokes_full = 1;
                snprintf(app->status_msg, sizeof(app->status_msg),
                         "ARTLINE FULL (%d/%d STROKES) - [Z]UNDO OR [C]LEAR",
                         app->stroke_count, MAX_STROKES);
                break;
            }
        }
        p = gt + 1;
    }
    free(buf);
}

/* ---------------- Boot State, HW Observation & UMA / ZO3 Polling ---------------- */

static void load_boot_state(const char *path, BootState *st) {
    memset(st, 0, sizeof(*st));
    snprintf(st->boot_count, sizeof(st->boot_count), "%s", "1");
    snprintf(st->restored, sizeof(st->restored), "%s", "false");
    snprintf(st->kernel, sizeof(st->kernel), "%s", "Linux-HAL x86_64");
    snprintf(st->cpu, sizeof(st->cpu), "%s", "x86_64 CPU");
    snprintf(st->ram_mb, sizeof(st->ram_mb), "%s", "512");
    snprintf(st->ip_addr, sizeof(st->ip_addr), "%s", "pending");
    snprintf(st->nic, sizeof(st->nic), "%s", "eth0");
    snprintf(st->disk, sizeof(st->disk), "%s", "/dev/vda [ZOE-STATE]");
    snprintf(st->chain_sha, sizeof(st->chain_sha), "%s", "0000000000000000");
    snprintf(st->prev_sha, sizeof(st->prev_sha), "%s", "genesis");
    snprintf(st->drawer_count, sizeof(st->drawer_count), "%s", "0");
    snprintf(st->drawer_latest, sizeof(st->drawer_latest), "%s", "(empty)");
    snprintf(st->artline_files, sizeof(st->artline_files), "%s", "0");
    snprintf(st->artline_sha, sizeof(st->artline_sha), "%s", "pending");
    snprintf(st->rsc_bytes, sizeof(st->rsc_bytes), "%s", "2990");
    snprintf(st->uma_gate, sizeof(st->uma_gate), "%s", "PRIVATE");
    snprintf(st->uma_shm, sizeof(st->uma_shm), "%s", "offline");
    snprintf(st->uma_9p, sizeof(st->uma_9p), "%s", "false");
    snprintf(st->uma_shm_ok, sizeof(st->uma_shm_ok), "%s", "false");
    snprintf(st->uma_nick_allow, sizeof(st->uma_nick_allow), "%s", "false");
    snprintf(st->uma_zoe_allow, sizeof(st->uma_zoe_allow), "%s", "false");
    snprintf(st->node_id, sizeof(st->node_id), "%s", "1");
    snprintf(st->theme, sizeof(st->theme), "%s", "gem");
    snprintf(st->hw_profile, sizeof(st->hw_profile), "%s", "KVM_UMA_SPLIT");
    snprintf(st->hw_safety_overall, sizeof(st->hw_safety_overall), "%s", "PASS");
    snprintf(st->hw_summary, sizeof(st->hw_summary), "%s", "x86_64 HAL FB0 READY");
    snprintf(st->hw_orientation, sizeof(st->hw_orientation), "%s", "landscape");
    snprintf(st->hw_zo3_budget, sizeof(st->hw_zo3_budget), "%s", "1");
    snprintf(st->zo3_slot, sizeof(st->zo3_slot), "%s", "1");
    snprintf(st->zo3_peers, sizeof(st->zo3_peers), "%s", "0");
    snprintf(st->clinical_action_authorized, sizeof(st->clinical_action_authorized), "%s", "false");
    snprintf(st->flight_control_authorized, sizeof(st->flight_control_authorized), "%s", "false");
    snprintf(st->sentience_claimed, sizeof(st->sentience_claimed), "%s", "false");
    snprintf(st->tokens_used, sizeof(st->tokens_used), "%s", "0");

    char *buf = read_file_alloc_bounded(path, 1024u * 1024u, NULL);
    if (!buf) {
        return;
    }

    parse_json_key_in_obj(buf, "boot_count", st->boot_count, sizeof(st->boot_count));
    if (!parse_json_key_in_obj(buf, "restored_from_prior", st->restored, sizeof(st->restored))) {
        parse_json_key_in_obj(buf, "self_restored", st->restored, sizeof(st->restored));
    }
    if (!parse_json_key_in_obj(buf, "kernel", st->kernel, sizeof(st->kernel))) {
        parse_json_key_in_obj(buf, "kernel_release", st->kernel, sizeof(st->kernel));
    }
    if (!parse_json_key_in_obj(buf, "cpu", st->cpu, sizeof(st->cpu))) {
        parse_json_key_in_obj(buf, "cpu_model", st->cpu, sizeof(st->cpu));
    }
    if (!parse_json_key_in_obj(buf, "ram_mb", st->ram_mb, sizeof(st->ram_mb))) {
        parse_json_key_in_obj(buf, "mem_total_mb", st->ram_mb, sizeof(st->ram_mb));
    }
    if (!parse_json_key_in_obj(buf, "ip_addr", st->ip_addr, sizeof(st->ip_addr))) {
        parse_json_key_in_obj(buf, "net_ip", st->ip_addr, sizeof(st->ip_addr));
    }
    if (!parse_json_key_in_obj(buf, "nic", st->nic, sizeof(st->nic))) {
        parse_json_key_in_obj(buf, "net_if", st->nic, sizeof(st->nic));
    }
    if (!parse_json_key_in_obj(buf, "disk", st->disk, sizeof(st->disk))) {
        parse_json_key_in_obj(buf, "state_dev", st->disk, sizeof(st->disk));
    }
    if (!parse_json_key_in_obj(buf, "chain_sha", st->chain_sha, sizeof(st->chain_sha))) {
        parse_json_key_in_obj(buf, "boot_sha256", st->chain_sha, sizeof(st->chain_sha));
    }
    if (!parse_json_key_in_obj(buf, "prev_sha", st->prev_sha, sizeof(st->prev_sha))) {
        parse_json_key_in_obj(buf, "prev_boot_sha256", st->prev_sha, sizeof(st->prev_sha));
    }
    parse_json_key_in_obj(buf, "drawer_count", st->drawer_count, sizeof(st->drawer_count));
    parse_json_key_in_obj(buf, "drawer_latest", st->drawer_latest, sizeof(st->drawer_latest));
    parse_json_key_in_obj(buf, "artline_files", st->artline_files, sizeof(st->artline_files));
    parse_json_key_in_obj(buf, "artline_sha", st->artline_sha, sizeof(st->artline_sha));
    parse_json_key_in_obj(buf, "rsc_bytes", st->rsc_bytes, sizeof(st->rsc_bytes));
    parse_json_key_in_obj(buf, "uma_gate", st->uma_gate, sizeof(st->uma_gate));
    parse_json_key_in_obj(buf, "uma_shm", st->uma_shm, sizeof(st->uma_shm));
    if (!parse_json_key_in_obj(buf, "uma_9p", st->uma_9p, sizeof(st->uma_9p))) {
        parse_json_key_in_obj(buf, "uma_9p_mounted", st->uma_9p, sizeof(st->uma_9p));
    }
    parse_json_key_in_obj(buf, "uma_shm_ok", st->uma_shm_ok, sizeof(st->uma_shm_ok));
    parse_json_key_in_obj(buf, "node_id", st->node_id, sizeof(st->node_id));
    parse_json_key_in_obj(buf, "theme", st->theme, sizeof(st->theme));
    parse_json_key_in_obj(buf, "hw_profile", st->hw_profile, sizeof(st->hw_profile));
    parse_json_key_in_obj(buf, "hw_safety_overall", st->hw_safety_overall, sizeof(st->hw_safety_overall));
    parse_json_key_in_obj(buf, "hw_summary", st->hw_summary, sizeof(st->hw_summary));
    parse_json_key_in_obj(buf, "hw_orientation", st->hw_orientation, sizeof(st->hw_orientation));
    parse_json_key_in_obj(buf, "hw_zo3_budget", st->hw_zo3_budget, sizeof(st->hw_zo3_budget));
    if (!parse_json_key_in_obj(buf, "zo3_slot", st->zo3_slot, sizeof(st->zo3_slot))) {
        snprintf(st->zo3_slot, sizeof(st->zo3_slot), "%s", st->node_id);
    }
    parse_json_key_in_obj(buf, "zo3_peers", st->zo3_peers, sizeof(st->zo3_peers));
    parse_json_key_in_obj(buf, "clinical_action_authorized", st->clinical_action_authorized,
                          sizeof(st->clinical_action_authorized));
    parse_json_key_in_obj(buf, "flight_control_authorized", st->flight_control_authorized,
                          sizeof(st->flight_control_authorized));
    parse_json_key_in_obj(buf, "sentience_claimed", st->sentience_claimed, sizeof(st->sentience_claimed));
    parse_json_key_in_obj(buf, "tokens_used", st->tokens_used, sizeof(st->tokens_used));
    free(buf);
}

static void init_gate_default(HwGate *g, const char *status, const char *detail) {
    snprintf(g->status, sizeof(g->status), "%s", status);
    snprintf(g->detail, sizeof(g->detail), "%s", detail);
}

static void load_hw_observation(const char *path, const BootState *st, HwObsInfo *obs) {
    memset(obs, 0, sizeof(*obs));
    snprintf(obs->profile, sizeof(obs->profile), "%s", st->hw_profile);
    snprintf(obs->safety_overall, sizeof(obs->safety_overall), "%s", st->hw_safety_overall);
    snprintf(obs->summary, sizeof(obs->summary), "%s", st->hw_summary);
    snprintf(obs->orientation, sizeof(obs->orientation), "%s", st->hw_orientation);
    snprintf(obs->zo3_budget, sizeof(obs->zo3_budget), "%s", st->hw_zo3_budget);
    init_gate_default(&obs->cpu_arch, "PASS", st->cpu);
    init_gate_default(&obs->ram_headroom, atoi(st->ram_mb) >= 256 ? "PASS" : "DEGRADED", st->ram_mb);
    init_gate_default(&obs->persistent_storage, strstr(st->disk, "ZOE-STATE") ? "PASS" : "DEGRADED", st->disk);
    init_gate_default(&obs->display_fb, "PASS", "32bpp /dev/fb0");
    init_gate_default(&obs->input_devices, "PASS", "evdev/tty0");
    init_gate_default(&obs->network, strcmp(st->ip_addr, "offline") == 0 ? "DEGRADED" : "PASS", st->ip_addr);
    init_gate_default(&obs->hardware_uma, strcmp(st->uma_shm, "offline") == 0 ? "DEGRADED" : "PASS", st->uma_gate);
    snprintf(obs->recommendation, sizeof(obs->recommendation), "%s", "Advisory read-only hardware check");

    char *buf = read_file_alloc_bounded(path, 1024u * 1024u, NULL);
    if (!buf) {
        return;
    }

    if (!parse_json_key_in_obj(buf, "profile", obs->profile, sizeof(obs->profile))) {
        parse_json_key_in_obj(buf, "hw_profile", obs->profile, sizeof(obs->profile));
    }
    if (!parse_json_key_in_obj(buf, "safety_overall", obs->safety_overall, sizeof(obs->safety_overall))) {
        parse_json_key_in_obj(buf, "hw_safety_overall", obs->safety_overall, sizeof(obs->safety_overall));
    }
    if (!parse_json_key_in_obj(buf, "summary", obs->summary, sizeof(obs->summary))) {
        parse_json_key_in_obj(buf, "hw_summary", obs->summary, sizeof(obs->summary));
    }
    if (!parse_json_key_in_obj(buf, "orientation", obs->orientation, sizeof(obs->orientation))) {
        parse_json_path(buf, "recommendations", "orientation", NULL, obs->orientation, sizeof(obs->orientation));
    }
    if (!parse_json_key_in_obj(buf, "zo3_budget", obs->zo3_budget, sizeof(obs->zo3_budget))) {
        parse_json_path(buf, "recommendations", "zo3_slot_budget", NULL, obs->zo3_budget, sizeof(obs->zo3_budget));
    }
    parse_json_path(buf, "gates", "cpu_arch", "status", obs->cpu_arch.status, sizeof(obs->cpu_arch.status));
    parse_json_path(buf, "gates", "cpu_arch", "detail", obs->cpu_arch.detail, sizeof(obs->cpu_arch.detail));
    parse_json_path(buf, "gates", "ram_headroom", "status", obs->ram_headroom.status, sizeof(obs->ram_headroom.status));
    parse_json_path(buf, "gates", "ram_headroom", "detail", obs->ram_headroom.detail, sizeof(obs->ram_headroom.detail));
    parse_json_path(buf, "gates", "persistent_storage", "status", obs->persistent_storage.status,
                    sizeof(obs->persistent_storage.status));
    parse_json_path(buf, "gates", "persistent_storage", "detail", obs->persistent_storage.detail,
                    sizeof(obs->persistent_storage.detail));
    parse_json_path(buf, "gates", "display_fb", "status", obs->display_fb.status, sizeof(obs->display_fb.status));
    parse_json_path(buf, "gates", "display_fb", "detail", obs->display_fb.detail, sizeof(obs->display_fb.detail));
    parse_json_path(buf, "gates", "input_devices", "status", obs->input_devices.status,
                    sizeof(obs->input_devices.status));
    parse_json_path(buf, "gates", "input_devices", "detail", obs->input_devices.detail,
                    sizeof(obs->input_devices.detail));
    parse_json_path(buf, "gates", "network", "status", obs->network.status, sizeof(obs->network.status));
    parse_json_path(buf, "gates", "network", "detail", obs->network.detail, sizeof(obs->network.detail));
    parse_json_path(buf, "gates", "hardware_uma", "status", obs->hardware_uma.status,
                    sizeof(obs->hardware_uma.status));
    parse_json_path(buf, "gates", "hardware_uma", "detail", obs->hardware_uma.detail,
                    sizeof(obs->hardware_uma.detail));
    free(buf);
}

static int find_pci_ivshmem_bar2(char *out_path, size_t cap) {
    DIR *d = opendir("/sys/bus/pci/devices");
    if (!d) {
        return 0;
    }
    struct dirent *de;
    while ((de = readdir(d)) != NULL) {
        if (de->d_name[0] == '.') {
            continue;
        }
        char vp[PATH_MAX], dp[PATH_MAX], rp[PATH_MAX];
        int n1 = snprintf(vp, sizeof(vp), "/sys/bus/pci/devices/%s/vendor", de->d_name);
        int n2 = snprintf(dp, sizeof(dp), "/sys/bus/pci/devices/%s/device", de->d_name);
        int n3 = snprintf(rp, sizeof(rp), "/sys/bus/pci/devices/%s/resource2", de->d_name);
        if (n1 < 0 || n1 >= (int)sizeof(vp) || n2 < 0 || n2 >= (int)sizeof(dp) || n3 < 0 || n3 >= (int)sizeof(rp)) {
            continue;
        }
        char vbuf[32] = {0}, dbuf[32] = {0};
        FILE *fv = fopen(vp, "r");
        FILE *fd = fopen(dp, "r");
        if (fv && fd) {
            if (fgets(vbuf, sizeof(vbuf), fv) && fgets(dbuf, sizeof(dbuf), fd)) {
                for (size_t i = 0; vbuf[i]; i++) {
                    vbuf[i] = (char)tolower((unsigned char)vbuf[i]);
                }
                for (size_t i = 0; dbuf[i]; i++) {
                    dbuf[i] = (char)tolower((unsigned char)dbuf[i]);
                }
                if (strncmp(vbuf, "0x1af4", 6) == 0 && strncmp(dbuf, "0x1110", 6) == 0 && access(rp, R_OK) == 0) {
                    fclose(fv);
                    fclose(fd);
                    closedir(d);
                    snprintf(out_path, cap, "%s", rp);
                    return 1;
                }
            }
        }
        if (fv) {
            fclose(fv);
        }
        if (fd) {
            fclose(fd);
        }
    }
    closedir(d);
    return 0;
}

static uint32_t zoe_crc32(const uint8_t *buf, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint32_t)buf[i];
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return ~crc;
}

static int read_bar2_slot_safe(const uint8_t *sp, char *jbuf, size_t jcap) {
    for (int attempt = 0; attempt < 4; attempt++) {
        uint8_t head_before[12], head_after[12];
        uint8_t meta_before[16], meta_after[16];
        memcpy(head_before, sp, 12);
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if (memcmp(head_before, UMA_SHM_MAGIC, 8) != 0) {
            return 0;
        }
        uint32_t jlen = 0;
        memcpy(&jlen, head_before + 8, 4);
        if (jlen == 0) {
            usleep(200);
            continue;
        }
        if (jlen > UMA_HDR_MAX || (size_t)jlen >= jcap) {
            return 0;
        }
        memcpy(meta_before, sp + UMA_META_OFF, 16);
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        int has_meta = (memcmp(meta_before, UMA_META_MAGIC, 4) == 0);
        uint32_t seq_before = 0, crc_before = 0, tag_before = 0;
        if (has_meta) {
            memcpy(&seq_before, meta_before + 4, 4);
            memcpy(&crc_before, meta_before + 8, 4);
            memcpy(&tag_before, meta_before + 12, 4);
            if ((seq_before & 1u) != 0u || tag_before != (crc_before ^ seq_before)) {
                usleep(200);
                continue;
            }
        }
        memcpy(jbuf, sp + 12, jlen);
        jbuf[jlen] = 0;
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        memcpy(meta_after, sp + UMA_META_OFF, 16);
        memcpy(head_after, sp, 12);
        if (memcmp(head_before, head_after, 12) != 0 ||
            memcmp(meta_before, meta_after, 16) != 0) {
            usleep(200);
            continue;
        }
        if (has_meta && zoe_crc32((const uint8_t *)jbuf, jlen) != crc_before) {
            usleep(200);
            continue;
        }
        return 1;
    }
    return 0;
}

static int poll_uma_and_zo3(DesktopApp *app, BootState *st) {
    char prev_gate[32], prev_shm[48], prev_peers[16];
    int prev_alive[4], prev_intact[4], prev_boot[4];
    snprintf(prev_gate, sizeof(prev_gate), "%s", st->uma_gate);
    snprintf(prev_shm, sizeof(prev_shm), "%s", st->uma_shm);
    snprintf(prev_peers, sizeof(prev_peers), "%s", st->zo3_peers);
    for (int i = 0; i < 4; i++) {
        prev_alive[i] = app->zo3_alive[i];
        prev_intact[i] = app->zo3_intact[i];
        prev_boot[i] = app->zo3_boot[i];
    }

    /* 1. Poll /mnt/uma/uma_state.json under non-blocking shared flock */
    int ufd = open("/mnt/uma/uma_state.json", O_RDONLY | O_NONBLOCK);
    if (ufd >= 0) {
        if (flock(ufd, LOCK_SH | LOCK_NB) == 0) {
            char ubuf[4096];
            ssize_t r = read(ufd, ubuf, sizeof(ubuf) - 1);
            flock(ufd, LOCK_UN);
            if (r > 0) {
                ubuf[r] = 0;
                parse_json_key_in_obj(ubuf, "gate", st->uma_gate, sizeof(st->uma_gate));
                parse_json_key_in_obj(ubuf, "nick_allow", st->uma_nick_allow, sizeof(st->uma_nick_allow));
                parse_json_key_in_obj(ubuf, "zoe_allow", st->uma_zoe_allow, sizeof(st->uma_zoe_allow));
                snprintf(st->uma_9p, sizeof(st->uma_9p), "%s", "true");
            }
        }
        close(ufd);
    }

    /* 2. Poll PCI ivshmem BAR2 (0x1af4:0x1110) slots 0..3 */
    static char bar2_path[PATH_MAX] = {0};
    if (!bar2_path[0]) {
        find_pci_ivshmem_bar2(bar2_path, sizeof(bar2_path));
    }
    if (bar2_path[0]) {
        int sfd = open(bar2_path, O_RDONLY);
        if (sfd >= 0) {
            size_t map_len = 4u * UMA_SLOT_STRIDE;
            void *mm = mmap(NULL, map_len, PROT_READ, MAP_SHARED, sfd, 0);
            if (mm != MAP_FAILED) {
                long long now_ts = (long long)time(NULL);
                int active_peers = 0;
                for (int slot = 0; slot < 4; slot++) {
                    const uint8_t *sp = (const uint8_t *)mm + (size_t)slot * UMA_SLOT_STRIDE;
                    char jbuf[UMA_HDR_MAX + 1];
                    if (read_bar2_slot_safe(sp, jbuf, sizeof(jbuf))) {
                        char ts_s[32] = {0}, intact_s[16] = {0}, bc_s[16] = {0};
                        parse_json_key_in_obj(jbuf, "ts", ts_s, sizeof(ts_s));
                        parse_json_key_in_obj(jbuf, "chain_intact", intact_s, sizeof(intact_s));
                        parse_json_key_in_obj(jbuf, "boot_count", bc_s, sizeof(bc_s));
                        long long slot_ts = atoll(ts_s);
                        int alive = (slot_ts > 0 && llabs(now_ts - slot_ts) <= 45) ? 1 : 0;
                        int intact = (strcmp(intact_s, "false") == 0) ? 0 : 1;
                        app->zo3_alive[slot] = alive;
                        app->zo3_intact[slot] = intact;
                        app->zo3_boot[slot] = atoi(bc_s);
                        if (slot >= 1 && alive) {
                            active_peers++;
                        }
                    } else {
                        app->zo3_alive[slot] = 0;
                    }
                }
                snprintf(st->zo3_peers, sizeof(st->zo3_peers), "%d", active_peers);
                snprintf(st->uma_shm, sizeof(st->uma_shm), "4MB BAR2 (%d/3)", active_peers);
                snprintf(st->uma_shm_ok, sizeof(st->uma_shm_ok), "%s", "true");
                munmap(mm, map_len);
            }
            close(sfd);
        }
    }

    int changed = (strcmp(prev_gate, st->uma_gate) != 0) ||
                  (strcmp(prev_shm, st->uma_shm) != 0) ||
                  (strcmp(prev_peers, st->zo3_peers) != 0);
    for (int i = 0; i < 4 && !changed; i++) {
        if (prev_alive[i] != app->zo3_alive[i] ||
            prev_intact[i] != app->zo3_intact[i] ||
            prev_boot[i] != app->zo3_boot[i]) {
            changed = 1;
        }
    }
    return changed;
}

static void trigger_uma_toggle(DesktopApp *app) {
    if (app->uma_toggle_pid > 0) {
        return;
    }
    if (access("/usr/lib/zoe/zoe_os_runtime.py", R_OK) != 0) {
        snprintf(app->status_msg, sizeof(app->status_msg),
                 "UMA TOGGLE UNAVAILABLE (OFFLINE HOST MODE)");
        return;
    }
    pid_t pid = fork();
    if (pid == 0) {
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > 2) {
                close(devnull);
            }
        }
        char *args[] = {
            "/usr/bin/python3",
            "/usr/lib/zoe/zoe_os_runtime.py",
            "--uma-toggle",
            NULL
        };
        execv(args[0], args);
        _exit(127);
    } else if (pid > 0) {
        app->uma_toggle_pid = pid;
        snprintf(app->status_msg, sizeof(app->status_msg), "UMA CONSENT TOGGLE REQUESTED...");
    }
}

/* ---------------- Artline Controls: Undo, Mandala, Stroke Add ---------------- */

static void push_undo(DesktopApp *app) {
    if (app->undo_top < MAX_UNDO) {
        app->undo_stack[app->undo_top++] = app->stroke_count;
    } else {
        memmove(&app->undo_stack[0], &app->undo_stack[1], sizeof(int) * (MAX_UNDO - 1));
        app->undo_stack[MAX_UNDO - 1] = app->stroke_count;
    }
}

static void add_stroke(DesktopApp *app, int x0, int y0, int x1, int y1) {
    int thick = (app->pen_thick >= 1 && app->pen_thick <= 5) ? app->pen_thick : 3;
    if (app->stroke_count < MAX_STROKES) {
        app->strokes[app->stroke_count++] = (Stroke){x0, y0, x1, y1, app->active_color, thick};
    } else {
        app->strokes_full = 1;
        snprintf(app->status_msg, sizeof(app->status_msg),
                 "ARTLINE FULL (%d/%d STROKES) - [Z]UNDO OR [C]LEAR",
                 app->stroke_count, MAX_STROKES);
        return;
    }
    if (app->mirror_on) {
        if (app->stroke_count < MAX_STROKES) {
            int mx0 = app->vw - x0;
            int mx1 = app->vw - x1;
            app->strokes[app->stroke_count++] = (Stroke){mx0, y0, mx1, y1, app->active_color, thick};
        } else {
            app->strokes_full = 1;
            snprintf(app->status_msg, sizeof(app->status_msg),
                     "ARTLINE FULL (%d/%d STROKES) - [Z]UNDO OR [C]LEAR",
                     app->stroke_count, MAX_STROKES);
        }
    }
}

static void stamp_mandala(DesktopApp *app) {
    if (app->vw <= 20 || app->vh <= 20) {
        return;
    }
    push_undo(app);
    int cx = app->vw / 2;
    int cy = app->vh / 2;
    int r_outer = (ZOE_MIN(app->vw, app->vh) * 38) / 100;
    int r_mid = (r_outer * 62) / 100;
    int r_inner = (r_outer * 28) / 100;
    int thick = (app->pen_thick >= 1 && app->pen_thick <= 5) ? app->pen_thick : 2;
    int added = 0;

    for (int i = 0; i < 16; i++) {
        double a0 = (2.0 * 3.14159265358979323846 * i) / 16.0;
        double a1 = (2.0 * 3.14159265358979323846 * ((i + 1) % 16)) / 16.0;
        double am = (a0 + a1) * 0.5;

        int ix0 = cx + (int)(cos(a0) * r_inner);
        int iy0 = cy + (int)(sin(a0) * r_inner);
        int ox0 = cx + (int)(cos(am) * r_outer);
        int oy0 = cy + (int)(sin(am) * r_outer);
        int ix1 = cx + (int)(cos(a1) * r_inner);
        int iy1 = cy + (int)(sin(a1) * r_inner);
        int mx0 = cx + (int)(cos(a0) * r_mid);
        int my0 = cy + (int)(sin(a0) * r_mid);
        int mx1 = cx + (int)(cos(a1) * r_mid);
        int my1 = cy + (int)(sin(a1) * r_mid);

        if (app->stroke_count + 3 <= MAX_STROKES) {
            app->strokes[app->stroke_count++] = (Stroke){ix0, iy0, ox0, oy0, app->active_color, thick};
            app->strokes[app->stroke_count++] = (Stroke){ox0, oy0, ix1, iy1, app->active_color, thick};
            app->strokes[app->stroke_count++] = (Stroke){mx0, my0, mx1, my1, (app->active_color + 2) & 7, 1};
            added += 3;
        } else {
            app->strokes_full = 1;
            break;
        }
    }
    if (app->strokes_full) {
        snprintf(app->status_msg, sizeof(app->status_msg),
                 "ARTLINE FULL (%d/%d STROKES) - [Z]UNDO OR [C]LEAR",
                 app->stroke_count, MAX_STROKES);
    } else {
        snprintf(app->status_msg, sizeof(app->status_msg),
                 "ARTLINE 16-FOLD MANDALA (+%d -> %d/%d)", added, app->stroke_count, MAX_STROKES);
    }
}

static void rescale_strokes(DesktopApp *app, int old_vw, int old_vh) {
    if (old_vw <= 0 || old_vh <= 0 || app->vw <= 0 || app->vh <= 0) {
        return;
    }
    if (old_vw == app->vw && old_vh == app->vh) {
        return;
    }
    for (int i = 0; i < app->stroke_count; i++) {
        Stroke *sk = &app->strokes[i];
        sk->x0 = clamp_svg_coord(sk->x0, old_vw, app->vw);
        sk->x1 = clamp_svg_coord(sk->x1, old_vw, app->vw);
        sk->y0 = clamp_svg_coord(sk->y0, old_vh, app->vh);
        sk->y1 = clamp_svg_coord(sk->y1, old_vh, app->vh);
    }
}

/* ---------------- Responsive 3-Mode Layout Calculator ---------------- */

static void compute_portrait_heights(int usable_h, int *hud_h, int *art_h, int *bot_h) {
    if (usable_h >= 1200) {
        *hud_h = (usable_h * 22) / 100;
        *art_h = (usable_h * 48) / 100;
        *bot_h = usable_h - *hud_h - *art_h;
        return;
    }
    if (usable_h >= 620) {
        *hud_h = ZOE_CLAMP((usable_h * 34) / 100, 224, 300);
        *art_h = ZOE_CLAMP((usable_h * 41) / 100, 236, 420);
        *bot_h = usable_h - *hud_h - *art_h;
        return;
    }
    int h_bot = (usable_h >= 440) ? 152 : ZOE_MAX(100, (usable_h * 33) / 100);
    int rem = usable_h - h_bot;
    int h_hud = ZOE_CLAMP((rem * 47) / 100, 86, 224);
    int h_art = rem - h_hud;
    if (h_art < 80) {
        int need = 80 - h_art;
        if (h_bot - need >= 100) {
            h_bot -= need;
        } else {
            h_hud -= need;
        }
        h_art = usable_h - h_hud - h_bot;
    }
    *hud_h = h_hud;
    *art_h = h_art;
    *bot_h = h_bot;
}

static void compute_layout(DesktopApp *app) {
    int lw = app->log_w;
    int lh = app->log_h;
    if (lw <= 400 || lh <= 400) {
        app->mode = MODE_MICRO;
    } else if (lh >= lw || lw < 640) {
        app->mode = MODE_PORTRAIT;
    } else {
        app->mode = MODE_LANDSCAPE;
    }

    app->menu_count = 0;
    app->uma_btn = (Rect){0, 0, 0, 0};
    app->amber_btn = (Rect){0, 0, 0, 0};
    app->theme_btn = (Rect){0, 0, 0, 0};
    app->hw_row_btn = (Rect){0, 0, 0, 0};
    app->drawer_card = (Rect){0, 0, 0, 0};
    for (int i = 0; i < 6; i++) {
        app->art_tools[i] = (Rect){0, 0, 0, 0};
    }
    for (int i = 0; i < 3; i++) {
        app->thick_btns[i] = (Rect){0, 0, 0, 0};
    }

    if (app->mode == MODE_MICRO) {
        app->menu_h = 24;
        app->foot_h = 20;
        const char *labels6[6] = {"HW", "UMA", "Flip", "Clr", "Drw", "Shl"};
        const int acts6[6] = {5, 9, 6, 2, 4, 7};
        const char *labels5[5] = {"HW", "UMA", "Flp", "Drw", "Shl"};
        const int acts5[5] = {5, 9, 6, 4, 7};
        const char *labels3[3] = {"HW", "Drw", "Shl"};
        const int acts3[3] = {5, 4, 7};
        int n = (lw >= 290) ? 6 : ((lw >= 230) ? 5 : 3);
        int x = 22;
        int avail_m = ZOE_MAX(30, lw - 60 - x);
        int item_w = (avail_m - (n - 1) * 2) / n;
        item_w = (n >= 5) ? ZOE_MAX(28, item_w) : ZOE_MAX(16, item_w);
        for (int i = 0; i < n; i++) {
            app->menus[i].label = (n == 6) ? labels6[i] : ((n == 5) ? labels5[i] : labels3[i]);
            app->menus[i].action = (n == 6) ? acts6[i] : ((n == 5) ? acts5[i] : acts3[i]);
            app->menus[i].x0 = x;
            app->menus[i].x1 = x + item_w;
            app->menus[i].y0 = 1;
            app->menus[i].y1 = 22;
            app->menus[i].scale = 1;
            x += item_w + 2;
        }
        app->menu_count = n;

        int pad = (lw < 200 || lh < 200) ? 2 : 4;
        int top = app->menu_h + pad;
        int cw = lw - 2 * pad;
        int hdr_h = (lh < 200) ? 44 : 52;
        int uma_y = top + hdr_h + pad;
        int uma_h = (lh < 200) ? 18 : 24;
        int amb_w = (lw < 200) ? 32 : 36;
        app->hw_row_btn = (Rect){pad, top, cw, hdr_h};
        app->uma_btn = (Rect){pad, uma_y, ZOE_MAX(48, ZOE_MIN(96, cw - (amb_w + 56))), uma_h};
        app->amber_btn = (Rect){lw - pad - amb_w, uma_y, amb_w, uma_h};

        int rem_y = uma_y + uma_h + pad;
        int min_rem = (lh < 200) ? 36 : 64;
        int rem_h = ZOE_MAX(min_rem, lh - app->foot_h - pad - rem_y);
        if (lw >= 300 && rem_h >= 76) {
            int pal_w = 108;
            int art_w = cw - pal_w - 4;
            app->vx = pad + 3;
            app->vy = rem_y + 3;
            app->vw = ZOE_MAX(40, art_w - 6);
            app->vh = ZOE_MAX(40, rem_h - 6);
            int px = pad + art_w + 4;
            app->sw_w = 23;
            app->sw_h = 20;
            for (int i = 0; i < 8; i++) {
                app->sw_x[i] = px + 4 + (i % 4) * 25;
                app->sw_y[i] = rem_y + 4 + (i / 4) * 23;
            }
        } else {
            int pal_h = (rem_h < 68) ? ((rem_h < 48) ? 16 : 20) : 30;
            int sh = (pal_h < 22) ? ZOE_CLAMP(pal_h - 4, 10, 16) : 24;
            int art_h = ZOE_MAX(16, rem_h - pal_h - pad);
            if (art_h + pad + pal_h > rem_h) {
                pal_h = ZOE_MAX(12, rem_h - art_h - pad);
                sh = ZOE_CLAMP(pal_h - 2, 8, sh);
            }
            app->vx = pad + 3;
            app->vy = rem_y + 3;
            app->vw = ZOE_MAX(40, cw - 6);
            app->vh = ZOE_MAX(10, art_h - 6);
            int py = rem_y + art_h + pad;
            int sw = ZOE_MAX(14, (cw - 8 - 7 * 3) / 8);
            int max_sw_y = lh - app->foot_h - sh - 1;
            int sw_y = py + ZOE_MAX(0, (pal_h - sh) / 2);
            if (sw_y > max_sw_y && max_sw_y >= rem_y) {
                sw_y = max_sw_y;
            }
            app->sw_w = sw;
            app->sw_h = sh;
            for (int i = 0; i < 8; i++) {
                app->sw_x[i] = pad + 4 + i * (sw + 3);
                app->sw_y[i] = sw_y;
            }
        }
        return;
    }

    if (app->mode == MODE_PORTRAIT) {
        app->menu_h = 68;
        app->foot_h = 28;
        const char *row1_lbl[6] = {"Desk", "Mirror", "Clear", "Save", "Drawer", "HW"};
        const int row1_act[6] = {0, 1, 2, 3, 4, 5};
        int rx = 30;
        int rw = lw - 6 - rx;
        int bw1 = (rw - 5 * 4) / 6;
        for (int i = 0; i < 6; i++) {
            app->menus[i].label = row1_lbl[i];
            app->menus[i].action = row1_act[i];
            app->menus[i].x0 = rx + i * (bw1 + 4);
            app->menus[i].x1 = app->menus[i].x0 + bw1;
            app->menus[i].y0 = 2;
            app->menus[i].y1 = 34;
            app->menus[i].scale = (bw1 >= 96) ? 2 : 1;
        }
        const char *row2_lbl[3] = {"Flip", "Shell", "Power"};
        const int row2_act[3] = {6, 7, 8};
        int bw2 = ZOE_CLAMP((lw - 256) / 3, 46, 92);
        for (int i = 0; i < 3; i++) {
            int idx = 6 + i;
            app->menus[idx].label = row2_lbl[i];
            app->menus[idx].action = row2_act[i];
            app->menus[idx].x0 = 6 + i * (bw2 + 4);
            app->menus[idx].x1 = app->menus[idx].x0 + bw2;
            app->menus[idx].y0 = 36;
            app->menus[idx].y1 = 66;
            app->menus[idx].scale = (bw2 >= 84) ? 2 : 1;
        }
        app->menu_count = 9;

        int right_x = lw - 6;
        app->amber_btn = (Rect){right_x - 38, 38, 38, 26};
        app->uma_btn = (Rect){right_x - 228, 38, 76, 26};

        int pad = 10;
        int top = app->menu_h + pad;
        int win_w = lw - 2 * pad;
        int usable_h = lh - top - app->foot_h - 3 * pad;
        int hud_h = 0, art_h = 0, bot_h = 0;
        compute_portrait_heights(usable_h, &hud_h, &art_h, &bot_h);

        app->hw_row_btn = (Rect){pad + 10, top + 24, win_w - 20, ZOE_MAX(24, ZOE_MIN(84, hud_h - 30))};

        int art_y = top + hud_h + pad;
        int art_top_off = (art_h >= 200) ? 30 : 25;
        int art_tb_h = (art_h >= 180) ? 30 : ((art_h >= 110) ? 24 : 20);
        app->vx = pad + 10;
        app->vy = art_y + art_top_off;
        app->vw = win_w - 20;
        app->vh = ZOE_MAX(28, art_h - art_top_off - art_tb_h - 10);

        int tb_y = app->vy + app->vh + 5;
        int tb_w = (app->vw - 5 * 4) / 6;
        for (int i = 0; i < 6; i++) {
            app->art_tools[i] = (Rect){app->vx + i * (tb_w + 4), tb_y, tb_w, art_tb_h};
        }

        int bot_y = art_y + art_h + pad;
        int tk_w = ((win_w - pad) * 48) / 100;
        if (tk_w < 214) {
            tk_w = 214;
        }
        int drw_w = win_w - pad - tk_w;

        int sw = (tk_w - 20 - 12) / 4;
        int sw_y_off = (bot_h >= 166) ? 30 : 25;
        int sw_gap = (bot_h >= 340) ? 8 : ((bot_h >= 166) ? 4 : 3);
        int sh = (bot_h >= 340) ? ZOE_CLAMP((bot_h - 150) / 2, 48, 86)
                                : ((bot_h >= 166) ? ZOE_CLAMP((bot_h - 98) / 2, 30, 42)
                                                  : ZOE_CLAMP((bot_h - 88) / 2, 15, 28));
        int th_h = (bot_h >= 340) ? 40 : ((bot_h >= 166) ? 24 : ((bot_h >= 132) ? 22 : ((bot_h >= 114) ? 18 : 16)));
        app->sw_w = sw;
        app->sw_h = sh;
        for (int i = 0; i < 8; i++) {
            app->sw_x[i] = pad + 10 + (i % 4) * (sw + 4);
            app->sw_y[i] = bot_y + sw_y_off + (i / 4) * (sh + sw_gap);
        }
        int th_y = bot_y + sw_y_off + 2 * (sh + sw_gap) + 2;
        int th_w = (tk_w - 20 - 8) / 3;
        for (int i = 0; i < 3; i++) {
            app->thick_btns[i] = (Rect){pad + 10 + i * (th_w + 4), th_y, th_w, th_h};
        }

        app->drawer_card = (Rect){pad + tk_w + pad, bot_y + 26, drw_w, ZOE_MAX(32, bot_h - 26)};
        return;
    }

    /* MODE_LANDSCAPE */
    app->menu_h = 30;
    app->foot_h = 28;
    const char *labels[9] = {"Desk", "Mirror", "Clear", "Save", "Drawer", "HW", "Flip", "Shell", "Power"};
    int mscale = (lw >= 1000) ? 2 : 1;
    int mpad = (lw >= 1000) ? 4 : 5;
    int mx = (lw >= 1000) ? 32 : 30;
    for (int i = 0; i < 9; i++) {
        int mw_i = (int)strlen(labels[i]) * 6 * mscale + mpad * 2;
        app->menus[i].label = labels[i];
        app->menus[i].action = i;
        app->menus[i].x0 = mx;
        app->menus[i].x1 = mx + mw_i;
        app->menus[i].y0 = 2;
        app->menus[i].y1 = 28;
        app->menus[i].scale = mscale;
        mx += mw_i + 2;
    }
    app->menu_count = 9;

    int rx = lw - 8;
    app->amber_btn = (Rect){rx - 34, 4, 34, 22};
    app->uma_btn = (Rect){rx - 204, 4, 62, 22};
    app->theme_btn = (lw >= 720) ? (Rect){rx - 250, 4, 42, 22} : (Rect){0, 0, 0, 0};

    int pad = (lw >= 1000) ? 14 : 10;
    int top = app->menu_h + pad;
    int win_h = lh - top - app->foot_h - pad;
    int left_w = (lw >= 1000) ? 210 : 172;
    int right_w = (lw >= 1000) ? 290 : 236;
    int mid_w = lw - left_w - right_w - pad * 4;
    if (mid_w < 260) {
        left_w = 156;
        right_w = 216;
        mid_w = lw - left_w - right_w - pad * 4;
    }

    int bx = pad + 12;
    int by = top + 34;
    int sw = (left_w - 24 - 12) / 4;
    int sh = (lw >= 1000) ? 26 : 24;
    app->sw_w = sw;
    app->sw_h = sh;
    for (int i = 0; i < 8; i++) {
        app->sw_x[i] = bx + (i % 4) * (sw + 4);
        app->sw_y[i] = by + (i / 4) * (sh + 6);
    }
    int th_y = by + 2 * (sh + 6) + 2;
    int th_w = (left_w - 24 - 8) / 3;
    for (int i = 0; i < 3; i++) {
        app->thick_btns[i] = (Rect){bx + i * (th_w + 4), th_y, th_w, 22};
    }

    int mid_x = pad * 2 + left_w;
    int hh = (mid_w >= 420) ? 136 : 114;
    int ty_start = top + 34 + hh + 10;
    int step_hi = (mid_w >= 540 && win_h >= 340) ? 22 : 16;
    app->hw_row_btn = (Rect){mid_x + 12, ty_start + step_hi - 2, mid_w - 24, step_hi + 2};
    app->drawer_card = (win_h >= 340)
        ? (Rect){mid_x + 12, top + win_h - 92, mid_w - 24, 82}
        : (Rect){0, 0, 0, 0};

    int art_x = mid_x + mid_w + pad;
    int info_h = (lw >= 1000) ? 196 : 176;
    app->vx = art_x + 12;
    app->vy = top + 34;
    app->vw = right_w - 24;
    app->vh = ZOE_MAX(120, win_h - 34 - info_h);

    int tool_y = app->vy + app->vh + 6;
    int tool_w = (app->vw - 5 * 3) / 6;
    for (int i = 0; i < 6; i++) {
        app->art_tools[i] = (Rect){app->vx + i * (tool_w + 3), tool_y, tool_w, 22};
    }
}

/* ---------------- 1985 P3 Amber Phosphor CRT LUT + Bloom ---------------- */

static void init_amber_lut(RenderScratch *sc, int bgr) {
    sc->bgr = bgr;
    for (int odd = 0; odd < 2; odd++) {
        double scan = odd ? 0.87 : 1.0;
        for (int l = 0; l < 256; l++) {
            double nl = (double)l / 255.0;
            int r = (int)(pow(nl, 0.85) * 255.0 * scan + 0.5);
            int g = (int)(pow(nl, 1.02) * 176.0 * scan + 0.5);
            int b = (int)(pow(nl, 1.80) * 26.0 * scan + 0.5);
            r = ZOE_CLAMP(r, 0, 255);
            g = ZOE_CLAMP(g, 0, 255);
            b = ZOE_CLAMP(b, 0, 255);
            sc->amber_lut[odd][l] = bgr
                ? ((0xFFu << 24) | ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b)
                : ((0xFFu << 24) | ((uint32_t)b << 16) | ((uint32_t)g << 8) | (uint32_t)r);
        }
    }
}

static int ensure_scratch(RenderScratch *sc, int w, int h, int bgr) {
    size_t npix = (size_t)w * (size_t)h;
    size_t roww = (size_t)ZOE_MAX(w, h);
    if (sc->bgr != bgr || !sc->lum_buf) {
        init_amber_lut(sc, bgr);
    }
    if (npix > sc->cap_pixels) {
        uint8_t *nb = (uint8_t *)realloc(sc->lum_buf, npix);
        if (!nb) {
            return 0;
        }
        sc->lum_buf = nb;
        sc->cap_pixels = npix;
    }
    if (roww > sc->cap_row) {
        uint8_t *nr = (uint8_t *)realloc(sc->bloom_row, roww);
        if (!nr) {
            return 0;
        }
        sc->bloom_row = nr;
        sc->cap_row = roww;
    }
    return 1;
}

static void free_scratch(RenderScratch *sc) {
    free(sc->lum_buf);
    free(sc->bloom_row);
    sc->lum_buf = NULL;
    sc->bloom_row = NULL;
    sc->cap_pixels = 0;
    sc->cap_row = 0;
}

static void apply_amber_crt_filter(Canvas *c, RenderScratch *sc) {
    if (!ensure_scratch(sc, c->w, c->h, c->bgr)) {
        return;
    }
    for (int y = 0; y < c->h; y++) {
        uint32_t *row = c->pix + y * c->stride;
        uint8_t *bloom = sc->bloom_row;
        uint8_t *lrow = sc->lum_buf + (size_t)y * (size_t)c->w;
        memset(bloom, 0, (size_t)c->w);
        for (int x = 0; x < c->w; x++) {
            uint32_t p = row[x];
            uint32_t r = c->bgr ? ((p >> 16) & 0xFFu) : (p & 0xFFu);
            uint32_t g = (p >> 8) & 0xFFu;
            uint32_t b = c->bgr ? (p & 0xFFu) : ((p >> 16) & 0xFFu);
            uint32_t lum = (r * 77u + g * 150u + b * 29u) >> 8;
            if (lum > 255u) {
                lum = 255u;
            }
            lrow[x] = (uint8_t)lum;
            if (lum > 150u) {
                uint32_t sp = (lum - 150u) >> 1;
                if (x > 0 && bloom[x - 1] < sp) {
                    bloom[x - 1] = (uint8_t)sp;
                }
                if (x + 1 < c->w && bloom[x + 1] < sp) {
                    bloom[x + 1] = (uint8_t)sp;
                }
                uint32_t sp2 = sp >> 1;
                if (x > 1 && bloom[x - 2] < sp2) {
                    bloom[x - 2] = (uint8_t)sp2;
                }
                if (x + 2 < c->w && bloom[x + 2] < sp2) {
                    bloom[x + 2] = (uint8_t)sp2;
                }
            }
        }
        const uint32_t *lut = sc->amber_lut[y & 1];
        for (int x = 0; x < c->w; x++) {
            uint32_t eff = (uint32_t)lrow[x] + ((uint32_t)bloom[x] >> 2);
            if (eff > 255u) {
                eff = 255u;
            }
            row[x] = lut[eff];
        }
    }
}

/* ---------------- Desktop Rendering (Landscape / Portrait / Micro) ---------------- */

static void draw_gem_p32_toolkit(Canvas *c, DesktopApp *app, int x, int y, int w, int h) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t win_bg = pack_c(c, th->win_bg);
    uint32_t accent = pack_c(c, th->accent);
    uint32_t accent2 = pack_c(c, th->accent2);
    uint32_t muted = pack_c(c, th->win_muted);
    uint32_t tab_bg = pack_c(c, th->tab_act_bg);
    uint32_t tab_fg = pack_c(c, th->tab_act_fg);
    uint32_t hov_bg = pack_c(c, th->tab_inact_bg);
    int compact = (app->mode == MODE_PORTRAIT || w < 200);

    draw_gem_window_themed(c, th, x, y, w, h, "GEM TOOLKIT", 0, compact);
    for (int i = 0; i < 8; i++) {
        int sx = app->sw_x[i];
        int sy = app->sw_y[i];
        int sw = app->sw_w;
        int sh = app->sw_h;
        int hovered = (app->mx >= sx && app->mx < sx + sw && app->my >= sy && app->my < sy + sh);
        draw_bevel_box(c, th, sx, sy, sw, sh, pal_col(c, i),
                       (i == app->active_color) ? accent : (hovered ? accent2 : ink),
                       (i == app->active_color));
        if (i == app->active_color || hovered) {
            draw_rect(c, sx, sy, sw, sh, (i == app->active_color) ? accent : accent2, 2);
        }
        char num[2] = {(char)('0' + i), 0};
        int nscale = (sh >= 26 && sw >= 28) ? 2 : 1;
        uint32_t ncol = (i == 0 || i == 5 || i == 6) ? pack_rgb(c, 18, 22, 30) : pack_rgb(c, 250, 248, 242);
        draw_text(c, sx + sw / 2 - 3 * nscale, sy + (sh - 7 * nscale) / 2, num, ncol, nscale);
    }

    const char *th_lbl[3] = {"1PX", "3PX", "5PX"};
    const int th_vals[3] = {1, 3, 5};
    for (int i = 0; i < 3; i++) {
        Rect r = app->thick_btns[i];
        int active = (app->pen_thick == th_vals[i]);
        int hov = rect_hit(r, app->mx, app->my);
        draw_bevel_box(c, th, r.x, r.y, r.w, r.h,
                       active ? tab_bg : (hov ? hov_bg : win_bg),
                       active ? accent : ink, active);
        draw_text_clipped(c, r.x + ZOE_MAX(4, (r.w - 18) / 2), r.y + (r.h - 7) / 2, th_lbl[i],
                          active ? tab_fg : ink, 1, r.w - 4);
    }

    int bx = x + 12;
    int bw = w - 24;
    int cur_y = app->thick_btns[0].y + app->thick_btns[0].h + 8;
    int bottom_lim = y + h - 38;

    if (app->mode == MODE_LANDSCAPE && cur_y + 34 < bottom_lim) {
        const char *bullets[5] = {" ", "o", "#", ">", "v"};
        int bstep = bw / 5;
        int bbw = ZOE_MIN(28, bstep - 4);
        for (int i = 0; i < 5; i++) {
            int sx = bx + i * bstep;
            draw_bevel_box(c, th, sx, cur_y, bbw, 22, (i == 0) ? hov_bg : win_bg, ink, i == 0);
            draw_text(c, sx + ZOE_MAX(3, (bbw - 6) / 2), cur_y + 7, bullets[i], ink, 1);
        }
        cur_y += 28;
    }
    if (app->mode == MODE_LANDSCAPE && cur_y + 42 < bottom_lim) {
        draw_bevel_box(c, th, bx, cur_y, bw, 38, win_bg, ink, 1);
        draw_text_clipped(c, bx + 6, cur_y + 6, "> Swiss", ink, 1, bw - 12);
        draw_text_clipped(c, bx + 6, cur_y + 22, "  Dutch", muted, 1, bw - 12);
        cur_y += 44;
    }
    if (app->mode == MODE_LANDSCAPE && cur_y + 84 < bottom_lim) {
        int lw_box = (bw - 6) * 60 / 100;
        draw_bevel_box(c, th, bx, cur_y, lw_box, 78, win_bg, ink, 1);
        draw_text_clipped(c, bx + 5, cur_y + 6,  "  Normal", muted, 1, lw_box - 8);
        draw_text_clipped(c, bx + 5, cur_y + 24, "> Bold", ink, 1, lw_box - 8);
        draw_text_clipped(c, bx + 5, cur_y + 42, "  Italic", muted, 1, lw_box - 8);
        draw_text_clipped(c, bx + 5, cur_y + 60, "  Underl", muted, 1, lw_box - 8);
        int rx = bx + lw_box + 6;
        int rw = bw - lw_box - 6;
        draw_bevel_box(c, th, rx, cur_y, rw, 78, win_bg, ink, 1);
        draw_text_clipped(c, rx + 5, cur_y + 6,  " 14", muted, 1, rw - 8);
        draw_text_clipped(c, rx + 5, cur_y + 20, " 20", muted, 1, rw - 8);
        draw_text_clipped(c, rx + 5, cur_y + 34, ">28", ink, 1, rw - 8);
        draw_text_clipped(c, rx + 5, cur_y + 48, " 36", muted, 1, rw - 8);
        draw_text_clipped(c, rx + 5, cur_y + 62, " 72", muted, 1, rw - 8);
        cur_y += 84;
    }
    if (app->mode == MODE_LANDSCAPE && cur_y + 76 < bottom_lim) {
        draw_bevel_box(c, th, bx, cur_y, bw, 72, win_bg, ink, 1);
        draw_text_clipped(c, bx + 6, cur_y + 8,  "  Left", muted, 1, bw - 12);
        draw_text_clipped(c, bx + 6, cur_y + 24, "> Center", ink, 1, bw - 12);
        draw_text_clipped(c, bx + 6, cur_y + 40, "  Right", muted, 1, bw - 12);
        draw_text_clipped(c, bx + 6, cur_y + 56, "  Decimal", muted, 1, bw - 12);
    }

    char pen_lbl[64];
    snprintf(pen_lbl, sizeof(pen_lbl), "PEN #%d %dPX * MIR %s",
             app->active_color, app->pen_thick, app->mirror_on ? "ON" : "OFF");
    if (h >= 114) {
        draw_text_clipped(c, bx, y + h - 30, pen_lbl, accent, 1, bw);
        draw_text_clipped(c, bx, y + h - 16, "[0-7] COL * [B] PX * [V] THM", muted, 1, bw);
    } else {
        draw_text_clipped(c, bx, y + h - 14, pen_lbl, accent, 1, bw);
    }
}

static void draw_artline_panel(Canvas *c, DesktopApp *app, int x, int y, int w, int h, const BootState *st) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t win_bg = pack_c(c, th->win_bg);
    uint32_t dark = pack_c(c, th->dark_panel);
    uint32_t cyan = pack_c(c, th->accent2);
    uint32_t accent = pack_c(c, th->accent);
    uint32_t mag = pack_rgb(c, 217, 70, 239);
    uint32_t cream = pack_c(c, th->dark_fg);
    uint32_t muted = pack_c(c, th->win_muted);
    uint32_t tab_bg = pack_c(c, th->tab_act_bg);
    uint32_t tab_fg = pack_c(c, th->tab_act_fg);
    uint32_t hov_bg = pack_c(c, th->tab_inact_bg);
    int compact = (app->mode == MODE_PORTRAIT);

    draw_gem_window_themed(c, th, x, y, w, h, "ARTLINE 2.0", 0, compact);
    int vx = app->vx, vy = app->vy, vw = app->vw, vh = app->vh;
    draw_bevel_box(c, th, vx, vy, vw, vh, dark, ink, 1);
    draw_rect(c, vx, vy, vw, vh, ink, 2);

    int cx = vx + vw / 2, cy = vy + vh / 2;
    for (int py = vy + 10; py < vy + vh - 10; py += 6) {
        draw_line(c, cx, py, cx, ZOE_MIN(py + 3, vy + vh - 10), accent, 1);
    }
    for (int i = 0; i < 16; i++) {
        double a0 = 2.0 * 3.14159265358979323846 * i / 16.0;
        double a1 = 2.0 * 3.14159265358979323846 * ((i + 1) % 16) / 16.0;
        int x0 = cx + (int)(cos(a0) * (vw * 0.30)), y0 = cy + (int)(sin(a0) * (vh * 0.30));
        int x1 = cx + (int)(cos(a1) * (vw * 0.30)), y1 = cy + (int)(sin(a1) * (vh * 0.30));
        draw_line(c, x0, y0, x1, y1, cyan, 1);
        int ix0 = cx + (int)(cos(a0) * (vw * 0.17)), iy0 = cy + (int)(sin(a0) * (vh * 0.17));
        draw_line(c, ix0, iy0, x0, y0, (i % 2 == 0) ? mag : accent, 1);
    }
    for (int i = 0; i < app->stroke_count; i++) {
        const Stroke *sk = &app->strokes[i];
        int thick = (sk->thick >= 1 && sk->thick <= 5) ? sk->thick : 3;
        draw_line(c, vx + ZOE_CLAMP(sk->x0, 0, vw - 1), vy + ZOE_CLAMP(sk->y0, 0, vh - 1),
                  vx + ZOE_CLAMP(sk->x1, 0, vw - 1), vy + ZOE_CLAMP(sk->y1, 0, vh - 1),
                  pal_col_artline(c, sk->color_idx, app->amber_crt), thick);
    }
    draw_text_clipped(c, vx + 6, vy + 6,
                      app->mirror_on ? "DRAG TO DRAW (MIRROR SYMM)" : "DRAG TO DRAW (FREEHAND)",
                      cyan, 1, vw - 12);
    char cnt_lbl[64];
    if (app->stroke_count >= MAX_STROKES) {
        snprintf(cnt_lbl, sizeof(cnt_lbl), "FULL %d/%d [Z]UNDO [C]LR", app->stroke_count, MAX_STROKES);
        draw_text_clipped(c, vx + 6, vy + vh - 13, cnt_lbl, accent, 1, vw - 12);
    } else {
        snprintf(cnt_lbl, sizeof(cnt_lbl), "STROKES:%d * [S]AVE [C]LR", app->stroke_count);
        draw_text_clipped(c, vx + 6, vy + vh - 13, cnt_lbl, cream, 1, vw - 12);
    }

    const char *t_lbl[6] = {"[M]IR", "[R]AD", "[Z]UND", "[B]PEN", "[S]AVE", "[C]LR"};
    const char *t_lbl_sm[6] = {"MIR", "RAD", "UND", "PEN", "SAV", "CLR"};
    for (int i = 0; i < 6; i++) {
        Rect r = app->art_tools[i];
        int on = (i == 0 && app->mirror_on);
        int hov = rect_hit(r, app->mx, app->my);
        const char *lbl = (r.w >= 40) ? t_lbl[i] : t_lbl_sm[i];
        int tw_lbl = (int)strlen(lbl) * 6;
        int tx_lbl = r.x + ZOE_MAX(2, (r.w - tw_lbl) / 2);
        draw_bevel_box(c, th, r.x, r.y, r.w, r.h,
                       on ? tab_bg : (hov ? hov_bg : win_bg),
                       on ? accent : ink, on);
        draw_text_clipped(c, tx_lbl, r.y + (r.h - 7) / 2, lbl, on ? tab_fg : ink, 1, r.w - 4);
    }

    if (app->mode == MODE_LANDSCAPE) {
        int ty = app->art_tools[0].y + app->art_tools[0].h + 8;
        int step = (h >= 600) ? 15 : 13;
        int tw = w - 24;
        int max_y = y + h - 34;
        char line[128];
        if (ty + 7 <= max_y) {
            snprintf(line, sizeof(line), "PLATES  : %s", st->artline_files);
            draw_text_clipped(c, x + 12, ty, line, ink, 1, tw);
        }
        if (ty + step + 7 <= max_y) {
            snprintf(line, sizeof(line), "VDI SHA : %.16s", st->artline_sha);
            draw_text_clipped(c, x + 12, ty + step, line, ink, 1, tw);
        }
        if (ty + step * 2 + 7 <= max_y) {
            snprintf(line, sizeof(line), "68K RSC : %s B (9 ICONS)", st->rsc_bytes);
            draw_text_clipped(c, x + 12, ty + step * 2, line, ink, 1, tw);
        }
        if (ty + step * 3 + 10 <= max_y) {
            draw_text_clipped(c, x + 12, ty + step * 3 + 3, "HOTKEYS / MOUSE:", accent, 1, tw);
        }
        if (ty + step * 4 + 10 <= max_y) {
            draw_text_clipped(c, x + 12, ty + step * 4 + 3, "[M]ir [R]adial [Z]Undo [B]Pen", ink, 1, tw);
        }
        if (ty + step * 5 + 10 <= max_y) {
            draw_text_clipped(c, x + 12, ty + step * 5 + 3, "[S]ave [C]lr [V]Thm [A]mb [O]Flp", ink, 1, tw);
        }
        if (ty + step * 6 + 10 <= max_y) {
            draw_text_clipped(c, x + 12, ty + step * 6 + 3, "[D]rawer [H]W [G]UMA [T]Shl", ink, 1, tw);
        }
        draw_text_clipped(c, x + 12, y + h - 30, "clinical_action=False * 0 TOK",
                          theme_err_red(c, th), 1, tw);
        draw_text_clipped(c, x + 12, y + h - 16, "sentience_claimed=False * HFBC",
                          muted, 1, tw);
    }
}

static void draw_menu_bar(Canvas *c, DesktopApp *app, const BootState *st) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t menu_bg = pack_c(c, th->menu_bg);
    uint32_t menu_fg = pack_c(c, th->menu_fg);
    uint32_t accent = pack_c(c, th->accent);
    uint32_t tab_bg = pack_c(c, th->tab_act_bg);
    uint32_t tab_fg = pack_c(c, th->tab_act_fg);
    uint32_t inact_bg = pack_c(c, th->tab_inact_bg);
    uint32_t hi = pack_c(c, th->bevel_hi);
    uint32_t green = theme_ok_green(c, th);
    uint32_t amber = theme_warn_amber(c, th);
    uint32_t err = theme_err_red(c, th);
    uint32_t slate = pack_c(c, th->win_muted);
    uint32_t white_hi = pack_rgb(c, 250, 248, 242);
    uint32_t pill_ink = pack_rgb(c, 16, 18, 24);

    fill_rect(c, 0, 0, c->w, app->menu_h, menu_bg);
    fill_rect(c, 0, 0, c->w, 1, hi);
    draw_line(c, 0, app->menu_h, c->w - 1, app->menu_h, ink, 2);

    /* Zoe 4-stroke flower crest inside ruby/accent badge (click cycles [V] theme!) */
    int logo_sz = (app->mode == MODE_MICRO) ? 14 : 18;
    draw_bevel_box(c, th, 6, 5, logo_sz, logo_sz, accent, ink, 0);
    draw_zoe_flower_mini(c, 6 + logo_sz / 2, 5 + logo_sz / 2, (logo_sz >= 18) ? 6 : 4,
                         is_dark_theme(th) ? pill_ink : white_hi);

    for (int i = 0; i < app->menu_count; i++) {
        MenuItem *mi = &app->menus[i];
        int hover = (app->mx >= mi->x0 && app->mx < mi->x1 && app->my >= mi->y0 && app->my < mi->y1);
        int active_tog = (mi->action == 1 && app->mirror_on) || (mi->action == 6 && app->orient_rot);
        if (hover) {
            draw_bevel_box(c, th, mi->x0, mi->y0, mi->x1 - mi->x0, mi->y1 - mi->y0, tab_bg, ink, 0);
        } else if (app->mode != MODE_LANDSCAPE) {
            draw_bevel_box(c, th, mi->x0, mi->y0, mi->x1 - mi->x0, mi->y1 - mi->y0,
                           active_tog ? inact_bg : menu_bg, ink, active_tog);
        }
        int tw = (int)strlen(mi->label) * 6 * mi->scale;
        int tx = mi->x0 + ZOE_MAX(3, (mi->x1 - mi->x0 - tw) / 2);
        int ty = mi->y0 + (mi->y1 - mi->y0 - 7 * mi->scale) / 2;
        draw_text_clipped(c, tx, ty, mi->label, hover ? tab_fg : menu_fg, mi->scale, mi->x1 - mi->x0 - 4);
    }

    if (app->mode == MODE_MICRO) {
        /* Compact ZO3 3-LED status block at top-right */
        int lx = c->w - 54;
        draw_text(c, lx, 8, "ZO3", menu_fg, 1);
        for (int s = 1; s <= 3; s++) {
            int dx = lx + 20 + (s - 1) * 10;
            uint32_t led = app->zo3_alive[s] ? (app->zo3_intact[s] ? green : amber) : slate;
            fill_rect(c, dx, 7, 8, 9, led);
            draw_rect(c, dx, 7, 8, 9, ink, 1);
        }
        return;
    }

    /* Optional Landscape [V] VMCOLOUR Theme pill */
    if (app->theme_btn.w > 0) {
        Rect tb = app->theme_btn;
        int thov = rect_hit(tb, app->mx, app->my);
        draw_bevel_box(c, th, tb.x, tb.y, tb.w, tb.h,
                       thov ? accent : tab_bg, ink, 0);
        char tlbl[16];
        snprintf(tlbl, sizeof(tlbl), "V:%d", app->theme_idx);
        draw_text_clipped(c, tb.x + 10, tb.y + 8, tlbl, thov ? white_hi : tab_fg, 1, tb.w - 8);
    }

    /* Right cluster: UMA pill + ZO3-1..3 LEDs + Boot badge + [AMB] pill */
    int cy = (app->mode == MODE_PORTRAIT) ? 38 : 4;
    Rect ub = app->uma_btn;
    int uma_shared = (strcmp(st->uma_gate, "SHARED") == 0);
    int uma_req = (strcmp(st->uma_gate, "REQUESTED") == 0);
    uint32_t ucol = uma_shared ? green : (uma_req ? amber : err);
    int uhov = rect_hit(ub, app->mx, app->my);
    draw_bevel_box(c, th, ub.x, ub.y, ub.w, ub.h, uhov ? ink : ucol, ink, 0);
    char ulbl[24];
    snprintf(ulbl, sizeof(ulbl), "UMA:%s", uma_shared ? "SHRD" : (uma_req ? "REQ" : "PRIV"));
    uint32_t utxt = (uhov && is_dark_theme(th)) ? pill_ink : (is_dark_theme(th) ? pill_ink : white_hi);
    draw_text_clipped(c, ub.x + 4, ub.y + 8, ulbl, utxt, 1, ub.w - 8);

    int zx = ub.x + ub.w + 6;
    draw_text(c, zx, cy + 8, "ZO3", menu_fg, 1);
    for (int s = 1; s <= 3; s++) {
        int lx = zx + 20 + (s - 1) * 12;
        uint32_t led = app->zo3_alive[s] ? (app->zo3_intact[s] ? green : amber) : slate;
        fill_rect(c, lx, cy + 6, 10, 11, led);
        draw_rect(c, lx, cy + 6, 10, 11, ink, 1);
    }

    int bx = zx + 60;
    char b_lbl[40];
    snprintf(b_lbl, sizeof(b_lbl), "B#%s", st->boot_count);
    draw_text_clipped(c, bx, cy + 8, b_lbl, accent, 1, app->amber_btn.x - bx - 4);

    Rect ab = app->amber_btn;
    int ahov = rect_hit(ab, app->mx, app->my);
    draw_bevel_box(c, th, ab.x, ab.y, ab.w, ab.h,
                   app->amber_crt ? amber : (ahov ? tab_bg : menu_bg), ink, app->amber_crt);
    draw_text_clipped(c, ab.x + 5, ab.y + 8, "AMB",
                      app->amber_crt ? pill_ink : (ahov ? tab_fg : menu_fg), 1, ab.w - 6);
}

static uint32_t gate_color_th(const Canvas *c, const GemTheme *th, const char *status) {
    if (strcmp(status, "PASS") == 0) {
        return theme_ok_green(c, th);
    }
    if (strcmp(status, "DEGRADED") == 0) {
        return theme_warn_amber(c, th);
    }
    return theme_err_red(c, th);
}

static void render_micro_hud(Canvas *c, DesktopApp *app, const BootState *st) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t win_bg = pack_c(c, th->win_bg);
    uint32_t dark = pack_c(c, th->dark_panel);
    uint32_t cyan = pack_c(c, th->accent2);
    uint32_t accent = pack_c(c, th->accent);
    uint32_t green = theme_ok_green(c, th);
    uint32_t amber = theme_warn_amber(c, th);
    uint32_t err = theme_err_red(c, th);
    uint32_t cream = pack_c(c, th->dark_fg);
    uint32_t white_hi = pack_rgb(c, 250, 248, 242);
    uint32_t pill_ink = pack_rgb(c, 16, 18, 24);

    Rect hc = app->hw_row_btn;
    draw_bevel_box(c, th, hc.x, hc.y, hc.w, hc.h, dark, ink, 1);
    draw_rect(c, hc.x, hc.y, hc.w, hc.h, ink, 2);
    int ruby_r = ZOE_MIN(16, ZOE_MAX(10, (hc.h - 12) / 2));
    draw_zoe_ruby(c, hc.x + ruby_r + 6, hc.y + hc.h / 2, ruby_r);

    int tx = hc.x + ruby_r * 2 + 12;
    int tw = hc.w - (ruby_r * 2 + 16);
    int hstep = (hc.h < 50) ? 10 : 11;
    int hy0 = hc.y + ((hc.h < 50) ? 3 : 5);
    char line[128];
    snprintf(line, sizeof(line), "ZOE MICRO-HUD | %s", st->hw_safety_overall);
    draw_text_clipped(c, tx, hy0, line,
                      strcmp(st->hw_safety_overall, "PASS") == 0 ? green : amber, 1, tw);
    draw_text_clipped(c, tx, hy0 + hstep, st->hw_profile, cyan, 1, tw);
    draw_text_clipped(c, tx, hy0 + hstep * 2, st->hw_summary, cream, 1, tw);
    snprintf(line, sizeof(line), "B#%s | %s | DRW:%s", st->boot_count, st->ip_addr, st->drawer_count);
    draw_text_clipped(c, tx, hy0 + hstep * 3, line, cream, 1, tw);

    /* UMA + ZO3 strip */
    Rect ub = app->uma_btn;
    int uty = ub.y + (ub.h - 7) / 2;
    int zly = ub.y + (ub.h - 11) / 2;
    int uma_shared = (strcmp(st->uma_gate, "SHARED") == 0);
    draw_bevel_box(c, th, ub.x, ub.y, ub.w, ub.h, uma_shared ? green : err, ink, 0);
    snprintf(line, sizeof(line), "UMA:%s", st->uma_gate);
    draw_text_clipped(c, ub.x + 4, uty, line, is_dark_theme(th) ? pill_ink : white_hi, 1, ub.w - 8);

    int zx = ub.x + ub.w + 6;
    draw_text_clipped(c, zx, uty, "Z:", ink, 1, 14);
    for (int s = 1; s <= 3; s++) {
        int lx = zx + 14 + (s - 1) * 11;
        uint32_t led = app->zo3_alive[s] ? green : pack_c(c, th->win_muted);
        fill_rect(c, lx, zly, 9, 11, led);
        draw_rect(c, lx, zly, 9, 11, ink, 1);
    }

    Rect ab = app->amber_btn;
    draw_bevel_box(c, th, ab.x, ab.y, ab.w, ab.h, app->amber_crt ? amber : win_bg, ink, app->amber_crt);
    draw_text_clipped(c, ab.x + 4, uty, "AMB", app->amber_crt ? pill_ink : ink, 1, ab.w - 6);

    /* Mini Artline pad */
    draw_bevel_box(c, th, app->vx, app->vy, app->vw, app->vh, dark, ink, 1);
    draw_rect(c, app->vx, app->vy, app->vw, app->vh, ink, 2);
    int midx = app->vx + app->vw / 2;
    for (int py = app->vy + 4; py < app->vy + app->vh - 4; py += 5) {
        draw_line(c, midx, py, midx, ZOE_MIN(py + 2, app->vy + app->vh - 4), accent, 1);
    }
    for (int i = 0; i < app->stroke_count; i++) {
        const Stroke *sk = &app->strokes[i];
        draw_line(c, app->vx + ZOE_CLAMP(sk->x0, 0, app->vw - 1),
                  app->vy + ZOE_CLAMP(sk->y0, 0, app->vh - 1),
                  app->vx + ZOE_CLAMP(sk->x1, 0, app->vw - 1),
                  app->vy + ZOE_CLAMP(sk->y1, 0, app->vh - 1),
                  pal_col_artline(c, sk->color_idx, app->amber_crt),
                  ZOE_CLAMP(sk->thick, 1, 5));
    }
    snprintf(line, sizeof(line), "ART:%d", app->stroke_count);
    draw_text_clipped(c, app->vx + 4, app->vy + 4, line, cyan, 1, app->vw - 8);

    /* Swatches */
    for (int i = 0; i < 8; i++) {
        fill_rect(c, app->sw_x[i], app->sw_y[i], app->sw_w, app->sw_h, pal_col(c, i));
        draw_rect(c, app->sw_x[i], app->sw_y[i], app->sw_w, app->sw_h,
                  (i == app->active_color) ? accent : ink, (i == app->active_color) ? 2 : 1);
    }
    if (c->w >= 300 && c->h >= 200) {
        int hx = app->sw_x[0];
        int hy = app->sw_y[4] + app->sw_h + 6;
        if (hy + 22 < c->h - app->foot_h) {
            draw_text_clipped(c, hx, hy, "[H]W [G]UMA [V]TH", ink, 1, 106);
            draw_text_clipped(c, hx, hy + 11, "[A]MB [S]AV [D]RW", accent, 1, 106);
        }
    }
}

static void render_hud_panel(Canvas *c, DesktopApp *app, const BootState *st, int x, int y, int w, int h) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t dark = pack_c(c, th->dark_panel);
    uint32_t cyan = pack_c(c, th->accent2);
    uint32_t accent = pack_c(c, th->accent);
    uint32_t green = theme_ok_green(c, th);
    uint32_t cream = pack_c(c, th->dark_fg);
    uint32_t amber = theme_warn_amber(c, th);
    uint32_t muted = pack_c(c, th->win_muted);
    uint32_t card_bg = pack_c(c, th->card_bg);
    uint32_t gold = pack_rgb(c, 245, 188, 42);
    uint32_t pill_ink = pack_rgb(c, 14, 18, 24);
    uint32_t white_hi = pack_rgb(c, 250, 248, 242);
    int compact = (app->mode == MODE_PORTRAIT);

    draw_gem_window_themed(c, th, x, y, w, h, "ZOE-GEM OS :: HW & RETENTION", 1, compact);
    int is_restored = (strcmp(st->restored, "true") == 0);

    if (app->mode == MODE_PORTRAIT) {
        int bx = x + 10, bw = w - 20;
        int wide_p = (w >= 660);
        int by = y + ((h < 130 && !wide_p) ? 23 : 26);
        int bh = wide_p ? ZOE_CLAMP(h - 34, 68, 130)
                        : ((h >= 190) ? 84 : ZOE_CLAMP(h - 30, 52, 76));
        int ban_w = wide_p ? 310 : bw;
        draw_bevel_box(c, th, bx, by, ban_w, bh, dark, ink, 1);
        draw_rect(c, bx, by, ban_w, bh, ink, 2);
        int rr = wide_p ? ZOE_MIN(38, (bh - 10) / 2)
                        : ((bh >= 78) ? 28 : ((bh >= 66) ? 24 : 20));
        draw_zoe_ruby(c, bx + rr + 14, by + bh / 2, rr);

        int btx = bx + rr * 2 + 24;
        int btw = ban_w - (rr * 2 + 30);
        draw_text_clipped(c, btx, by + 8, "ZOE-GEM OS v1.0", cream, wide_p ? 2 : 1, btw);
        fill_rect(c, btx, by + (wide_p ? 28 : 20), btw, 20, is_restored ? green : accent);
        draw_rect(c, btx, by + (wide_p ? 28 : 20), btw, 20, cream, 1);
        draw_text_clipped(c, btx + 4, by + (wide_p ? 34 : 26),
                          is_restored ? "SELF-RESTORED!" : "COLD BOOT SEALED",
                          is_dark_theme(th) ? pill_ink : white_hi, 1, btw - 8);
        if (bh >= 56) {
            char sub[96];
            snprintf(sub, sizeof(sub), "FB0 %dx%d * %s", app->log_w, app->log_h, th->key);
            draw_text_clipped(c, btx, by + (wide_p ? 56 : 46), sub, cyan, 1, btw);
        }
        if (bh >= 72) {
            draw_text_clipped(c, btx, by + (wide_p ? 72 : 62), "NICK x ZOE * HFBC * [V]THM",
                              gold, 1, btw);
        }

        int tx = wide_p ? (bx + ban_w + 12) : bx;
        int tw = wide_p ? (bw - ban_w - 12) : bw;
        int ty = wide_p ? by : (by + bh + 6);
        int max_y = y + h - 8;
        char row[160];
        if (ty + 14 < max_y) {
            snprintf(row, sizeof(row), "BOOT #%s (%s) * KERNEL: %.24s",
                     st->boot_count, is_restored ? "VERIFIED" : "GENESIS", st->kernel);
            draw_text_clipped(c, tx, ty, row, is_restored ? green : ink, 1, tw);
            ty += 15;
        }
        if (ty + 14 < max_y) {
            app->hw_row_btn = (Rect){tx, ty - 2, tw, 16};
            snprintf(row, sizeof(row), "HW [H]: %s [%s]", st->hw_profile, st->hw_safety_overall);
            draw_text_clipped(c, tx, ty, row, gate_color_th(c, th, st->hw_safety_overall), 1, tw);
            ty += 15;
        }
        if (ty + 14 < max_y) {
            draw_text_clipped(c, tx, ty, st->hw_summary, ink, 1, tw);
            ty += 15;
        }
        if (ty + 14 < max_y) {
            snprintf(row, sizeof(row), "CPU/RAM: %.22s / %s MB", st->cpu, st->ram_mb);
            draw_text_clipped(c, tx, ty, row, ink, 1, tw);
            ty += 15;
        }
        if (ty + 14 < max_y) {
            snprintf(row, sizeof(row), "NET: %s -> %s", st->nic, st->ip_addr);
            draw_text_clipped(c, tx, ty, row, green, 1, tw);
            ty += 15;
        }
        if (ty + 14 < max_y) {
            int uma_open = (strcmp(st->uma_gate, "SHARED") == 0);
            snprintf(row, sizeof(row), "UMA[G]: %s (%s) * ZO3:%s",
                     st->uma_gate, st->uma_shm, st->zo3_peers);
            draw_text_clipped(c, tx, ty, row, uma_open ? green : amber, 1, tw);
            ty += 15;
        }
        if (ty + 12 < max_y) {
            snprintf(row, sizeof(row), "SHA256: %.20s", st->chain_sha);
            draw_text_clipped(c, tx, ty, row, muted, 1, tw);
        }
        return;
    }

    /* Landscape Center HUD */
    int hx = x + 12, hy = y + 34, hw = w - 24;
    int hh = (w >= 420) ? 136 : 114;
    int rr = (w >= 420) ? 46 : 34;
    int rcx = hx + rr + 16;
    draw_bevel_box(c, th, hx, hy, hw, hh, dark, ink, 1);
    draw_rect(c, hx, hy, hw, hh, ink, 2);
    draw_zoe_ruby(c, rcx, hy + hh / 2, rr);

    int crest_pad = (hw >= 390) ? 44 : 8;
    int btx = rcx + rr + 14;
    int btw = hx + hw - btx - crest_pad;
    int t_sc = (btw >= 200) ? 2 : 1;
    draw_text_clipped(c, btx, hy + 12, "ZOE-GEM OS v1.0", cream, t_sc, btw);
    draw_text_clipped(c, btx, hy + (t_sc == 2 ? 34 : 26), "7-STRAND SOVEREIGN DNA * GEM+BEOS", cyan, 1, btw);
    if (hw >= 390) {
        draw_nick_florette_mini(c, hx + hw - 28, hy + 20, 7, white_hi, gold);
        draw_zoe_flower_mini(c, hx + hw - 13, hy + 21, 7, cyan);
    }
    int pill_y = hy + (t_sc == 2 ? 50 : 40);
    int pill_h = (btw >= 280) ? 28 : 22;
    int pill_w = hx + hw - btx - 8;
    draw_bevel_box(c, th, btx, pill_y, pill_w, pill_h, is_restored ? green : accent, cream, 0);
    int p_sc = (pill_w >= 300) ? 2 : 1;
    draw_text_clipped(c, btx + 6, pill_y + (pill_h - 7 * p_sc) / 2,
                      is_restored ? "SELF-RESTORED FROM DISK!" : "COLD BOOT SEALED ON DISK",
                      is_dark_theme(th) ? pill_ink : white_hi, p_sc, pill_w - 12);
    char sub[96];
    snprintf(sub, sizeof(sub), "FB0 %dx%d * EVDEV+KD_GFX * 0 TOK", app->log_w, app->log_h);
    draw_text_clipped(c, btx, pill_y + pill_h + 8, sub, cream, 1, pill_w);
    snprintf(sub, sizeof(sub), "NICK x ZOE * HFBC * [V] %s", th->name);
    draw_text_clipped(c, btx, pill_y + pill_h + 22, sub, gold, 1, pill_w);

    int ty = hy + hh + 10;
    int tw = w - 28;
    int hi_sc = (w >= 540 && h >= 340) ? 2 : 1;
    int hi_step = (hi_sc == 2) ? 22 : 16;
    int lo_step = 16;
    int hi_gh = 7 * hi_sc;
    int max_y = y + h - 8;
    char row[180];

    app->hw_row_btn = (Rect){0, 0, 0, 0};
    if (ty + hi_gh <= max_y) {
        snprintf(row, sizeof(row), "BOOT COUNT  : #%s (prior=%s)", st->boot_count, is_restored ? "VERIFIED" : "GENESIS");
        draw_text_clipped(c, x + 14, ty, row, is_restored ? green : ink, hi_sc, tw);
        ty += hi_step;
    }
    if (ty + hi_gh <= max_y) {
        app->hw_row_btn = (Rect){x + 12, ty - 2, tw, hi_step + 2};
        snprintf(row, sizeof(row), "HW PROFILE  : %s [%s] (H)", st->hw_profile, st->hw_safety_overall);
        draw_text_clipped(c, x + 14, ty, row, gate_color_th(c, th, st->hw_safety_overall), hi_sc, tw);
        ty += hi_step;
    }
    if (ty + 7 <= max_y) {
        snprintf(row, sizeof(row), "HW CHECK    : %s", st->hw_summary);
        draw_text_clipped(c, x + 14, ty, row, ink, 1, tw);
        ty += lo_step;
    }
    if (ty + 7 <= max_y) {
        snprintf(row, sizeof(row), "KERNEL HAL  : %s", st->kernel);
        draw_text_clipped(c, x + 14, ty, row, ink, 1, tw);
        ty += lo_step;
    }
    if (ty + 7 <= max_y) {
        snprintf(row, sizeof(row), "CPU / RAM   : %.26s / %s MB", st->cpu, st->ram_mb);
        draw_text_clipped(c, x + 14, ty, row, ink, 1, tw);
        ty += lo_step;
    }
    if (ty + 7 <= max_y) {
        snprintf(row, sizeof(row), "HARDWARE DB : %s", st->disk);
        draw_text_clipped(c, x + 14, ty, row, ink, 1, tw);
        ty += lo_step;
    }
    if (ty + hi_gh <= max_y) {
        snprintf(row, sizeof(row), "NETWORK NIC : %s -> IPv4 %s", st->nic, st->ip_addr);
        draw_text_clipped(c, x + 14, ty, row, green, hi_sc, tw);
        ty += hi_step;
    }
    if (ty + hi_gh <= max_y) {
        int uma_open = (strcmp(st->uma_gate, "SHARED") == 0);
        snprintf(row, sizeof(row), "UMA BRIDGE  : %s (%s) [G]", st->uma_gate, st->uma_shm);
        draw_text_clipped(c, x + 14, ty, row, uma_open ? green : amber, hi_sc, tw);
        ty += hi_step;
    }

    int drawer_top = ZOE_MAX(ty + 6, y + h - 98);
    if (ty + 30 < drawer_top && ty + 21 <= max_y) {
        snprintf(row, sizeof(row), "BOOT SHA256 : %.24s", st->chain_sha);
        draw_text_clipped(c, x + 14, ty, row, ink, 1, tw);
        ty += 14;
        snprintf(row, sizeof(row), "PREV SHA256 : %.24s", st->prev_sha);
        draw_text_clipped(c, x + 14, ty, row, muted, 1, tw);
        ty += 16;
    }

    int dx = x + 12, dw = w - 24, dh = (y + h) - ty - 10;
    app->drawer_card = (dh >= 56) ? (Rect){dx, ty, dw, dh} : (Rect){0, 0, 0, 0};
    if (dh >= 56) {
        draw_bevel_box(c, th, dx, ty, dw, dh, card_bg, ink, 1);
        draw_rect(c, dx, ty, dw, dh, ink, 2);
        snprintf(row, sizeof(row), "NICK'S PERSISTENT DRAWER (%s NOTES)", st->drawer_count);
        draw_text_clipped(c, dx + 8, ty + 7, row, accent, 1, dw - 16);

        int ny = ty + 22;
        if (app->note_count > 0) {
            int max_show = (dh >= 96) ? 3 : ((dh >= 76) ? 2 : 1);
            int start = ZOE_MAX(0, app->note_count - max_show);
            for (int i = app->note_count - 1; i >= start && ny + 14 < ty + dh - 14; i--) {
                snprintf(row, sizeof(row), "[#%d] %s", app->notes[i].boot, app->notes[i].text);
                draw_text_clipped(c, dx + 8, ny, row, ink, 1, dw - 16);
                ny += 13;
            }
        } else {
            snprintf(row, sizeof(row), "> %s", st->drawer_latest);
            draw_text_clipped(c, dx + 8, ny, row, ink, 1, dw - 16);
        }
        draw_text_clipped(c, dx + 8, ty + dh - 14,
                          "[D] ADD / VIEW NOTES * SHA-256 SEALED",
                          muted, 1, dw - 16);
    }
}

static void render_portrait_drawer_card(Canvas *c, DesktopApp *app, const BootState *st) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t accent = pack_c(c, th->accent);
    uint32_t card_bg = pack_c(c, th->card_bg);
    uint32_t tab_bg = pack_c(c, th->tab_act_bg);
    uint32_t tab_fg = pack_c(c, th->tab_act_fg);
    Rect dr = app->drawer_card;
    int win_y = dr.y - 26;
    int win_h = dr.h + 26;
    draw_gem_window_themed(c, th, dr.x, win_y, dr.w, win_h, "NICK'S DRAWER", 0, 1);

    int ix = dr.x + 8, iy = dr.y + 4, iw = dr.w - 16, ih = dr.h - 12;
    draw_bevel_box(c, th, ix, iy, iw, ih, card_bg, ink, 1);

    char hdr[48];
    snprintf(hdr, sizeof(hdr), "%s NOTES ON DISK", st->drawer_count);
    draw_text_clipped(c, ix + 6, iy + 6, hdr, accent, 1, iw - 12);

    int ny = iy + 22;
    if (app->note_count > 0) {
        int start = ZOE_MAX(0, app->note_count - 4);
        for (int i = app->note_count - 1; i >= start && ny + 16 < iy + ih - 28; i--) {
            char line[160];
            snprintf(line, sizeof(line), "[#%d] %s", app->notes[i].boot, app->notes[i].text);
            draw_text_clipped(c, ix + 6, ny, line, ink, 1, iw - 12);
            ny += 14;
        }
    } else {
        draw_text_clipped(c, ix + 6, ny, st->drawer_latest, ink, 1, iw - 12);
    }

    int btn_y = iy + ih - 26;
    draw_bevel_box(c, th, ix + 6, btn_y, iw - 12, 22, tab_bg, ink, 0);
    draw_text_clipped(c, ix + 12, btn_y + 7, "[D] TAP TO ADD/VIEW", tab_fg, 1, iw - 24);
}

static void render_modals(Canvas *c, DesktopApp *app, const BootState *st) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t win_bg = pack_c(c, th->win_bg);
    uint32_t accent = pack_c(c, th->accent);
    uint32_t accent2 = pack_c(c, th->accent2);
    uint32_t green = theme_ok_green(c, th);
    uint32_t err = theme_err_red(c, th);
    uint32_t slate = pack_c(c, th->win_muted);
    uint32_t gold = pack_rgb(c, 245, 188, 42);
    uint32_t white_hi = pack_rgb(c, 250, 248, 242);
    uint32_t pill_ink = pack_rgb(c, 16, 18, 24);
    int compact = (app->mode != MODE_LANDSCAPE);
    int band_top = app->menu_h + 4;
    int band_bot = c->h - app->foot_h - 6;
    int max_mh = ZOE_MAX(40, band_bot - band_top);

    app->modal_save_btn = (Rect){0, 0, 0, 0};
    app->modal_cancel_btn = (Rect){0, 0, 0, 0};
    app->kbd_rect = (Rect){0, 0, 0, 0};
    app->kbd_count = 0;

    if (app->about_modal) {
        int mw = ZOE_MIN(500, c->w - 16);
        int mh = ZOE_MIN(192, max_mh);
        int mdx = (c->w - mw) / 2;
        int mdy = band_top + ZOE_MAX(0, (max_mh - mh) / 2);
        app->modal_rect = (Rect){mdx, mdy, mw, mh};
        draw_gem_window_themed(c, th, mdx, mdy, mw, mh, "ABOUT ZOE-GEM OS v1.0", 1, compact);
        int tw = mw - 24;
        int ay = mdy + (compact ? 26 : 34);
        int astep = (mh >= 176) ? 20 : 14;
        int alim = mdy + mh - 22;
        if (mw >= 320 && mh >= 110) {
            draw_nick_florette_mini(c, mdx + mw - 38, mdy + (compact ? 38 : 48), 9, ink, gold);
            draw_zoe_flower_mini(c, mdx + mw - 18, mdy + (compact ? 39 : 49), 9, accent);
        }
        if (ay + 10 < alim) {
            draw_text_clipped(c, mdx + 12, ay, "Nick x Zoe :: 7-Strand Sovereign DNA (HFBC)", ink, 1, tw - 48);
            ay += astep;
        }
        if (ay + 10 < alim) {
            draw_text_clipped(c, mdx + 12, ay, "Star + GEM + ViewMAX/3 + BeOS + QNX + Plan9 + Amiga",
                              is_dark_theme(th) ? accent2 : pack_rgb(c, 22, 86, 158), 1, tw - 48);
            ay += astep;
        }
        if (ay + 10 < alim) {
            draw_text_clipped(c, mdx + 12, ay, "UEFI x86_64 -> Linux HAL -> Native /dev/fb0 Desktop", ink, 1, tw);
            ay += astep;
        }
        if (ay + 10 < alim) {
            draw_text_clipped(c, mdx + 12, ay, "Zero X11 * Zero Systemd * Zero Cloud Tokens ($0.00)", green, 1, tw);
            ay += astep;
        }
        if (ay + 10 < alim) {
            draw_text_clipped(c, mdx + 12, ay,
                              "clinical_action=False * flight_ctrl=False * sentience=False", err, 1, tw);
        }
        draw_text_clipped(c, mdx + 12, mdy + mh - 18, "Press [V] for 10 VMCOLOUR themes * ESC/Click to dismiss", slate, 1, tw);
    } else if (app->hw_modal) {
        int mw = ZOE_MIN(560, c->w - 16);
        int mh = ZOE_MIN(290, max_mh);
        int mdx = (c->w - mw) / 2;
        int mdy = band_top + ZOE_MAX(0, (max_mh - mh) / 2);
        app->modal_rect = (Rect){mdx, mdy, mw, mh};
        draw_gem_window_themed(c, th, mdx, mdy, mw, mh, "HARDWARE SAFETY DIAGNOSTIC [H]", 1, compact);
        int tw = mw - 24;
        int y = mdy + (compact ? 25 : 32);
        int step = (mh >= 240) ? 18 : ((mh >= 200) ? 14 : 13);
        char line[180];
        snprintf(line, sizeof(line), "PROFILE: %s | OVERALL: %s | ZO3 BUDGET: %s",
                 app->hw_obs.profile, app->hw_obs.safety_overall, app->hw_obs.zo3_budget);
        draw_text_clipped(c, mdx + 12, y, line, gate_color_th(c, th, app->hw_obs.safety_overall), 1, tw);
        y += step;
        draw_text_clipped(c, mdx + 12, y, app->hw_obs.summary, ink, 1, tw);
        y += step;

        const char *gnames[7] = {
            "CPU/ARCH", "RAM", "STORAGE", "DISPLAY", "INPUT", "NETWORK", "HW UMA"
        };
        const HwGate *gates[7] = {
            &app->hw_obs.cpu_arch, &app->hw_obs.ram_headroom, &app->hw_obs.persistent_storage,
            &app->hw_obs.display_fb, &app->hw_obs.input_devices, &app->hw_obs.network,
            &app->hw_obs.hardware_uma
        };
        for (int i = 0; i < 7 && y + 10 <= mdy + mh - 36; i++) {
            snprintf(line, sizeof(line), "%-8s [%-8s] %s", gnames[i], gates[i]->status, gates[i]->detail);
            draw_text_clipped(c, mdx + 12, y, line, gate_color_th(c, th, gates[i]->status), 1, tw);
            y += step;
        }
        draw_text_clipped(c, mdx + 12, mdy + mh - 32,
                          "clinical_action=False * flight_control=False * sentience_claimed=False * 0 TOK",
                          err, 1, tw);
        draw_text_clipped(c, mdx + 12, mdy + mh - 16,
                          "Advisory read-only check * Click or press ESC/H to close", slate, 1, tw);
    } else if (app->drawer_modal) {
        int show_kbd = (app->mode == MODE_PORTRAIT && max_mh >= 380);
        int kbd_h = show_kbd ? ZOE_CLAMP((max_mh * 30) / 100, 176, 320) : 0;
        int mw = ZOE_MIN(show_kbd ? 740 : 540, c->w - 16);
        int mh = show_kbd ? ZOE_MIN(340, max_mh - kbd_h - 18) : ZOE_MIN(264, max_mh);
        int total_h = mh + (show_kbd ? (kbd_h + 10) : 0);
        int mdx = (c->w - mw) / 2;
        int mdy = band_top + ZOE_MAX(4, (max_mh - total_h) / 2);
        app->modal_rect = (Rect){mdx, mdy, mw, mh};
        draw_gem_window_themed(c, th, mdx, mdy, mw, mh, "NICK'S DRAWER :: NOTES", 1, compact);
        int tw = mw - 24;
        int tight = (mh < 210);
        int top_y = mdy + (compact ? 25 : 34);
        draw_text_clipped(c, mdx + 12, top_y,
                          show_kbd ? "Tap GEM touch keys or type + SAVE:" : "Type note + ENTER (or tap SAVE):",
                          ink, 1, tw);

        int box_y = top_y + (tight ? 11 : 14);
        int box_h = tight ? 22 : (mw >= 600 ? 34 : 26);
        int box_w = tw;
        draw_bevel_box(c, th, mdx + 12, box_y, box_w, box_h, win_bg, accent, 1);
        draw_rect(c, mdx + 12, box_y, box_w, box_h, accent, 2);
        char prompt_line[110];
        snprintf(prompt_line, sizeof(prompt_line), "%s_", app->drawer_buf);
        int in_sc = (mw >= 360 && !tight) ? 2 : 1;
        draw_text_tail(c, mdx + 18, box_y + (box_h - 7 * in_sc) / 2, prompt_line, ink, in_sc, box_w - 12);

        int btn_y = box_y + box_h + (tight ? 4 : 6);
        int btn_h = tight ? 22 : (mw >= 600 ? 30 : 24);
        int btn_w = ZOE_MIN(132, (tw - 8) / 2);
        app->modal_save_btn = (Rect){mdx + 12, btn_y, btn_w, btn_h};
        app->modal_cancel_btn = (Rect){mdx + 12 + btn_w + 8, btn_y, btn_w, btn_h};
        draw_bevel_box(c, th, app->modal_save_btn.x, app->modal_save_btn.y, btn_w, btn_h, green, ink, 0);
        draw_text_clipped(c, app->modal_save_btn.x + 8, btn_y + (btn_h - 7) / 2, "SAVE [RET]",
                          is_dark_theme(th) ? pill_ink : white_hi, 1, btn_w - 12);
        draw_bevel_box(c, th, app->modal_cancel_btn.x, app->modal_cancel_btn.y, btn_w, btn_h, win_bg, ink, 0);
        draw_text_clipped(c, app->modal_cancel_btn.x + 8, btn_y + (btn_h - 7) / 2, "CANCEL [ESC]", ink, 1, btn_w - 12);

        int list_y = btn_y + btn_h + (tight ? 6 : 8);
        int list_bot = mdy + mh - 18;
        if (list_y + 14 < list_bot && app->note_count > 0) {
            int max_vis = (list_bot - list_y) / 14;
            if (max_vis < 1) {
                max_vis = 1;
            }
            int max_scroll = ZOE_MAX(0, app->note_count - max_vis);
            if (app->drawer_scroll > max_scroll) {
                app->drawer_scroll = max_scroll;
            }
            if (app->drawer_scroll < 0) {
                app->drawer_scroll = 0;
            }
            for (int row_i = 0; row_i < max_vis; row_i++) {
                int idx = app->note_count - 1 - (app->drawer_scroll + row_i);
                if (idx < 0) {
                    break;
                }
                char nline[180];
                snprintf(nline, sizeof(nline), "[#%d] %s", app->notes[idx].boot, app->notes[idx].text);
                draw_text_clipped(c, mdx + 12, list_y + row_i * 14, nline, ink, 1, tw);
            }
        } else if (list_y + 14 < list_bot) {
            draw_text_clipped(c, mdx + 12, list_y, "No sealed notes yet.", slate, 1, tw);
        }
        draw_text_clipped(c, mdx + 12, mdy + mh - 14,
                          "Target: /mnt/zoe-state/nick_drawer.json (flock+fsync)", slate, 1, tw);

        if (show_kbd) {
            int ky = mdy + mh + 10;
            app->kbd_rect = (Rect){mdx, ky, mw, kbd_h};
            draw_gem_window_themed(c, th, mdx, ky, mw, kbd_h, "PIXEL TOUCH KEYBOARD [QWERTY]", 0, 1);
            const char *rows[4] = {"1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM.-"};
            int ix = mdx + 8;
            int iy = ky + 24;
            int iw = mw - 16;
            int ih = kbd_h - 30;
            int gap = 4;
            int rh = ZOE_MAX(22, (ih - 4 * gap) / 5);
            uint32_t tab_bg = pack_c(c, th->tab_act_bg);
            uint32_t tab_fg = pack_c(c, th->tab_act_fg);
            uint32_t hov_bg = pack_c(c, th->tab_inact_bg);

            for (int r_i = 0; r_i < 4; r_i++) {
                int nkeys = (int)strlen(rows[r_i]);
                int kw_k = (iw - (nkeys - 1) * gap) / nkeys;
                int row_tot = nkeys * kw_k + (nkeys - 1) * gap;
                int rx0 = ix + (iw - row_tot) / 2;
                int ry0 = iy + r_i * (rh + gap);
                int ksc = (rh >= 34 && kw_k >= 34) ? 2 : 1;
                for (int k_i = 0; k_i < nkeys && app->kbd_count < MAX_TOUCH_KEYS; k_i++) {
                    char kc = rows[r_i][k_i];
                    char disp = (!app->kbd_shift && kc >= 'A' && kc <= 'Z') ? (char)(kc + 32) : kc;
                    TouchKey *tk = &app->kbd_keys[app->kbd_count++];
                    tk->r = (Rect){rx0 + k_i * (kw_k + gap), ry0, kw_k, rh};
                    tk->ch = kc;
                    tk->lbl[0] = disp;
                    tk->lbl[1] = 0;
                    int khov = rect_hit(tk->r, app->mx, app->my);
                    draw_bevel_box(c, th, tk->r.x, tk->r.y, tk->r.w, tk->r.h,
                                   khov ? hov_bg : win_bg, ink, 0);
                    draw_text(c, tk->r.x + (tk->r.w - 6 * ksc) / 2,
                              tk->r.y + (tk->r.h - 7 * ksc) / 2, tk->lbl, ink, ksc);
                }
            }
            int ay0 = iy + 4 * (rh + gap);
            int w_shf = (iw - 3 * gap) * 18 / 100;
            int w_spc = (iw - 3 * gap) * 44 / 100;
            int w_del = (iw - 3 * gap) * 18 / 100;
            int w_sav = iw - 3 * gap - w_shf - w_spc - w_del;
            const char *albls[4] = {app->kbd_shift ? "SHF*" : "SHF", "SPACE", "DEL", "SAVE"};
            const char achs[4] = {1, ' ', '\b', '\r'};
            const int aws[4] = {w_shf, w_spc, w_del, w_sav};
            int ax = ix;
            int asc = (rh >= 34 && w_shf >= 72) ? 2 : 1;
            for (int a_i = 0; a_i < 4 && app->kbd_count < MAX_TOUCH_KEYS; a_i++) {
                TouchKey *tk = &app->kbd_keys[app->kbd_count++];
                tk->r = (Rect){ax, ay0, aws[a_i], rh};
                tk->ch = achs[a_i];
                snprintf(tk->lbl, sizeof(tk->lbl), "%s", albls[a_i]);
                uint32_t bg = (a_i == 3) ? green : ((a_i == 0 && app->kbd_shift) ? tab_bg : win_bg);
                uint32_t fg = (a_i == 3) ? (is_dark_theme(th) ? pill_ink : white_hi)
                                         : ((a_i == 0 && app->kbd_shift) ? tab_fg : ink);
                draw_bevel_box(c, th, tk->r.x, tk->r.y, tk->r.w, tk->r.h, bg, ink, a_i == 0 && app->kbd_shift);
                int lpx = (int)strlen(tk->lbl) * 6 * asc;
                draw_text_clipped(c, tk->r.x + ZOE_MAX(4, (tk->r.w - lpx) / 2),
                                  tk->r.y + (tk->r.h - 7 * asc) / 2, tk->lbl, fg, asc, tk->r.w - 6);
                ax += aws[a_i] + gap;
            }
        }
        (void)st;
    }
}

static void fill_themed_wallpaper(Canvas *dst, const GemTheme *th) {
    uint32_t bg_a = pack_c(dst, th->bg_a);
    uint32_t bg_b = pack_c(dst, th->bg_b);
    for (int y = 0; y < dst->h; y++) {
        uint32_t *row = dst->pix + y * dst->stride;
        if (th->fill_mode == 1) {
            int gy = ((y & 15) == 0);
            for (int x = 0; x < dst->w; x++) {
                row[x] = (gy || (x & 15) == 0) ? bg_b : bg_a;
            }
        } else if (th->fill_mode == 2) {
            for (int x = 0; x < dst->w; x++) {
                row[x] = (((x ^ y) & 3) == 0) ? bg_b : bg_a;
            }
        } else if (th->fill_mode == 3) {
            for (int x = 0; x < dst->w; x++) {
                row[x] = ((((x + y) & 3) == 0) || (((x - y) & 7) == 0)) ? bg_b : bg_a;
            }
        } else {
            for (int x = 0; x < dst->w; x++) {
                row[x] = (((x >> 1) + (y >> 1)) & 1) ? bg_a : bg_b;
            }
        }
    }
}

static void rebuild_bg_cache(Canvas *bg, int w, int h, int bgr, const GemTheme *th) {
    bg->w = w;
    bg->h = h;
    bg->stride = w;
    bg->bgr = bgr;
    fill_themed_wallpaper(bg, th);
}

static void render_desktop(Canvas *c, Canvas *bg_cache, RenderScratch *sc, DesktopApp *app,
                           const BootState *st, int show_cursor) {
    const GemTheme *th = active_theme(app);
    uint32_t ink = pack_c(c, th->win_ink);
    uint32_t foot_bg = pack_c(c, th->foot_bg);
    uint32_t foot_fg = pack_c(c, th->foot_fg);
    uint32_t hi = pack_c(c, th->bevel_hi);

    if (bg_cache && bg_cache->pix) {
        if (app->bg_dirty || bg_cache->w != c->w || bg_cache->h != c->h || bg_cache->bgr != c->bgr) {
            rebuild_bg_cache(bg_cache, c->w, c->h, c->bgr, th);
            app->bg_dirty = 0;
        }
        for (int y = 0; y < c->h; y++) {
            memcpy(c->pix + y * c->stride, bg_cache->pix + y * bg_cache->stride, (size_t)c->w * 4);
        }
    } else {
        fill_themed_wallpaper(c, th);
    }

    draw_menu_bar(c, app, st);

    if (app->mode == MODE_MICRO) {
        render_micro_hud(c, app, st);
    } else if (app->mode == MODE_PORTRAIT) {
        int pad = 10;
        int top = app->menu_h + pad;
        int win_w = c->w - 2 * pad;
        int usable_h = c->h - top - app->foot_h - 3 * pad;
        int hud_h = 0, art_h = 0, bot_h = 0;
        compute_portrait_heights(usable_h, &hud_h, &art_h, &bot_h);
        int tk_w = ((win_w - pad) * 48) / 100;
        if (tk_w < 214) {
            tk_w = 214;
        }

        render_hud_panel(c, app, st, pad, top, win_w, hud_h);
        draw_artline_panel(c, app, pad, top + hud_h + pad, win_w, art_h, st);
        draw_gem_p32_toolkit(c, app, pad, top + hud_h + pad + art_h + pad, tk_w, bot_h);
        render_portrait_drawer_card(c, app, st);
    } else {
        int pad = (c->w >= 1000) ? 14 : 10;
        int top = app->menu_h + pad;
        int win_h = c->h - top - app->foot_h - pad;
        int left_w = (c->w >= 1000) ? 210 : 172;
        int right_w = (c->w >= 1000) ? 290 : 236;
        int mid_w = c->w - left_w - right_w - pad * 4;
        if (mid_w < 260) {
            left_w = 156;
            right_w = 216;
            mid_w = c->w - left_w - right_w - pad * 4;
        }
        draw_gem_p32_toolkit(c, app, pad, top, left_w, win_h);
        render_hud_panel(c, app, st, pad * 2 + left_w, top, mid_w, win_h);
        draw_artline_panel(c, app, pad * 3 + left_w + mid_w, top, right_w, win_h, st);
    }

    fill_rect(c, 0, c->h - app->foot_h, c->w, app->foot_h, foot_bg);
    draw_line(c, 0, c->h - app->foot_h, c->w - 1, c->h - app->foot_h, ink, 2);
    fill_rect(c, 0, c->h - app->foot_h + 2, c->w, 1, hi);
    char foot[180];
    if (app->status_msg[0]) {
        snprintf(foot, sizeof(foot), "%s", app->status_msg);
    } else if (app->mode == MODE_MICRO) {
        if (c->w >= 300) {
            snprintf(foot, sizeof(foot), "ADVISORY ONLY * clinical=F * sentience=F * 0 TOK");
        } else {
            snprintf(foot, sizeof(foot), "clinical=F sentience=F 0TOK");
        }
    } else {
        snprintf(foot, sizeof(foot),
                 "ZOE-GEM [%s] :: PTR(%d,%d) :: [V]THM [A]MB [S]AVE [D]RAW [H]W [G]UMA [O]FLP [T]SHL",
                 th->key, app->mx, app->my);
    }
    int fty = c->h - app->foot_h + (app->foot_h - 7) / 2;
    draw_text_clipped(c, (app->mode == MODE_MICRO) ? 4 : 12, fty, foot, foot_fg, 1, c->w - 16);

    render_modals(c, app, st);

    if (show_cursor) {
        draw_cursor(c, app->mx, app->my, pal_col(c, app->active_color), app->amber_crt);
    }
    if (app->amber_crt && sc) {
        apply_amber_crt_filter(c, sc);
    }
}

/* ---------------- Physical <-> Logical Rotation & Cursor Fast-Path ---------------- */

static void sync_log_from_phys(DesktopApp *app) {
    if (app->orient_rot == 0) {
        app->mx = ZOE_CLAMP(app->phys_mx, 0, ZOE_MAX(0, app->log_w - 1));
        app->my = ZOE_CLAMP(app->phys_my, 0, ZOE_MAX(0, app->log_h - 1));
    } else {
        app->mx = ZOE_CLAMP((app->phys_h - 1) - app->phys_my, 0, ZOE_MAX(0, app->log_w - 1));
        app->my = ZOE_CLAMP(app->phys_mx, 0, ZOE_MAX(0, app->log_h - 1));
    }
}

static void sync_phys_from_log(DesktopApp *app) {
    if (app->orient_rot == 0) {
        app->phys_mx = ZOE_CLAMP(app->mx, 0, ZOE_MAX(0, app->phys_w - 1));
        app->phys_my = ZOE_CLAMP(app->my, 0, ZOE_MAX(0, app->phys_h - 1));
    } else {
        app->phys_mx = ZOE_CLAMP(app->my, 0, ZOE_MAX(0, app->phys_w - 1));
        app->phys_my = ZOE_CLAMP((app->phys_h - 1) - app->mx, 0, ZOE_MAX(0, app->phys_h - 1));
    }
}

static void toggle_orientation(DesktopApp *app, Canvas *back) {
    int old_vw = app->vw;
    int old_vh = app->vh;
    app->orient_rot ^= 1;
    app->log_w = app->orient_rot ? app->phys_h : app->phys_w;
    app->log_h = app->orient_rot ? app->phys_w : app->phys_h;
    if (back) {
        back->w = app->log_w;
        back->h = app->log_h;
        back->stride = app->log_w;
    }
    compute_layout(app);
    rescale_strokes(app, old_vw, old_vh);
    sync_log_from_phys(app);
    app->bg_dirty = 1;
    snprintf(app->status_msg, sizeof(app->status_msg),
             "ORIENTATION: %s (%dx%d)",
             app->orient_rot ? "ROTATED 90" : "NATIVE", app->log_w, app->log_h);
}

static void blit_back_to_fb(Canvas *fb, const Canvas *back, int orient_rot) {
    if (orient_rot == 0) {
        for (int py = 0; py < fb->h; py++) {
            memcpy(fb->pix + py * fb->stride, back->pix + py * back->stride, (size_t)fb->w * 4);
        }
    } else {
        for (int py = 0; py < fb->h; py++) {
            uint32_t *dst = fb->pix + py * fb->stride;
            int lx = (fb->h - 1) - py;
            for (int px = 0; px < fb->w; px++) {
                dst[px] = back->pix[px * back->stride + lx];
            }
        }
    }
}

static void blit_cursor_restore_fb(Canvas *fb, const Canvas *back, int orient_rot, int old_px, int old_py) {
    for (int r = 0; r < 16; r++) {
        for (int col = 0; col < 16; col++) {
            int px = orient_rot ? (old_px + r) : (old_px + col);
            int py = orient_rot ? (old_py - col) : (old_py + r);
            if (px < 0 || px >= fb->w || py < 0 || py >= fb->h) {
                continue;
            }
            if (orient_rot == 0) {
                fb->pix[py * fb->stride + px] = back->pix[py * back->stride + px];
            } else {
                int lx = (fb->h - 1) - py;
                int ly = px;
                fb->pix[py * fb->stride + px] = back->pix[ly * back->stride + lx];
            }
        }
    }
}

/* ---------------- Pointer Hit-Testing & Modal Guards ---------------- */

static int hover_zone_id(const DesktopApp *app, int x, int y) {
    if (y <= app->menu_h) {
        for (int i = 0; i < app->menu_count; i++) {
            const MenuItem *mi = &app->menus[i];
            if (x >= mi->x0 && x < mi->x1 && y >= mi->y0 && y < mi->y1) {
                return 100 + i;
            }
        }
    }
    if (rect_hit(app->uma_btn, x, y)) {
        return 200;
    }
    if (rect_hit(app->amber_btn, x, y)) {
        return 201;
    }
    if (rect_hit(app->theme_btn, x, y)) {
        return 202;
    }
    for (int i = 0; i < 8; i++) {
        if (x >= app->sw_x[i] && x < app->sw_x[i] + app->sw_w &&
            y >= app->sw_y[i] && y < app->sw_y[i] + app->sw_h) {
            return 300 + i;
        }
    }
    for (int i = 0; i < 3; i++) {
        if (rect_hit(app->thick_btns[i], x, y)) {
            return 400 + i;
        }
    }
    for (int i = 0; i < 6; i++) {
        if (rect_hit(app->art_tools[i], x, y)) {
            return 500 + i;
        }
    }
    return 0;
}

static void execute_menu_action(DesktopApp *app, BootState *st, Canvas *back, int action) {
    if (action == 0) {
        app->about_modal = 1;
    } else if (action == 1) {
        app->mirror_on = !app->mirror_on;
        snprintf(app->status_msg, sizeof(app->status_msg),
                 "ARTLINE BILATERAL MIRROR: %s", app->mirror_on ? "ON" : "OFF");
    } else if (action == 2) {
        push_undo(app);
        app->stroke_count = 0;
        app->strokes_full = 0;
        snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE CANVAS CLEARED");
    } else if (action == 3) {
        save_live_canvas_svg(app, "/mnt/zoe-state/artline/live_canvas.svg");
        snprintf(app->status_msg, sizeof(app->status_msg),
                 "SAVED live_canvas.svg (%d strokes) TO DISK!", app->stroke_count);
        printf("ZOE_OS_CANVAS_SAVED strokes=%d\n", app->stroke_count);
        fflush(stdout);
    } else if (action == 4) {
        app->drawer_modal = 1;
        app->drawer_len = 0;
        app->drawer_buf[0] = 0;
        app->drawer_scroll = 0;
        snprintf(app->status_msg, sizeof(app->status_msg), "DRAWER COMPOSER OPEN (TYPE + ENTER)");
    } else if (action == 5) {
        load_hw_observation("/mnt/zoe-state/hw_observation.json", st, &app->hw_obs);
        app->hw_modal = 1;
    } else if (action == 6) {
        toggle_orientation(app, back);
    } else if (action == 7) {
        app->request_exit = 1;
    } else if (action == 8) {
        app->request_exit = 3;
    } else if (action == 9) {
        trigger_uma_toggle(app);
    }
}

static void handle_left_press(DesktopApp *app, BootState *st, Canvas *back) {
    int x = app->mx, y = app->my;

    /* Modal click-through guards (NEVER leak clicks to controls behind modals!) */
    if (app->about_modal) {
        app->about_modal = 0;
        app->drawing_active = 0;
        app->modal_dismiss_hold = 1;
        return;
    }
    if (app->hw_modal) {
        app->hw_modal = 0;
        app->drawing_active = 0;
        app->modal_dismiss_hold = 1;
        return;
    }
    if (app->drawer_modal) {
        for (int i = 0; i < app->kbd_count; i++) {
            if (rect_hit(app->kbd_keys[i].r, x, y)) {
                char kc = app->kbd_keys[i].ch;
                if (kc == 1) {
                    app->kbd_shift = !app->kbd_shift;
                } else if (kc == '\b') {
                    if (app->drawer_len > 0) {
                        app->drawer_buf[--app->drawer_len] = 0;
                    }
                } else if (kc == '\r') {
                    if (app->drawer_len > 0) {
                        append_drawer_note_path(app, st, "/mnt/zoe-state/nick_drawer.json", app->drawer_buf);
                        snprintf(app->status_msg, sizeof(app->status_msg), "SEALED NOTE TO NICK'S HARDWARE DRAWER!");
                    }
                    app->drawer_modal = 0;
                    app->drawing_active = 0;
                    app->modal_dismiss_hold = 1;
                } else if (app->drawer_len < 88) {
                    char out_c = (!app->kbd_shift && kc >= 'A' && kc <= 'Z') ? (char)(kc + 32) : kc;
                    app->drawer_buf[app->drawer_len++] = out_c;
                    app->drawer_buf[app->drawer_len] = 0;
                }
                return;
            }
        }
        if (rect_hit(app->modal_save_btn, x, y)) {
            if (app->drawer_len > 0) {
                append_drawer_note_path(app, st, "/mnt/zoe-state/nick_drawer.json", app->drawer_buf);
                snprintf(app->status_msg, sizeof(app->status_msg), "SEALED NOTE TO NICK'S HARDWARE DRAWER!");
            }
            app->drawer_modal = 0;
            app->drawing_active = 0;
            app->modal_dismiss_hold = 1;
        } else if (rect_hit(app->modal_cancel_btn, x, y) ||
                   (!rect_hit(app->modal_rect, x, y) && !rect_hit(app->kbd_rect, x, y))) {
            app->drawer_modal = 0;
            app->drawing_active = 0;
            app->modal_dismiss_hold = 1;
        }
        return;
    }

    if (rect_hit(app->uma_btn, x, y)) {
        trigger_uma_toggle(app);
        return;
    }
    if (rect_hit(app->amber_btn, x, y)) {
        app->amber_crt = !app->amber_crt;
        snprintf(app->status_msg, sizeof(app->status_msg), "DISPLAY PALETTE: %s",
                 app->amber_crt ? "1985 AMBER PHOSPHOR CRT" : active_theme(app)->name);
        return;
    }
    if (rect_hit(app->theme_btn, x, y) || (x >= 6 && x < 24 && y >= 4 && y < 24)) {
        cycle_sovereign_theme(app);
        return;
    }
    if (y <= app->menu_h) {
        for (int i = 0; i < app->menu_count; i++) {
            MenuItem *mi = &app->menus[i];
            if (x >= mi->x0 && x < mi->x1 && y >= mi->y0 && y < mi->y1) {
                execute_menu_action(app, st, back, mi->action);
                return;
            }
        }
        return;
    }
    for (int i = 0; i < 8; i++) {
        if (x >= app->sw_x[i] && x < app->sw_x[i] + app->sw_w &&
            y >= app->sw_y[i] && y < app->sw_y[i] + app->sw_h) {
            app->active_color = i;
            snprintf(app->status_msg, sizeof(app->status_msg),
                     "GEM TOOLKIT PEN COLOR -> #%d (%s)", i, PAL_HEX[i]);
            return;
        }
    }
    for (int i = 0; i < 3; i++) {
        if (rect_hit(app->thick_btns[i], x, y)) {
            const int th[3] = {1, 3, 5};
            app->pen_thick = th[i];
            snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE PEN THICKNESS -> %dPX", app->pen_thick);
            return;
        }
    }
    for (int i = 0; i < 6; i++) {
        if (rect_hit(app->art_tools[i], x, y)) {
            if (i == 0) {
                execute_menu_action(app, st, back, 1);
            } else if (i == 1) {
                stamp_mandala(app);
            } else if (i == 2) {
                if (app->undo_top > 0) {
                    app->stroke_count = app->undo_stack[--app->undo_top];
                    app->strokes_full = 0;
                    snprintf(app->status_msg, sizeof(app->status_msg),
                             "ARTLINE UNDO -> %d STROKES", app->stroke_count);
                }
            } else if (i == 3) {
                app->pen_thick = (app->pen_thick == 1) ? 3 : ((app->pen_thick == 3) ? 5 : 1);
                snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE PEN THICKNESS -> %dPX", app->pen_thick);
            } else if (i == 4) {
                execute_menu_action(app, st, back, 3);
            } else if (i == 5) {
                execute_menu_action(app, st, back, 2);
            }
            return;
        }
    }
    if (rect_hit(app->hw_row_btn, x, y)) {
        execute_menu_action(app, st, back, 5);
        return;
    }
    if (rect_hit(app->drawer_card, x, y)) {
        execute_menu_action(app, st, back, 4);
        return;
    }
    if (x >= app->vx && x < app->vx + app->vw && y >= app->vy && y < app->vy + app->vh) {
        int nx = x - app->vx, ny = y - app->vy;
        push_undo(app);
        app->drawing_active = 1;
        app->draw_prev_x = nx;
        app->draw_prev_y = ny;
        add_stroke(app, nx, ny, nx, ny);
    }
}

static void handle_pointer_move(DesktopApp *app) {
    if (app->about_modal || app->hw_modal || app->drawer_modal) {
        app->drawing_active = 0;
        return;
    }
    if (!app->left_down) {
        app->drawing_active = 0;
        app->modal_dismiss_hold = 0;
        return;
    }
    if (app->modal_dismiss_hold) {
        app->drawing_active = 0;
        return;
    }
    if (app->mx >= app->vx && app->mx < app->vx + app->vw &&
        app->my >= app->vy && app->my < app->vy + app->vh) {
        int nx = app->mx - app->vx, ny = app->my - app->vy;
        if (!app->drawing_active) {
            push_undo(app);
            app->drawing_active = 1;
            app->draw_prev_x = nx;
            app->draw_prev_y = ny;
        } else if (nx != app->draw_prev_x || ny != app->draw_prev_y) {
            add_stroke(app, app->draw_prev_x, app->draw_prev_y, nx, ny);
            app->draw_prev_x = nx;
            app->draw_prev_y = ny;
        }
    }
}

/* ---------------- VT Escape State Machine & Keyboard Dispatch ---------------- */

static long long elapsed_ms(const struct timespec *a, const struct timespec *b) {
    return (long long)(b->tv_sec - a->tv_sec) * 1000LL + (long long)(b->tv_nsec - a->tv_nsec) / 1000000LL;
}

static void vt_parser_init(VtEscParser *p) {
    memset(p, 0, sizeof(*p));
    p->state = VT_GROUND;
}

static VtKeyEvent vt_parser_feed(VtEscParser *p, unsigned char ch, const struct timespec *now) {
    VtKeyEvent ev = {VKEY_NONE, 0};

    if (p->state == VT_ESC) {
        if (ch == '[') {
            p->state = VT_CSI;
            p->state_ts = *now;
            p->csi_len = 0;
            p->csi_buf[0] = 0;
            return ev;
        }
        if (ch == 'O') {
            p->state = VT_SS3;
            p->state_ts = *now;
            return ev;
        }
        if (ch == 0x1B) {
            p->state_ts = *now;
            ev.kind = VKEY_ESC;
            return ev;
        }
        /* Alt+key or unrecognized escape byte: swallow cleanly without leaking */
        p->state = VT_GROUND;
        return ev;
    }

    if (p->state == VT_CSI) {
        if (ch == '[' && p->csi_len == 0) {
            p->state = VT_CSI_LINUX;
            p->state_ts = *now;
            return ev;
        }
        if (ch >= 0x20 && ch <= 0x3F) {
            if (p->csi_len < (int)sizeof(p->csi_buf) - 1) {
                p->csi_buf[p->csi_len++] = (char)ch;
                p->csi_buf[p->csi_len] = 0;
            }
            return ev;
        }
        if (ch >= 0x40 && ch <= 0x7E) {
            p->state = VT_GROUND;
            if (ch == 'A') {
                ev.kind = VKEY_UP;
            } else if (ch == 'B') {
                ev.kind = VKEY_DOWN;
            } else if (ch == 'C') {
                ev.kind = VKEY_RIGHT;
            } else if (ch == 'D') {
                ev.kind = VKEY_LEFT;
            } else if (ch == 'H') {
                ev.kind = VKEY_HOME;
            } else if (ch == 'F') {
                ev.kind = VKEY_END;
            } else if (ch == 'P' || ch == 'Q' || ch == 'R' || ch == 'S') {
                ev.kind = VKEY_FN;
            } else if (ch == '~') {
                int code = atoi(p->csi_buf);
                if (code == 1 || code == 7) {
                    ev.kind = VKEY_HOME;
                } else if (code == 3) {
                    ev.kind = VKEY_DEL;
                } else if (code == 4 || code == 8) {
                    ev.kind = VKEY_END;
                } else if (code == 5) {
                    ev.kind = VKEY_PGUP;
                } else if (code == 6) {
                    ev.kind = VKEY_PGDN;
                } else if (code >= 11 && code <= 24) {
                    ev.kind = VKEY_FN;
                }
            }
            return ev;
        }
        p->state = VT_GROUND;
        if (ch == 0x1B) {
            p->state = VT_ESC;
            p->state_ts = *now;
        }
        return ev;
    }

    if (p->state == VT_CSI_LINUX) {
        p->state = VT_GROUND;
        if (ch >= 'A' && ch <= 'E') {
            ev.kind = VKEY_FN;
        }
        return ev;
    }

    if (p->state == VT_SS3) {
        p->state = VT_GROUND;
        if (ch == 'A') {
            ev.kind = VKEY_UP;
        } else if (ch == 'B') {
            ev.kind = VKEY_DOWN;
        } else if (ch == 'C') {
            ev.kind = VKEY_RIGHT;
        } else if (ch == 'D') {
            ev.kind = VKEY_LEFT;
        } else if (ch == 'H') {
            ev.kind = VKEY_HOME;
        } else if (ch == 'F') {
            ev.kind = VKEY_END;
        } else if (ch >= 'P' && ch <= 'S') {
            ev.kind = VKEY_FN;
        }
        return ev;
    }

    /* VT_GROUND */
    if (ch == 0x1B) {
        p->state = VT_ESC;
        p->state_ts = *now;
    } else if (ch == 0x03) {
        ev.kind = VKEY_CTRL_C;
    } else if (ch == 0x12) {
        ev.kind = VKEY_CTRL_R;
    } else if (ch == '\r' || ch == '\n') {
        ev.kind = VKEY_ENTER;
    } else if (ch == 127 || ch == '\b') {
        ev.kind = VKEY_BACKSPACE;
    } else if (ch >= 32 && ch <= 126) {
        ev.kind = VKEY_CHAR;
        ev.ch = (char)ch;
    }
    return ev;
}

static VtKeyEvent vt_parser_tick(VtEscParser *p, const struct timespec *now) {
    VtKeyEvent ev = {VKEY_NONE, 0};
    if (p->state == VT_ESC && elapsed_ms(&p->state_ts, now) >= 50) {
        p->state = VT_GROUND;
        ev.kind = VKEY_ESC;
    } else if ((p->state == VT_CSI || p->state == VT_CSI_LINUX || p->state == VT_SS3) &&
               elapsed_ms(&p->state_ts, now) >= 200) {
        p->state = VT_GROUND;
    }
    return ev;
}

static void handle_vt_key(DesktopApp *app, BootState *st, Canvas *back, const VtKeyEvent *ev, int *dirty) {
    if (ev->kind == VKEY_NONE) {
        return;
    }
    if (ev->kind == VKEY_CTRL_C) {
        app->request_exit = 1;
        *dirty = 1;
        return;
    }
    if (ev->kind == VKEY_CTRL_R) {
        app->request_exit = 2;
        *dirty = 1;
        return;
    }

    if (app->about_modal) {
        if (ev->kind == VKEY_ESC || ev->kind == VKEY_ENTER || (ev->kind == VKEY_CHAR && ev->ch == ' ')) {
            app->about_modal = 0;
            *dirty = 1;
        }
        return;
    }
    if (app->hw_modal) {
        if (ev->kind == VKEY_ESC || ev->kind == VKEY_ENTER ||
            (ev->kind == VKEY_CHAR && (ev->ch == ' ' || ev->ch == 'h' || ev->ch == 'H'))) {
            app->hw_modal = 0;
            *dirty = 1;
        }
        return;
    }
    if (app->drawer_modal) {
        if (ev->kind == VKEY_ESC) {
            app->drawer_modal = 0;
            *dirty = 1;
        } else if (ev->kind == VKEY_ENTER) {
            if (app->drawer_len > 0) {
                append_drawer_note_path(app, st, "/mnt/zoe-state/nick_drawer.json", app->drawer_buf);
                snprintf(app->status_msg, sizeof(app->status_msg), "SEALED NOTE TO NICK'S HARDWARE DRAWER!");
            }
            app->drawer_modal = 0;
            *dirty = 1;
        } else if (ev->kind == VKEY_BACKSPACE) {
            if (app->drawer_len > 0) {
                app->drawer_buf[--app->drawer_len] = 0;
                *dirty = 1;
            }
        } else if (ev->kind == VKEY_UP || ev->kind == VKEY_PGUP) {
            if (app->drawer_scroll > 0) {
                app->drawer_scroll--;
                *dirty = 1;
            }
        } else if (ev->kind == VKEY_DOWN || ev->kind == VKEY_PGDN) {
            app->drawer_scroll++;
            *dirty = 1;
        } else if (ev->kind == VKEY_CHAR && app->drawer_len < 88) {
            app->drawer_buf[app->drawer_len++] = ev->ch;
            app->drawer_buf[app->drawer_len] = 0;
            *dirty = 1;
        }
        return;
    }

    /* Desktop active */
    if (ev->kind == VKEY_ESC) {
        app->drawing_active = 0;
        app->status_msg[0] = 0;
        *dirty = 1;
        return;
    }
    if (ev->kind == VKEY_UP || ev->kind == VKEY_DOWN || ev->kind == VKEY_LEFT || ev->kind == VKEY_RIGHT) {
        int step = 8;
        if (ev->kind == VKEY_UP) {
            app->my -= step;
        } else if (ev->kind == VKEY_DOWN) {
            app->my += step;
        } else if (ev->kind == VKEY_LEFT) {
            app->mx -= step;
        } else if (ev->kind == VKEY_RIGHT) {
            app->mx += step;
        }
        app->mx = ZOE_CLAMP(app->mx, 0, ZOE_MAX(0, app->log_w - 1));
        app->my = ZOE_CLAMP(app->my, 0, ZOE_MAX(0, app->log_h - 1));
        sync_phys_from_log(app);
        *dirty = 1;
        return;
    }
    if (ev->kind == VKEY_HOME) {
        app->mx = app->log_w / 2;
        app->my = app->log_h / 2;
        sync_phys_from_log(app);
        *dirty = 1;
        return;
    }
    if (ev->kind != VKEY_CHAR) {
        return;
    }

    char ch = ev->ch;
    if (ch >= '0' && ch <= '7') {
        app->active_color = ch - '0';
        snprintf(app->status_msg, sizeof(app->status_msg), "GEM TOOLKIT PEN COLOR -> #%d", app->active_color);
    } else if (ch == 'a' || ch == 'A') {
        app->amber_crt = !app->amber_crt;
        snprintf(app->status_msg, sizeof(app->status_msg), "DISPLAY PALETTE: %s",
                 app->amber_crt ? "1985 AMBER PHOSPHOR CRT" : active_theme(app)->name);
    } else if (ch == 'v' || ch == 'V') {
        cycle_sovereign_theme(app);
    } else if (ch == 'o' || ch == 'O') {
        toggle_orientation(app, back);
    } else if (ch == 'm' || ch == 'M') {
        app->mirror_on = !app->mirror_on;
        snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE BILATERAL MIRROR: %s",
                 app->mirror_on ? "ON" : "OFF");
    } else if (ch == 'b' || ch == 'B') {
        app->pen_thick = (app->pen_thick == 1) ? 3 : ((app->pen_thick == 3) ? 5 : 1);
        snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE PEN THICKNESS -> %dPX", app->pen_thick);
    } else if (ch == 'z' || ch == 'Z') {
        if (app->undo_top > 0) {
            app->stroke_count = app->undo_stack[--app->undo_top];
            app->strokes_full = 0;
            snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE UNDO -> %d STROKES", app->stroke_count);
        }
    } else if (ch == 'r' || ch == 'R') {
        stamp_mandala(app);
    } else if (ch == 'c' || ch == 'C') {
        push_undo(app);
        app->stroke_count = 0;
        app->strokes_full = 0;
        snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE CANVAS CLEARED");
    } else if (ch == 's' || ch == 'S') {
        save_live_canvas_svg(app, "/mnt/zoe-state/artline/live_canvas.svg");
        snprintf(app->status_msg, sizeof(app->status_msg),
                 "SAVED live_canvas.svg (%d strokes) TO DISK!", app->stroke_count);
        printf("ZOE_OS_CANVAS_SAVED strokes=%d\n", app->stroke_count);
        fflush(stdout);
    } else if (ch == 'd' || ch == 'D') {
        app->drawer_modal = 1;
        app->drawer_len = 0;
        app->drawer_buf[0] = 0;
        app->drawer_scroll = 0;
    } else if (ch == 'h' || ch == 'H') {
        load_hw_observation("/mnt/zoe-state/hw_observation.json", st, &app->hw_obs);
        app->hw_modal = 1;
    } else if (ch == 'g' || ch == 'G') {
        trigger_uma_toggle(app);
    } else if (ch == 't' || ch == 'T') {
        app->request_exit = 1;
    } else if (ch == 'q' || ch == 'Q') {
        app->request_exit = 3;
    }
    *dirty = 1;
}

/* ---------------- evdev Packet Coalescing, Multitouch & Hotplug ---------------- */

static void reset_evdev_pkt(EvDev *d) {
    d->pkt_has_abs_x = 0;
    d->pkt_has_abs_y = 0;
    d->pkt_has_mt_x = 0;
    d->pkt_has_mt_y = 0;
    d->pkt_has_mt_track = 0;
    d->pkt_rel_dx = 0;
    d->pkt_rel_dy = 0;
    d->pkt_has_btn = 0;
    d->pkt_btn_right = 0;
}

static void process_evdev_event(EvDev *d, const struct input_event *ev, DesktopApp *app,
                                BootState *st, Canvas *back, int *dirty, int *cursor_only) {
    if (ev->type == EV_ABS) {
        if (ev->code == ABS_X && d->has_abs) {
            d->pkt_has_abs_x = 1;
            d->pkt_abs_x = ev->value;
        } else if (ev->code == ABS_Y && d->has_abs) {
            d->pkt_has_abs_y = 1;
            d->pkt_abs_y = ev->value;
        } else if (ev->code == ABS_MT_SLOT) {
            d->pkt_mt_slot = ev->value;
        } else if (d->pkt_mt_slot == 0 && d->has_mt) {
            if (ev->code == ABS_MT_POSITION_X) {
                d->pkt_has_mt_x = 1;
                d->pkt_mt_x = ev->value;
            } else if (ev->code == ABS_MT_POSITION_Y) {
                d->pkt_has_mt_y = 1;
                d->pkt_mt_y = ev->value;
            } else if (ev->code == ABS_MT_TRACKING_ID) {
                d->pkt_has_mt_track = 1;
                d->pkt_mt_down = (ev->value >= 0) ? 1 : 0;
            }
        }
    } else if (ev->type == EV_REL) {
        if (ev->code == REL_X) {
            d->pkt_rel_dx += ev->value;
        } else if (ev->code == REL_Y) {
            d->pkt_rel_dy += ev->value;
        }
    } else if (ev->type == EV_KEY) {
        if (ev->code == BTN_LEFT || ev->code == BTN_TOUCH) {
            d->pkt_has_btn = 1;
            d->pkt_btn_val = ev->value ? 1 : 0;
        } else if (ev->code == BTN_RIGHT && ev->value == 1) {
            d->pkt_btn_right = 1;
        }
    } else if (ev->type == EV_SYN) {
        if (ev->code == SYN_DROPPED) {
            reset_evdev_pkt(d);
            if (d->fd >= 0 && d->has_abs) {
                struct input_absinfo ax = {0}, ay = {0};
                if (ioctl(d->fd, EVIOCGABS(ABS_X), &ax) == 0 && ioctl(d->fd, EVIOCGABS(ABS_Y), &ay) == 0) {
                    long sx = d->abs_max_x - d->abs_min_x;
                    long sy = d->abs_max_y - d->abs_min_y;
                    if (sx > 0 && sy > 0) {
                        app->phys_mx = ZOE_CLAMP((int)((long long)(ax.value - d->abs_min_x) * (app->phys_w - 1) / sx),
                                                 0, app->phys_w - 1);
                        app->phys_my = ZOE_CLAMP((int)((long long)(ay.value - d->abs_min_y) * (app->phys_h - 1) / sy),
                                                 0, app->phys_h - 1);
                        sync_log_from_phys(app);
                        *dirty = 1;
                    }
                }
            }
            return;
        }
        if (ev->code == SYN_REPORT) {
            int old_lx = app->mx, old_ly = app->my;
            if (d->pkt_has_abs_x || d->pkt_has_abs_y || d->pkt_has_mt_x || d->pkt_has_mt_y) {
                int new_px = app->phys_mx;
                int new_py = app->phys_my;
                if (d->pkt_has_abs_x && d->abs_max_x > d->abs_min_x) {
                    long span = d->abs_max_x - d->abs_min_x;
                    new_px = (int)((long long)(d->pkt_abs_x - d->abs_min_x) * (app->phys_w - 1) / span);
                } else if (d->pkt_has_mt_x && d->mt_max_x > d->mt_min_x) {
                    long span = d->mt_max_x - d->mt_min_x;
                    new_px = (int)((long long)(d->pkt_mt_x - d->mt_min_x) * (app->phys_w - 1) / span);
                }
                if (d->pkt_has_abs_y && d->abs_max_y > d->abs_min_y) {
                    long span = d->abs_max_y - d->abs_min_y;
                    new_py = (int)((long long)(d->pkt_abs_y - d->abs_min_y) * (app->phys_h - 1) / span);
                } else if (d->pkt_has_mt_y && d->mt_max_y > d->mt_min_y) {
                    long span = d->mt_max_y - d->mt_min_y;
                    new_py = (int)((long long)(d->pkt_mt_y - d->mt_min_y) * (app->phys_h - 1) / span);
                }
                app->phys_mx = ZOE_CLAMP(new_px, 0, ZOE_MAX(0, app->phys_w - 1));
                app->phys_my = ZOE_CLAMP(new_py, 0, ZOE_MAX(0, app->phys_h - 1));
                sync_log_from_phys(app);
            } else if (d->pkt_rel_dx != 0 || d->pkt_rel_dy != 0) {
                int dlx = (app->orient_rot == 0) ? d->pkt_rel_dx : -d->pkt_rel_dy;
                int dly = (app->orient_rot == 0) ? d->pkt_rel_dy :  d->pkt_rel_dx;
                app->mx = ZOE_CLAMP(app->mx + dlx, 0, ZOE_MAX(0, app->log_w - 1));
                app->my = ZOE_CLAMP(app->my + dly, 0, ZOE_MAX(0, app->log_h - 1));
                sync_phys_from_log(app);
            }

            int moved = (app->mx != old_lx || app->my != old_ly);
            int new_down = d->pkt_has_btn ? d->pkt_btn_val : (d->pkt_has_mt_track ? d->pkt_mt_down : app->left_down);
            app->prev_left = app->left_down;
            app->left_down = new_down;
            if (!app->left_down) {
                app->modal_dismiss_hold = 0;
            }

            if (app->left_down && !app->prev_left) {
                handle_left_press(app, st, back);
                *dirty = 1;
            } else if (!app->left_down && app->prev_left) {
                app->drawing_active = 0;
                app->modal_dismiss_hold = 0;
                *dirty = 1;
            } else if (moved) {
                if (app->left_down) {
                    handle_pointer_move(app);
                    *dirty = 1;
                } else {
                    if (app->mode == MODE_LANDSCAPE && !app->about_modal && !app->hw_modal && !app->drawer_modal &&
                        hover_zone_id(app, old_lx, old_ly) == hover_zone_id(app, app->mx, app->my)) {
                        *cursor_only = 1;
                    } else {
                        *dirty = 1;
                    }
                }
            }

            if (d->pkt_btn_right && !app->about_modal && !app->hw_modal && !app->drawer_modal) {
                app->mirror_on = !app->mirror_on;
                snprintf(app->status_msg, sizeof(app->status_msg),
                         "ARTLINE BILATERAL MIRROR: %s", app->mirror_on ? "ON" : "OFF");
                *dirty = 1;
            }
            reset_evdev_pkt(d);
        }
    }
}

static void rescan_evdev_pointers(EvDev *devs, int *n_ev, int max_devs, int *mice_fd) {
    /* Prune missing or replaced devices */
    for (int i = 0; i < *n_ev; ) {
        char path[40];
        snprintf(path, sizeof(path), "/dev/input/event%d", devs[i].idx);
        struct stat sb;
        if (stat(path, &sb) != 0 || sb.st_rdev != devs[i].rdev) {
            close(devs[i].fd);
            devs[i] = devs[--(*n_ev)];
        } else {
            i++;
        }
    }

    for (int idx = 0; idx < 32 && *n_ev < max_devs; idx++) {
        char path[40];
        snprintf(path, sizeof(path), "/dev/input/event%d", idx);
        struct stat sb;
        if (stat(path, &sb) != 0 || !S_ISCHR(sb.st_mode)) {
            continue;
        }
        int already = 0;
        for (int j = 0; j < *n_ev; j++) {
            if (devs[j].rdev == sb.st_rdev) {
                already = 1;
                break;
            }
        }
        if (already) {
            continue;
        }
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) {
            continue;
        }
        unsigned long evbits[4] = {0};
        if (ioctl(fd, EVIOCGBIT(0, sizeof(evbits)), evbits) < 0) {
            close(fd);
            continue;
        }
        int has_rel = TEST_BIT(evbits, EV_REL);
        int has_abs_bit = TEST_BIT(evbits, EV_ABS);
        if (!has_rel && !has_abs_bit) {
            close(fd);
            continue;
        }

        EvDev d;
        memset(&d, 0, sizeof(d));
        d.fd = fd;
        d.rdev = sb.st_rdev;
        d.idx = idx;
        d.has_rel = has_rel;
        d.abs_max_x = 32767;
        d.abs_max_y = 32767;
        d.mt_max_x = 32767;
        d.mt_max_y = 32767;

        if (has_abs_bit) {
            unsigned long absbits[(ABS_CNT + sizeof(unsigned long) * 8 - 1) / (sizeof(unsigned long) * 8)] = {0};
            if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(absbits)), absbits) >= 0) {
                if (TEST_BIT(absbits, ABS_X) && TEST_BIT(absbits, ABS_Y)) {
                    struct input_absinfo ax = {0}, ay = {0};
                    if (ioctl(fd, EVIOCGABS(ABS_X), &ax) == 0 && ioctl(fd, EVIOCGABS(ABS_Y), &ay) == 0 &&
                        ax.maximum > ax.minimum && ay.maximum > ay.minimum) {
                        d.has_abs = 1;
                        d.abs_min_x = ax.minimum;
                        d.abs_max_x = ax.maximum;
                        d.abs_min_y = ay.minimum;
                        d.abs_max_y = ay.maximum;
                    }
                }
                if (TEST_BIT(absbits, ABS_MT_POSITION_X) && TEST_BIT(absbits, ABS_MT_POSITION_Y)) {
                    struct input_absinfo mx = {0}, my = {0};
                    if (ioctl(fd, EVIOCGABS(ABS_MT_POSITION_X), &mx) == 0 &&
                        ioctl(fd, EVIOCGABS(ABS_MT_POSITION_Y), &my) == 0 &&
                        mx.maximum > mx.minimum && my.maximum > my.minimum) {
                        d.has_mt = 1;
                        d.mt_min_x = mx.minimum;
                        d.mt_max_x = mx.maximum;
                        d.mt_min_y = my.minimum;
                        d.mt_max_y = my.maximum;
                    }
                }
            }
        }
        if (!d.has_rel && !d.has_abs && !d.has_mt) {
            close(fd);
            continue;
        }
        devs[(*n_ev)++] = d;
    }

    if (mice_fd) {
        if (*n_ev > 0 && *mice_fd >= 0) {
            close(*mice_fd);
            *mice_fd = -1;
        } else if (*n_ev == 0 && *mice_fd < 0) {
            *mice_fd = open("/dev/input/mice", O_RDONLY | O_NONBLOCK);
        }
    }
}

/* ---------------- Interactive Main Loop ---------------- */

static void run_interactive_loop(Canvas *fb, Canvas *back, Canvas *bg_cache, RenderScratch *sc,
                                 DesktopApp *app, BootState *st, int autotest_sec) {
    EvDev evdevs[MAX_EVDEVS];
    int n_ev = 0;
    int mice_fd = -1;
    rescan_evdev_pointers(evdevs, &n_ev, MAX_EVDEVS, &mice_fd);

    int tty_fd = open("/dev/tty0", O_RDWR | O_NONBLOCK);
    int kbd_fd = (tty_fd >= 0) ? tty_fd : STDIN_FILENO;
    int kd_switched = 0;
    if (tty_fd >= 0 && ioctl(tty_fd, KDSETMODE, KD_GRAPHICS) == 0) {
        kd_switched = 1;
    }

    struct termios orig_t, raw_t;
    int have_tty = (tcgetattr(kbd_fd, &orig_t) == 0);
    if (have_tty) {
        raw_t = orig_t;
        raw_t.c_lflag &= (tcflag_t)~(ICANON | ECHO | ISIG | IEXTEN);
        raw_t.c_iflag &= (tcflag_t)~(IXON | ICRNL | INLCR | IGNCR);
        raw_t.c_cc[VMIN] = 0;
        raw_t.c_cc[VTIME] = 0;
        tcsetattr(kbd_fd, TCSANOW, &raw_t);
    }
    int flags = fcntl(kbd_fd, F_GETFL, 0);
    if (flags >= 0) {
        fcntl(kbd_fd, F_SETFL, flags | O_NONBLOCK);
    }

    VtEscParser vt;
    vt_parser_init(&vt);
    struct timespec start_ts, last_1s_ts;
    clock_gettime(CLOCK_MONOTONIC, &start_ts);
    last_1s_ts = start_ts;

    int dirty = 1;
    int cursor_only = 0;
    int prev_phys_mx = app->phys_mx;
    int prev_phys_my = app->phys_my;

    while (!app->request_exit) {
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        if (autotest_sec > 0 && (now.tv_sec - start_ts.tv_sec) >= autotest_sec) {
            break;
        }

        /* Reap non-blocking --uma-toggle child if finished */
        if (app->uma_toggle_pid > 0) {
            int wstatus = 0;
            pid_t wr = waitpid(app->uma_toggle_pid, &wstatus, WNOHANG);
            if (wr == app->uma_toggle_pid || (wr < 0 && errno == ECHILD)) {
                app->uma_toggle_pid = 0;
                poll_uma_and_zo3(app, st);
                snprintf(app->status_msg, sizeof(app->status_msg), "UMA GATE -> %s", st->uma_gate);
                dirty = 1;
            }
        }

        /* Periodic ~1s hotplug rescan + live UMA / BAR2 ZO3 poll */
        if (elapsed_ms(&last_1s_ts, &now) >= 1000) {
            last_1s_ts = now;
            rescan_evdev_pointers(evdevs, &n_ev, MAX_EVDEVS, &mice_fd);
            if (poll_uma_and_zo3(app, st)) {
                dirty = 1;
            }
        }

        if (dirty) {
            render_desktop(back, bg_cache, sc, app, st, 0);
            blit_back_to_fb(fb, back, app->orient_rot);
            draw_cursor_oriented(fb, app->phys_mx, app->phys_my, pal_col(fb, app->active_color), app->amber_crt, app->orient_rot);
            prev_phys_mx = app->phys_mx;
            prev_phys_my = app->phys_my;
            dirty = 0;
            cursor_only = 0;
        } else if (cursor_only) {
            blit_cursor_restore_fb(fb, back, app->orient_rot, prev_phys_mx, prev_phys_my);
            draw_cursor_oriented(fb, app->phys_mx, app->phys_my, pal_col(fb, app->active_color), app->amber_crt, app->orient_rot);
            prev_phys_mx = app->phys_mx;
            prev_phys_my = app->phys_my;
            cursor_only = 0;
        }

        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(kbd_fd, &rfds);
        int maxfd = kbd_fd;
        for (int i = 0; i < n_ev; i++) {
            FD_SET(evdevs[i].fd, &rfds);
            if (evdevs[i].fd > maxfd) {
                maxfd = evdevs[i].fd;
            }
        }
        if (mice_fd >= 0) {
            FD_SET(mice_fd, &rfds);
            if (mice_fd > maxfd) {
                maxfd = mice_fd;
            }
        }
        struct timeval tv = {0, 20000};
        int sret = select(maxfd + 1, &rfds, NULL, NULL, &tv);

        clock_gettime(CLOCK_MONOTONIC, &now);
        VtKeyEvent tick_ev = vt_parser_tick(&vt, &now);
        if (tick_ev.kind != VKEY_NONE) {
            handle_vt_key(app, st, back, &tick_ev, &dirty);
        }
        if (sret <= 0) {
            continue;
        }

        for (int i = 0; i < n_ev; ) {
            if (!FD_ISSET(evdevs[i].fd, &rfds)) {
                i++;
                continue;
            }
            struct input_event ev;
            int removed = 0;
            for (;;) {
                ssize_t r = read(evdevs[i].fd, &ev, sizeof(ev));
                if (r == (ssize_t)sizeof(ev)) {
                    process_evdev_event(&evdevs[i], &ev, app, st, back, &dirty, &cursor_only);
                } else if (r < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                    break;
                } else {
                    /* ENODEV / EOF -> remove unplugged device cleanly */
                    close(evdevs[i].fd);
                    evdevs[i] = evdevs[--n_ev];
                    removed = 1;
                    break;
                }
            }
            if (!removed) {
                i++;
            }
        }

        if (mice_fd >= 0 && FD_ISSET(mice_fd, &rfds)) {
            uint8_t pkt[3];
            while (read(mice_fd, pkt, 3) == 3) {
                int old_lx = app->mx, old_ly = app->my;
                int dx = (int)(int8_t)pkt[1];
                int dy = -(int)(int8_t)pkt[2];
                int dlx = (app->orient_rot == 0) ? dx : -dy;
                int dly = (app->orient_rot == 0) ? dy :  dx;
                app->mx = ZOE_CLAMP(app->mx + dlx, 0, ZOE_MAX(0, app->log_w - 1));
                app->my = ZOE_CLAMP(app->my + dly, 0, ZOE_MAX(0, app->log_h - 1));
                sync_phys_from_log(app);
                app->prev_left = app->left_down;
                app->left_down = (pkt[0] & 1) ? 1 : 0;
                if (!app->left_down) {
                    app->modal_dismiss_hold = 0;
                }
                if (app->left_down && !app->prev_left) {
                    handle_left_press(app, st, back);
                    dirty = 1;
                } else {
                    handle_pointer_move(app);
                    if (app->left_down || old_lx != app->mx || old_ly != app->my) {
                        dirty = 1;
                    }
                }
            }
        }

        if (FD_ISSET(kbd_fd, &rfds)) {
            unsigned char kbuf[64];
            ssize_t kn;
            while ((kn = read(kbd_fd, kbuf, sizeof(kbuf))) > 0) {
                clock_gettime(CLOCK_MONOTONIC, &now);
                for (ssize_t k = 0; k < kn; k++) {
                    VtKeyEvent kev = vt_parser_feed(&vt, kbuf[k], &now);
                    if (kev.kind != VKEY_NONE) {
                        handle_vt_key(app, st, back, &kev, &dirty);
                    }
                }
            }
        }
    }

    if (autotest_sec > 0) {
        render_desktop(back, bg_cache, sc, app, st, 0);
        blit_back_to_fb(fb, back, app->orient_rot);
        draw_cursor_oriented(fb, app->phys_mx, app->phys_my, pal_col(fb, app->active_color), app->amber_crt, app->orient_rot);
        printf("ZOE_OS_READY_FOR_CAPTURE\n");
        fflush(stdout);
        sleep(1);
    }

    for (int i = 0; i < n_ev; i++) {
        close(evdevs[i].fd);
    }
    if (mice_fd >= 0) {
        close(mice_fd);
    }
    if (have_tty) {
        tcsetattr(kbd_fd, TCSANOW, &orig_t);
    }
    if (flags >= 0) {
        fcntl(kbd_fd, F_SETFL, flags);
    }
    if (kd_switched && tty_fd >= 0) {
        ioctl(tty_fd, KDSETMODE, KD_TEXT);
        const char *clr = "\033[2J\033[H";
        if (write(tty_fd, clr, strlen(clr)) < 0) {
            /* ignore */
        }
    }
    if (tty_fd >= 0) {
        close(tty_fd);
    }
}

/* ---------------- PPM Export & Entrypoint ---------------- */

static int dump_ppm(const Canvas *c, const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) {
        return 1;
    }
    fprintf(f, "P6\n%d %d\n255\n", c->w, c->h);
    for (int y = 0; y < c->h; y++) {
        for (int x = 0; x < c->w; x++) {
            uint32_t p = c->pix[y * c->stride + x];
            uint8_t rgb[3] = {
                (uint8_t)(c->bgr ? ((p >> 16) & 0xFFu) : (p & 0xFFu)),
                (uint8_t)((p >> 8) & 0xFFu),
                (uint8_t)(c->bgr ? (p & 0xFFu) : ((p >> 16) & 0xFFu)),
            };
            fwrite(rgb, 1, 3, f);
        }
    }
    fclose(f);
    return 0;
}

int main(int argc, char **argv) {
    const char *state_path = "/run/zoe-boot-state.json";
    const char *ppm_out = NULL;
    int interactive = 0;
    int autotest_sec = 0;
    int req_w = 1024;
    int req_h = 768;
    int force_amber = 0;
    int force_portrait = 0;
    int req_theme = -1;
    const char *demo_modal = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--state") == 0 && i + 1 < argc) {
            state_path = argv[++i];
        } else if (strcmp(argv[i], "--dump-ppm") == 0 && i + 1 < argc) {
            ppm_out = argv[++i];
        } else if (strcmp(argv[i], "--interactive") == 0) {
            interactive = 1;
        } else if (strcmp(argv[i], "--autotest-sec") == 0 && i + 1 < argc) {
            interactive = 1;
            autotest_sec = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--size") == 0 && i + 1 < argc) {
            int pw = 0, ph = 0;
            if (sscanf(argv[++i], "%dx%d", &pw, &ph) == 2 && pw >= 160 && ph >= 160) {
                req_w = ZOE_CLAMP(pw, 160, 4096);
                req_h = ZOE_CLAMP(ph, 160, 4096);
            }
        } else if (strcmp(argv[i], "--amber") == 0) {
            force_amber = 1;
        } else if (strcmp(argv[i], "--theme") == 0 && i + 1 < argc) {
            const char *t_arg = argv[++i];
            if (eq_ci(t_arg, "amber")) {
                force_amber = 1;
            } else {
                int tidx = resolve_theme_arg(t_arg);
                if (tidx >= 0) {
                    req_theme = tidx;
                }
            }
        } else if (strcmp(argv[i], "--demo-modal") == 0 && i + 1 < argc) {
            demo_modal = argv[++i];
        } else if (strcmp(argv[i], "--portrait") == 0) {
            force_portrait = 1;
        }
    }

    BootState st;
    load_boot_state(state_path, &st);

    DesktopApp app;
    memset(&app, 0, sizeof(app));
    app.active_color = 5;
    app.pen_thick = 3;
    app.mirror_on = 1;
    app.kbd_shift = 1;
    app.amber_crt = (force_amber || strcmp(st.theme, "amber") == 0) ? 1 : 0;
    if (req_theme >= 0) {
        app.theme_idx = req_theme;
    } else {
        int st_tidx = resolve_theme_arg(st.theme);
        if (st_tidx >= 0) {
            app.theme_idx = st_tidx;
        }
    }
    if (demo_modal) {
        if (eq_ci(demo_modal, "about")) {
            app.about_modal = 1;
        } else if (eq_ci(demo_modal, "hw")) {
            app.hw_modal = 1;
        } else if (eq_ci(demo_modal, "drawer")) {
            app.drawer_modal = 1;
            snprintf(app.drawer_buf, sizeof(app.drawer_buf), "Pixel 7 Panther Sovereign!");
            app.drawer_len = (int)strlen(app.drawer_buf);
        }
    }
    app.bg_dirty = 1;

    load_hw_observation("/mnt/zoe-state/hw_observation.json", &st, &app.hw_obs);
    load_drawer_notes_path(&app, &st, "/mnt/zoe-state/nick_drawer.json");
    poll_uma_and_zo3(&app, &st);

    if (ppm_out) {
        app.phys_w = req_w;
        app.phys_h = req_h;
        app.orient_rot = (force_portrait && req_w > req_h) ? 1 : 0;
        app.log_w = app.orient_rot ? req_h : req_w;
        app.log_h = app.orient_rot ? req_w : req_h;
        app.mx = app.log_w / 2;
        app.my = app.log_h / 2;
        sync_phys_from_log(&app);
        compute_layout(&app);
        load_live_canvas_svg(&app, "/mnt/zoe-state/artline/live_canvas.svg");

        Canvas fb = {0};
        fb.w = req_w;
        fb.h = req_h;
        fb.stride = req_w;
        fb.bgr = 1;
        fb.pix = (uint32_t *)calloc((size_t)fb.w * (size_t)fb.h, sizeof(uint32_t));
        Canvas back = {0};
        back.w = app.log_w;
        back.h = app.log_h;
        back.stride = app.log_w;
        back.bgr = 1;
        back.pix = (uint32_t *)calloc((size_t)back.w * (size_t)back.h, sizeof(uint32_t));
        Canvas bg_cache = {0};
        bg_cache.pix = (uint32_t *)calloc((size_t)fb.w * (size_t)fb.h, sizeof(uint32_t));
        RenderScratch sc;
        memset(&sc, 0, sizeof(sc));
        if (!fb.pix || !back.pix || !bg_cache.pix) {
            free(fb.pix);
            free(back.pix);
            free(bg_cache.pix);
            free_scratch(&sc);
            return 1;
        }
        render_desktop(&back, &bg_cache, &sc, &app, &st, 0);
        blit_back_to_fb(&fb, &back, app.orient_rot);
        draw_cursor_oriented(&fb, app.phys_mx, app.phys_my, pal_col(&fb, app.active_color), app.amber_crt, app.orient_rot);
        int rc = dump_ppm(&fb, ppm_out);
        free(fb.pix);
        free(back.pix);
        free(bg_cache.pix);
        free_scratch(&sc);
        return rc;
    }

    const char *fb_dev = getenv("ZOE_FB_DEV");
    if (!fb_dev || !fb_dev[0]) {
        fb_dev = "/dev/fb0";
    }
    int fd = open(fb_dev, O_RDWR);
    if (fd < 0) {
        fprintf(stderr, "zoe_gem_fb: %s unavailable\n", fb_dev);
        return 2;
    }
    struct fb_var_screeninfo vinfo;
    struct fb_fix_screeninfo finfo;
    if (ioctl(fd, FBIOGET_VSCREENINFO, &vinfo) < 0 || ioctl(fd, FBIOGET_FSCREENINFO, &finfo) < 0) {
        close(fd);
        return 3;
    }
    if (vinfo.bits_per_pixel != 32) {
        close(fd);
        return 4;
    }
    size_t map_sz = (size_t)finfo.line_length * (size_t)vinfo.yres;
    void *mem = mmap(NULL, map_sz, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mem == MAP_FAILED) {
        close(fd);
        return 5;
    }

    Canvas fb = {
        (uint32_t *)mem,
        (int)vinfo.xres,
        (int)vinfo.yres,
        (int)(finfo.line_length / 4),
        (vinfo.red.offset >= 16) ? 1 : 0
    };
    app.phys_w = fb.w;
    app.phys_h = fb.h;
    app.orient_rot = (force_portrait && fb.w > fb.h) ? 1 : 0;
    app.log_w = app.orient_rot ? fb.h : fb.w;
    app.log_h = app.orient_rot ? fb.w : fb.h;

    Canvas back = {
        (uint32_t *)calloc((size_t)fb.w * (size_t)fb.h, sizeof(uint32_t)),
        app.log_w,
        app.log_h,
        app.log_w,
        fb.bgr
    };
    Canvas bg_cache = {
        (uint32_t *)calloc((size_t)fb.w * (size_t)fb.h, sizeof(uint32_t)),
        app.log_w,
        app.log_h,
        app.log_w,
        fb.bgr
    };
    RenderScratch sc;
    memset(&sc, 0, sizeof(sc));
    if (!back.pix || !bg_cache.pix) {
        free(back.pix);
        free(bg_cache.pix);
        free_scratch(&sc);
        munmap(mem, map_sz);
        close(fd);
        return 6;
    }

    app.mx = app.log_w / 2;
    app.my = app.log_h / 2;
    sync_phys_from_log(&app);
    compute_layout(&app);
    load_live_canvas_svg(&app, "/mnt/zoe-state/artline/live_canvas.svg");

    render_desktop(&back, &bg_cache, &sc, &app, &st, 0);
    blit_back_to_fb(&fb, &back, app.orient_rot);
    draw_cursor_oriented(&fb, app.phys_mx, app.phys_my, pal_col(&fb, app.active_color), app.amber_crt, app.orient_rot);
    msync(mem, map_sz, MS_SYNC);
    printf("ZOE_OS_FB_OK %dx%d %ubpp interactive=%d\n", fb.w, fb.h, vinfo.bits_per_pixel, interactive);
    fflush(stdout);

    if (interactive) {
        run_interactive_loop(&fb, &back, &bg_cache, &sc, &app, &st, autotest_sec);
    }

    free(back.pix);
    free(bg_cache.pix);
    free_scratch(&sc);
    munmap(mem, map_sz);
    close(fd);
    return app.request_exit;
}
