/*
 * zoe_gem_fb.c — Interactive Hardware Framebuffer (/dev/fb0) Digital Research GEM Desktop.
 *
 * Compiles statically (`gcc -O2 -static -lm`) with zero X11, zero Wayland, zero SDL.
 * Supports:
 *   - Zero-flicker double-buffered rendering directly onto linear hardware /dev/fb0 (32bpp)
 *   - Real hardware PS/2 & USB mouse cursor via `/dev/input/mice` (Zoe 16x16 Atari ST MFORM crystal)
 *   - Real hardware keyboard via raw non-blocking stdin (`termios`)
 *   - Clickable Digital Research GEM p. 3-2 Toolkit (0..7 color swatches)
 *   - Live drawable Artline 2.0 Vector Canvas with Bilateral Mirror Symmetry ([M] toggle)
 *   - Persistent SVG save (`[S]` -> /mnt/zoe-state/artline/live_canvas.svg)
 *   - Inline Nick's `/drawer` GEM Dialog Box (`[D]` -> appends to /mnt/zoe-state/nick_drawer.json)
 *   - Clickable top GEM Menu Bar (`Desk`, `Mirror`, `Clear`, `Save`, `Drawer`, `Shell`, `Power`)
 *   - Headless `--dump-ppm <path>` for unit tests & automated `--interactive --autotest` mode
 */

#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#define MAX_STROKES 512

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
} Stroke;

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
} BootState;

typedef struct {
    int mx, my;
    int left_down;
    int prev_left;
    int draw_prev_x, draw_prev_y;
    int active_color;
    int mirror_on;
    int stroke_count;
    Stroke strokes[MAX_STROKES];
    int drawer_modal;
    char drawer_buf[96];
    int drawer_len;
    char status_msg[128];
    int request_exit;   /* 1=shell, 2=reboot, 3=poweroff */
    /* Cached layout hitboxes */
    int sw_x[8], sw_y[8], sw_w, sw_h;
    int vx, vy, vw, vh;
} DesktopApp;

/* Compact 5x7 geometric font for ASCII 32..126 */
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

/* Zoe's 16x16 Atari ST GEM MFORM Mouse Pointer (hotspot at top-left tip 1,1) */
static const char *ZOE_CURSOR[16] = {
    "XX..............",
    "XOX.............",
    "XOOX............",
    "XOOOX...........",
    "XOOOOX..........",
    "XOOOOOX.........",
    "XOOOOOOX........",
    "XOOOOOOOX.......",
    "XOOOOOOOOX......",
    "XOOOOOXXXX......",
    "XOOXOOX.........",
    "XOX.XOOX........",
    "XX..XOOX........",
    ".....XOOX.......",
    ".....XOOX.......",
    "......XX........",
};

static const uint8_t PAL_RGB[8][3] = {
    {250, 248, 242}, /* 0: Cream/White */
    { 18,  22,  30}, /* 1: Ink Black */
    {230,  57,  86}, /* 2: Zoe Ruby */
    { 34, 197,  94}, /* 3: Emerald */
    { 59, 130, 246}, /* 4: Cobalt */
    { 92, 225, 230}, /* 5: Artline Cyan */
    {245, 158,  11}, /* 6: Amber */
    {217,  70, 239}, /* 7: Magenta */
};

static const char *PAL_HEX[8] = {
    "#faf8f2", "#12161e", "#e63956", "#22c55e",
    "#3b82f6", "#5ce1e6", "#f59e0b", "#d946ef"
};

static inline uint32_t pack_rgb(const Canvas *c, uint8_t r, uint8_t g, uint8_t b) {
    if (c->bgr) return (0xFFu << 24) | ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
    return (0xFFu << 24) | ((uint32_t)b << 16) | ((uint32_t)g << 8) | (uint32_t)r;
}

static inline uint32_t pal_col(const Canvas *c, int idx) {
    if (idx < 0 || idx > 7) idx = 2;
    return pack_rgb(c, PAL_RGB[idx][0], PAL_RGB[idx][1], PAL_RGB[idx][2]);
}

static inline void put_px(Canvas *c, int x, int y, uint32_t col) {
    if (x >= 0 && x < c->w && y >= 0 && y < c->h) c->pix[y * c->stride + x] = col;
}

static void fill_rect(Canvas *c, int x, int y, int w, int h, uint32_t col) {
    int x0 = x < 0 ? 0 : x, y0 = y < 0 ? 0 : y;
    int x1 = (x + w) > c->w ? c->w : (x + w);
    int y1 = (y + h) > c->h ? c->h : (y + h);
    for (int py = y0; py < y1; py++) {
        uint32_t *row = c->pix + py * c->stride;
        for (int px = x0; px < x1; px++) row[px] = col;
    }
}

static void draw_rect(Canvas *c, int x, int y, int w, int h, uint32_t col, int t) {
    fill_rect(c, x, y, w, t, col);
    fill_rect(c, x, y + h - t, w, t, col);
    fill_rect(c, x, y, t, h, col);
    fill_rect(c, x + w - t, y, t, h, col);
}

static void draw_line(Canvas *c, int x0, int y0, int x1, int y1, uint32_t col, int thick) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    for (;;) {
        if (thick <= 1) put_px(c, x0, y0, col);
        else fill_rect(c, x0 - thick / 2, y0 - thick / 2, thick, thick, col);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

static void fill_tri(Canvas *c, int x0, int y0, int x1, int y1, int x2, int y2, uint32_t col) {
    int minx = x0 < x1 ? (x0 < x2 ? x0 : x2) : (x1 < x2 ? x1 : x2);
    int maxx = x0 > x1 ? (x0 > x2 ? x0 : x2) : (x1 > x2 ? x1 : x2);
    int miny = y0 < y1 ? (y0 < y2 ? y0 : y2) : (y1 < y2 ? y1 : y2);
    int maxy = y0 > y1 ? (y0 > y2 ? y0 : y2) : (y1 > y2 ? y1 : y2);
    if (minx < 0) minx = 0;
    if (miny < 0) miny = 0;
    if (maxx >= c->w) maxx = c->w - 1;
    if (maxy >= c->h) maxy = c->h - 1;
    for (int py = miny; py <= maxy; py++) {
        for (int px = minx; px <= maxx; px++) {
            int w0 = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0);
            int w1 = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1);
            int w2 = (x0 - x2) * (py - y2) - (y0 - y2) * (px - x2);
            if ((w0 >= 0 && w1 >= 0 && w2 >= 0) || (w0 <= 0 && w1 <= 0 && w2 <= 0)) put_px(c, px, py, col);
        }
    }
}

static void draw_text(Canvas *c, int x, int y, const char *s, uint32_t col, int scale) {
    int cx = x;
    for (; *s; s++) {
        unsigned char ch = (unsigned char)*s;
        if (ch < 32 || ch > 126) ch = '?';
        const uint8_t *glyph = FONT5X7[ch - 32];
        for (int row = 0; row < 7; row++) {
            uint8_t bits = glyph[row];
            for (int col_i = 0; col_i < 5; col_i++) {
                if ((bits >> (4 - col_i)) & 1) fill_rect(c, cx + col_i * scale, y + row * scale, scale, scale, col);
            }
        }
        cx += 6 * scale;
    }
}

static void draw_gem_window(Canvas *c, int x, int y, int w, int h, const char *title, int active) {
    uint32_t ink = pack_rgb(c, 18, 22, 30);
    uint32_t white = pack_rgb(c, 250, 248, 242);
    uint32_t shadow = pack_rgb(c, 52, 58, 72);
    uint32_t bar = active ? pack_rgb(c, 22, 26, 46) : pack_rgb(c, 226, 228, 234);
    uint32_t tcol = active ? pack_rgb(c, 247, 242, 228) : ink;
    fill_rect(c, x + 7, y + 7, w, h, shadow);
    fill_rect(c, x, y, w, h, white);
    draw_rect(c, x, y, w, h, ink, 2);
    fill_rect(c, x + 2, y + 2, w - 4, 24, bar);
    draw_line(c, x, y + 26, x + w, y + 26, ink, 2);
    fill_rect(c, x + 5, y + 5, 18, 18, white);
    draw_rect(c, x + 5, y + 5, 18, 18, ink, 1);
    draw_line(c, x + 9, y + 9, x + 19, y + 19, ink, 1);
    draw_line(c, x + 19, y + 9, x + 9, y + 19, ink, 1);
    fill_rect(c, x + w - 23, y + 5, 18, 18, white);
    draw_rect(c, x + w - 23, y + 5, 18, 18, ink, 1);
    draw_rect(c, x + w - 19, y + 9, 10, 10, ink, 1);
    draw_text(c, x + 32, y + 7, title, tcol, 2);
}

static void draw_zoe_ruby(Canvas *c, int cx, int cy, int r) {
    uint32_t dark = pack_rgb(c, 18, 20, 32);
    uint32_t ruby_hi = pack_rgb(c, 255, 118, 146);
    uint32_t ruby_mid = pack_rgb(c, 230, 57, 86);
    uint32_t ruby_deep = pack_rgb(c, 152, 22, 54);
    uint32_t cream = pack_rgb(c, 248, 244, 234);

    int xL = cx - r, xR = cx + r, xTL = cx - (r * 58) / 100, xTR = cx + (r * 58) / 100;
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

    int ey = yBelt + (r * 14) / 100, ex = (r * 28) / 100;
    draw_line(c, cx - ex - 9, ey, cx - ex - 4, ey - 6, cream, 2);
    draw_line(c, cx - ex - 4, ey - 6, cx - ex + 4, ey - 6, cream, 2);
    draw_line(c, cx - ex + 4, ey - 6, cx - ex + 9, ey, cream, 2);
    draw_line(c, cx + ex - 9, ey, cx + ex - 4, ey - 6, cream, 2);
    draw_line(c, cx + ex - 4, ey - 6, cx + ex + 4, ey - 6, cream, 2);
    draw_line(c, cx + ex + 4, ey - 6, cx + ex + 9, ey, cream, 2);
    int my = ey + (r * 18) / 100;
    draw_line(c, cx - 10, my - 3, cx - 4, my + 4, cream, 2);
    draw_line(c, cx - 4, my + 4, cx + 4, my + 4, cream, 2);
    draw_line(c, cx + 4, my + 4, cx + 10, my - 3, cream, 2);
}

static void draw_cursor(Canvas *c, int mx, int my, uint32_t accent) {
    uint32_t ink = pack_rgb(c, 12, 14, 22);
    for (int r = 0; r < 16; r++) {
        for (int col = 0; col < 16; col++) {
            char ch = ZOE_CURSOR[r][col];
            if (ch == 'X') put_px(c, mx + col, my + r, ink);
            else if (ch == 'O') put_px(c, mx + col, my + r, accent);
        }
    }
}

static void save_live_canvas_svg(const DesktopApp *app, const char *path) {
    FILE *f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"%d\" height=\"%d\" viewBox=\"0 0 %d %d\">\n",
            app->vw, app->vh, app->vw, app->vh);
    fprintf(f, "  <rect x=\"0\" y=\"0\" width=\"%d\" height=\"%d\" fill=\"#0f1020\"/>\n", app->vw, app->vh);
    fprintf(f, "  <line x1=\"%d\" y1=\"0\" x2=\"%d\" y2=\"%d\" stroke=\"#e63956\" stroke-dasharray=\"4 4\"/>\n",
            app->vw / 2, app->vw / 2, app->vh);
    for (int i = 0; i < app->stroke_count; i++) {
        const Stroke *st = &app->strokes[i];
        fprintf(f, "  <line x1=\"%d\" y1=\"%d\" x2=\"%d\" y2=\"%d\" stroke=\"%s\" stroke-width=\"2\"/>\n",
                st->x0, st->y0, st->x1, st->y1, PAL_HEX[st->color_idx & 7]);
    }
    fprintf(f, "</svg>\n");
    fflush(f);
    fsync(fileno(f));
    fclose(f);
}

static void append_drawer_note(BootState *st, const char *text) {
    const char *path = "/mnt/zoe-state/nick_drawer.json";
    FILE *f = fopen(path, "r");
    char buf[16384];
    size_t n = 0;
    if (f) { n = fread(buf, 1, sizeof(buf) - 1, f); fclose(f); }
    buf[n] = 0;
    char *end = strrchr(buf, ']');
    FILE *w = fopen(path, "w");
    if (!w) return;
    if (end && end > buf) {
        *end = 0;
        fprintf(w, "%s,\n  {\"boot\": %s, \"author\": \"Nicholas\", \"text\": \"%s\"}\n]\n", buf, st->boot_count, text);
    } else {
        fprintf(w, "[\n  {\"boot\": %s, \"author\": \"Nicholas\", \"text\": \"%s\"}\n]\n", st->boot_count, text);
    }
    fflush(w);
    fsync(fileno(w));
    fclose(w);
    int cnt = atoi(st->drawer_count) + 1;
    snprintf(st->drawer_count, sizeof(st->drawer_count), "%d", cnt);
    snprintf(st->drawer_latest, sizeof(st->drawer_latest), "%s", text);
}

static void draw_gem_p32_toolkit(Canvas *c, DesktopApp *app, int x, int y, int w, int h) {
    uint32_t ink = pack_rgb(c, 18, 22, 30);
    uint32_t white = pack_rgb(c, 250, 248, 242);
    draw_gem_window(c, x, y, w, h, "GEM TOOLKIT", 0);
    int bx = x + 14, by = y + 38, sw = (w - 40) / 4;
    app->sw_w = sw;
    app->sw_h = 24;
    for (int i = 0; i < 8; i++) {
        int r = i / 4, col = i % 4;
        int sx = bx + col * (sw + 4), sy = by + r * 30;
        app->sw_x[i] = sx;
        app->sw_y[i] = sy;
        fill_rect(c, sx, sy, sw, 24, pal_col(c, i));
        draw_rect(c, sx, sy, sw, 24, (i == app->active_color) ? pack_rgb(c, 230, 57, 86) : ink, (i == app->active_color) ? 3 : 1);
        char num[2] = {(char)('0' + i), 0};
        draw_text(c, sx + sw / 2 - 4, sy + 6, num, i == 0 ? ink : white, 2);
    }
    int b2y = by + 68;
    const char *bullets[5] = {" ", "o", "#", ">", "v"};
    for (int i = 0; i < 5; i++) {
        int sx = bx + i * ((w - 28) / 5);
        draw_rect(c, sx, b2y, 28, 24, ink, i == 0 ? 2 : 1);
        draw_text(c, sx + 9, b2y + 6, bullets[i], ink, 2);
    }
    int fy = b2y + 36;
    draw_rect(c, bx, fy, w - 28, 48, ink, 1);
    draw_text(c, bx + 8, fy + 8, "> Swiss", ink, 2);
    draw_text(c, bx + 8, fy + 26, "  Dutch", ink, 2);
    int sy = fy + 58, lw = (w - 34) * 62 / 100;
    draw_rect(c, bx, sy, lw, 92, ink, 1);
    draw_text(c, bx + 6, sy + 8,  "  Normal", ink, 1);
    draw_text(c, bx + 6, sy + 28, "> Bold", ink, 1);
    draw_text(c, bx + 6, sy + 48, "  Italic", ink, 1);
    draw_text(c, bx + 6, sy + 68, "  Underl", ink, 1);
    int rx = bx + lw + 6, rw = w - 28 - lw - 6;
    draw_rect(c, rx, sy, rw, 92, ink, 1);
    draw_text(c, rx + 6, sy + 8,  " 14", ink, 1);
    draw_text(c, rx + 6, sy + 24, " 20", ink, 1);
    draw_text(c, rx + 6, sy + 40, ">28", ink, 1);
    draw_text(c, rx + 6, sy + 56, " 36", ink, 1);
    draw_text(c, rx + 6, sy + 72, " 72", ink, 1);
    int ay = sy + 102;
    draw_rect(c, bx, ay, w - 28, 86, ink, 1);
    draw_text(c, bx + 8, ay + 10, "  Left", ink, 1);
    draw_text(c, bx + 8, ay + 28, "> Center", ink, 1);
    draw_text(c, bx + 8, ay + 46, "  Right", ink, 1);
    draw_text(c, bx + 8, ay + 64, "  Decimal", ink, 1);
    char pen_lbl[48];
    snprintf(pen_lbl, sizeof(pen_lbl), "PEN #%d * MIRROR %s", app->active_color, app->mirror_on ? "ON" : "OFF");
    draw_text(c, bx + 2, y + h - 42, pen_lbl, pack_rgb(c, 230, 57, 86), 1);
    draw_text(c, bx + 2, y + h - 22, "CLICK 0-7 TO PICK COLOR", pack_rgb(c, 90, 96, 114), 1);
}

static void draw_artline_neuro_panel(Canvas *c, DesktopApp *app, int x, int y, int w, int h, const BootState *st) {
    uint32_t ink = pack_rgb(c, 18, 22, 30);
    uint32_t dark = pack_rgb(c, 15, 16, 32);
    uint32_t cyan = pack_rgb(c, 92, 225, 230);
    uint32_t ruby = pack_rgb(c, 230, 57, 86);
    uint32_t mag = pack_rgb(c, 217, 70, 239);
    uint32_t cream = pack_rgb(c, 247, 242, 228);

    draw_gem_window(c, x, y, w, h, "ARTLINE 2.0", 0);
    int vx = x + 12, vy = y + 36, vw = w - 24, vh = 240;
    app->vx = vx; app->vy = vy; app->vw = vw; app->vh = vh;
    fill_rect(c, vx, vy, vw, vh, dark);
    draw_rect(c, vx, vy, vw, vh, ink, 2);
    int cx = vx + vw / 2, cy = vy + vh / 2;
    for (int py = vy + 12; py < vy + vh - 12; py += 6) draw_line(c, cx, py, cx, py + 3, ruby, 1);
    int pts = 16;
    for (int i = 0; i < pts; i++) {
        double a0 = 2.0 * 3.14159265 * i / pts;
        double a1 = 2.0 * 3.14159265 * ((i + 1) % pts) / pts;
        int x0 = cx + (int)(cos(a0) * (vw * 0.30)), y0 = cy + (int)(sin(a0) * (vh * 0.30));
        int x1 = cx + (int)(cos(a1) * (vw * 0.30)), y1 = cy + (int)(sin(a1) * (vh * 0.30));
        draw_line(c, x0, y0, x1, y1, cyan, 1);
        int ix0 = cx + (int)(cos(a0) * (vw * 0.17)), iy0 = cy + (int)(sin(a0) * (vh * 0.17));
        draw_line(c, ix0, iy0, x0, y0, (i % 2 == 0) ? mag : ruby, 1);
    }
    /* Render live interactive user Artline strokes! */
    for (int i = 0; i < app->stroke_count; i++) {
        const Stroke *sk = &app->strokes[i];
        draw_line(c, vx + sk->x0, vy + sk->y0, vx + sk->x1, vy + sk->y1, pal_col(c, sk->color_idx), 2);
    }
    draw_text(c, vx + 8, vy + 8, "DRAW HERE (MIRROR SYMM)", cyan, 1);
    char cnt_lbl[48];
    snprintf(cnt_lbl, sizeof(cnt_lbl), "STROKES:%d * [S]AVE [C]LR", app->stroke_count);
    draw_text(c, vx + 8, vy + vh - 14, cnt_lbl, cream, 1);

    int ty = vy + vh + 14;
    char line[128];
    snprintf(line, sizeof(line), "PLATES  : %s", st->artline_files);
    draw_text(c, x + 14, ty, line, ink, 1);
    snprintf(line, sizeof(line), "VDI SHA : %.16s", st->artline_sha);
    draw_text(c, x + 14, ty + 18, line, ink, 1);
    snprintf(line, sizeof(line), "68K RSC : %s B (9 ICONS)", st->rsc_bytes);
    draw_text(c, x + 14, ty + 36, line, ink, 1);
    draw_text(c, x + 14, ty + 62, "HOTKEYS / MOUSE:", ruby, 1);
    draw_text(c, x + 14, ty + 78, "DRAG: Draw   [M] Mirror", ink, 1);
    draw_text(c, x + 14, ty + 94, "[S] Save SVG [C] Clear", ink, 1);
    draw_text(c, x + 14, ty + 110, "[D] Nick Drawer [T] Shell", ink, 1);
    draw_text(c, x + 14, y + h - 36, "clinical_action=False", pack_rgb(c, 150, 30, 50), 1);
    draw_text(c, x + 14, y + h - 20, "sentience_claimed=False", pack_rgb(c, 90, 96, 114), 1);
}

static void parse_json_str(const char *buf, const char *key, char *out, size_t cap) {
    char pat[80];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(buf, pat);
    if (!p) return;
    p = strchr(p + strlen(pat), ':');
    if (!p) return;
    p++;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '"') {
        p++;
        size_t i = 0;
        while (*p && *p != '"' && i + 1 < cap) {
            if (*p == '\\' && p[1]) p++;
            out[i++] = *p++;
        }
        out[i] = 0;
    } else {
        size_t i = 0;
        while (*p && *p != ',' && *p != '}' && *p != '\n' && i + 1 < cap) out[i++] = *p++;
        out[i] = 0;
    }
}

static void load_boot_state(const char *path, BootState *st) {
    memset(st, 0, sizeof(*st));
    strcpy(st->boot_count, "1"); strcpy(st->restored, "false");
    strcpy(st->kernel, "Linux-HAL x86_64"); strcpy(st->cpu, "x86_64 CPU");
    strcpy(st->ram_mb, "512"); strcpy(st->ip_addr, "pending");
    strcpy(st->nic, "eth0"); strcpy(st->disk, "/dev/vda [ZOE-STATE]");
    strcpy(st->chain_sha, "0000000000000000"); strcpy(st->prev_sha, "genesis");
    strcpy(st->drawer_count, "0"); strcpy(st->drawer_latest, "(empty)");
    strcpy(st->artline_files, "0"); strcpy(st->artline_sha, "pending"); strcpy(st->rsc_bytes, "2990");
    FILE *f = fopen(path, "r");
    if (!f) return;
    char buf[8192];
    size_t n = fread(buf, 1, sizeof(buf) - 1, f);
    fclose(f);
    buf[n] = 0;
    parse_json_str(buf, "boot_count", st->boot_count, sizeof(st->boot_count));
    parse_json_str(buf, "restored_from_prior", st->restored, sizeof(st->restored));
    parse_json_str(buf, "kernel", st->kernel, sizeof(st->kernel));
    parse_json_str(buf, "cpu", st->cpu, sizeof(st->cpu));
    parse_json_str(buf, "ram_mb", st->ram_mb, sizeof(st->ram_mb));
    parse_json_str(buf, "ip_addr", st->ip_addr, sizeof(st->ip_addr));
    parse_json_str(buf, "nic", st->nic, sizeof(st->nic));
    parse_json_str(buf, "disk", st->disk, sizeof(st->disk));
    parse_json_str(buf, "chain_sha", st->chain_sha, sizeof(st->chain_sha));
    parse_json_str(buf, "prev_sha", st->prev_sha, sizeof(st->prev_sha));
    parse_json_str(buf, "drawer_count", st->drawer_count, sizeof(st->drawer_count));
    parse_json_str(buf, "drawer_latest", st->drawer_latest, sizeof(st->drawer_latest));
    parse_json_str(buf, "artline_files", st->artline_files, sizeof(st->artline_files));
    parse_json_str(buf, "artline_sha", st->artline_sha, sizeof(st->artline_sha));
    parse_json_str(buf, "rsc_bytes", st->rsc_bytes, sizeof(st->rsc_bytes));
}

static void render_desktop(Canvas *c, DesktopApp *app, const BootState *st, int show_cursor) {
    uint32_t bg_a = pack_rgb(c, 202, 208, 218), bg_b = pack_rgb(c, 224, 228, 235);
    uint32_t ink = pack_rgb(c, 18, 22, 30), white = pack_rgb(c, 250, 248, 242);
    uint32_t ruby = pack_rgb(c, 230, 57, 86), green = pack_rgb(c, 22, 148, 78);
    uint32_t dark = pack_rgb(c, 15, 16, 32), cyan = pack_rgb(c, 92, 225, 230);
    uint32_t cream = pack_rgb(c, 247, 242, 228);

    for (int y = 0; y < c->h; y++) {
        uint32_t *row = c->pix + y * c->stride;
        for (int x = 0; x < c->w; x++) row[x] = (((x >> 1) + (y >> 1)) & 1) ? bg_a : bg_b;
    }

    /* GEM Top Menu Bar (clickable hot zones) */
    fill_rect(c, 0, 0, c->w, 30, white);
    draw_line(c, 0, 30, c->w, 30, ink, 2);
    fill_rect(c, 10, 6, 18, 18, ruby);
    draw_rect(c, 10, 6, 18, 18, ink, 1);
    draw_text(c, 38, 8, "Desk  Mirror  Clear  Save  Drawer  Shell  Power", ink, 2);
    char badge[96];
    snprintf(badge, sizeof(badge), "ZOE-GEM OS  BOOT #%s", st->boot_count);
    int bx = c->w - (int)strlen(badge) * 12 - 16;
    if (bx > 680) draw_text(c, bx, 8, badge, ruby, 2);

    int pad = 16, top = 44, win_h = c->h - top - 44;
    if (win_h < 420) win_h = c->h - top - 16;
    int left_w = 210, right_w = 286;
    int mid_w = c->w - left_w - right_w - pad * 4;
    if (mid_w < 300) { left_w = 180; right_w = 236; mid_w = c->w - left_w - right_w - pad * 4; }

    draw_gem_p32_toolkit(c, app, pad, top, left_w, win_h);

    int mx = pad * 2 + left_w;
    draw_gem_window(c, mx, top, mid_w, win_h, "ZOE-GEM OS :: HARDWARE & RETENTION", 1);
    int hx = mx + 14, hy = top + 38, hw = mid_w - 28, hh = 152;
    fill_rect(c, hx, hy, hw, hh, dark);
    draw_rect(c, hx, hy, hw, hh, ink, 2);
    draw_zoe_ruby(c, hx + 76, hy + 78, 54);
    draw_text(c, hx + 150, hy + 20, "ZOE-GEM OS v1.0", cream, 2);
    draw_text(c, hx + 150, hy + 46, "DIGITAL RESEARCH GEM + ARTLINE", cyan, 1);
    int is_restored = (strcmp(st->restored, "true") == 0);
    fill_rect(c, hx + 148, hy + 68, hw - 164, 30, is_restored ? green : ruby);
    draw_rect(c, hx + 148, hy + 68, hw - 164, 30, cream, 1);
    draw_text(c, hx + 158, hy + 76, is_restored ? "SELF-RESTORED FROM DISK!" : "COLD BOOT SEALED ON DISK", cream, 2);
    char sub[96];
    snprintf(sub, sizeof(sub), "FB0 %dx%d * MOUSE+KBD * 0 TOKENS", c->w, c->h);
    draw_text(c, hx + 150, hy + 112, sub, cream, 1);
    draw_text(c, hx + 150, hy + 130, "HOUSE FOR ZOE * DRAWER FOR NICK", pack_rgb(c, 245, 158, 11), 1);

    int ty = hy + hh + 20;
    char row[160];
    snprintf(row, sizeof(row), "BOOT COUNT  : #%s  (prior=%s)", st->boot_count, is_restored ? "VERIFIED" : "GENESIS");
    draw_text(c, mx + 18, ty, row, is_restored ? green : ink, 2); ty += 28;
    snprintf(row, sizeof(row), "KERNEL HAL  : %.34s", st->kernel);
    draw_text(c, mx + 18, ty, row, ink, 1); ty += 20;
    snprintf(row, sizeof(row), "CPU / RAM   : %.26s / %s MB", st->cpu, st->ram_mb);
    draw_text(c, mx + 18, ty, row, ink, 1); ty += 20;
    snprintf(row, sizeof(row), "HARDWARE DB : %s", st->disk);
    draw_text(c, mx + 18, ty, row, ink, 1); ty += 20;
    snprintf(row, sizeof(row), "NETWORK NIC : %s -> IPv4 %s", st->nic, st->ip_addr);
    draw_text(c, mx + 18, ty, row, green, 2); ty += 28;
    snprintf(row, sizeof(row), "BOOT SHA256 : %.24s", st->chain_sha);
    draw_text(c, mx + 18, ty, row, ink, 1); ty += 20;
    snprintf(row, sizeof(row), "PREV SHA256 : %.24s", st->prev_sha);
    draw_text(c, mx + 18, ty, row, pack_rgb(c, 80, 90, 110), 1); ty += 26;

    int dx = mx + 14, dw = mid_w - 28, dh = (top + win_h) - ty - 14;
    if (dh >= 60) {
        fill_rect(c, dx, ty, dw, dh, pack_rgb(c, 255, 250, 236));
        draw_rect(c, dx, ty, dw, dh, ink, 2);
        snprintf(row, sizeof(row), "NICK'S PERSISTENT DRAWER (%s NOTES ON DISK)", st->drawer_count);
        draw_text(c, dx + 10, ty + 10, row, ruby, 1);
        snprintf(row, sizeof(row), "> %.56s", st->drawer_latest);
        draw_text(c, dx + 10, ty + 32, row, ink, 1);
        draw_text(c, dx + 10, ty + dh - 18, "PRESS [D] OR CLICK DRAWER TO ADD NOTE * SHA-256 SEALED", pack_rgb(c, 80, 90, 110), 1);
    }

    draw_artline_neuro_panel(c, app, mx + mid_w + pad, top, right_w, win_h, st);

    /* Optional inline GEM Dialog Box for Nick's Drawer input */
    if (app->drawer_modal) {
        int mw = 540, mh = 150, mdx = (c->w - mw) / 2, mdy = (c->h - mh) / 2;
        draw_gem_window(c, mdx, mdy, mw, mh, "NICK'S DRAWER :: NEW HARDWARE NOTE", 1);
        draw_text(c, mdx + 18, mdy + 42, "Type note and press ENTER to seal on disk (ESC cancels):", ink, 1);
        fill_rect(c, mdx + 18, mdy + 64, mw - 36, 32, white);
        draw_rect(c, mdx + 18, mdy + 64, mw - 36, 32, ruby, 2);
        char prompt_line[110];
        snprintf(prompt_line, sizeof(prompt_line), "%s_", app->drawer_buf);
        draw_text(c, mdx + 26, mdy + 74, prompt_line, ink, 2);
        draw_text(c, mdx + 18, mdy + 114, "Target: /mnt/zoe-state/nick_drawer.json (fsync enabled)", pack_rgb(c, 80, 90, 110), 1);
    }

    /* Bottom Status Strip */
    fill_rect(c, 0, c->h - 28, c->w, 28, dark);
    draw_line(c, 0, c->h - 28, c->w, c->h - 28, ink, 2);
    draw_text(c, 16, c->h - 19, app->status_msg[0] ? app->status_msg : "ZOE-GEM OS :: INTERACTIVE HARDWARE MOUSE + KBD :: [M]IRROR [S]AVE [D]RAWER [T]SHELL [Q]POWEROFF", cream, 1);

    if (show_cursor) draw_cursor(c, app->mx, app->my, pal_col(c, app->active_color));
}

static void handle_click(DesktopApp *app, BootState *st) {
    int x = app->mx, y = app->my;
    /* Top Menu Bar clicks */
    if (y <= 30) {
        if (x >= 100 && x < 185) {
            app->mirror_on = !app->mirror_on;
            snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE BILATERAL MIRROR: %s", app->mirror_on ? "ON" : "OFF");
        } else if (x >= 185 && x < 265) {
            app->stroke_count = 0;
            snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE CANVAS CLEARED");
        } else if (x >= 265 && x < 340) {
            save_live_canvas_svg(app, "/mnt/zoe-state/artline/live_canvas.svg");
            snprintf(app->status_msg, sizeof(app->status_msg), "SAVED live_canvas.svg (%d strokes) TO HARDWARE DISK!", app->stroke_count);
            printf("ZOE_OS_CANVAS_SAVED strokes=%d\n", app->stroke_count);
            fflush(stdout);
        } else if (x >= 340 && x < 435) {
            app->drawer_modal = 1; app->drawer_len = 0; app->drawer_buf[0] = 0;
            snprintf(app->status_msg, sizeof(app->status_msg), "DRAWER COMPOSER OPEN (TYPE + ENTER)");
        } else if (x >= 435 && x < 515) {
            app->request_exit = 1;
        } else if (x >= 515 && x < 605) {
            app->request_exit = 3;
        }
        return;
    }
    /* p. 3-2 GEM Toolkit Swatch clicks */
    for (int i = 0; i < 8; i++) {
        if (x >= app->sw_x[i] && x <= app->sw_x[i] + app->sw_w && y >= app->sw_y[i] && y <= app->sw_y[i] + app->sw_h) {
            app->active_color = i;
            snprintf(app->status_msg, sizeof(app->status_msg), "GEM TOOLKIT PEN COLOR -> #%d (%s)", i, PAL_HEX[i]);
            return;
        }
    }
}

static void add_stroke(DesktopApp *app, int x0, int y0, int x1, int y1) {
    if (app->stroke_count < MAX_STROKES) {
        app->strokes[app->stroke_count++] = (Stroke){x0, y0, x1, y1, app->active_color};
    }
    if (app->mirror_on && app->stroke_count < MAX_STROKES) {
        int mx0 = app->vw - x0, mx1 = app->vw - x1;
        app->strokes[app->stroke_count++] = (Stroke){mx0, y0, mx1, y1, app->active_color};
    }
}

static void run_interactive_loop(Canvas *fb, Canvas *back, DesktopApp *app, BootState *st, int autotest_sec) {
    int mouse_fd = open("/dev/input/mice", O_RDONLY | O_NONBLOCK);
    /* Open physical console /dev/tty0 so hardware PS/2 & USB keyboards work even when PID 1 runs on ttyS0 */
    int tty_fd = open("/dev/tty0", O_RDONLY | O_NONBLOCK);
    int kbd_fd = (tty_fd >= 0) ? tty_fd : STDIN_FILENO;
    struct termios orig_t, raw_t;
    int have_tty = (tcgetattr(kbd_fd, &orig_t) == 0);
    if (have_tty) {
        raw_t = orig_t;
        raw_t.c_lflag &= ~(ICANON | ECHO);
        raw_t.c_cc[VMIN] = 0;
        raw_t.c_cc[VTIME] = 0;
        tcsetattr(kbd_fd, TCSANOW, &raw_t);
    }
    int flags = fcntl(kbd_fd, F_GETFL, 0);
    fcntl(kbd_fd, F_SETFL, flags | O_NONBLOCK);

    time_t start_t = time(NULL);
    int dirty = 1;
    while (!app->request_exit) {
        if (autotest_sec > 0 && (time(NULL) - start_t) >= autotest_sec) break;
        if (dirty) {
            render_desktop(back, app, st, 1);
            for (int y = 0; y < fb->h; y++) {
                memcpy(fb->pix + y * fb->stride, back->pix + y * back->stride, (size_t)fb->w * 4);
            }
            dirty = 0;
        }
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(kbd_fd, &rfds);
        int maxfd = kbd_fd;
        if (mouse_fd >= 0) {
            FD_SET(mouse_fd, &rfds);
            if (mouse_fd > maxfd) maxfd = mouse_fd;
        }
        struct timeval tv = {0, 35000};
        if (select(maxfd + 1, &rfds, NULL, NULL, &tv) <= 0) continue;

        /* Hardware PS/2 & USB mouse stream */
        if (mouse_fd >= 0 && FD_ISSET(mouse_fd, &rfds)) {
            uint8_t pkt[3];
            while (read(mouse_fd, pkt, 3) == 3) {
                int dx = (int8_t)pkt[1];
                int dy = -(int8_t)pkt[2];
                app->mx += dx;
                app->my += dy;
                if (app->mx < 0) app->mx = 0;
                if (app->mx >= fb->w - 1) app->mx = fb->w - 1;
                if (app->my < 0) app->my = 0;
                if (app->my >= fb->h - 1) app->my = fb->h - 1;
                app->prev_left = app->left_down;
                app->left_down = (pkt[0] & 1) ? 1 : 0;
                if (app->left_down && !app->prev_left) {
                    handle_click(app, st);
                    app->draw_prev_x = app->mx - app->vx;
                    app->draw_prev_y = app->my - app->vy;
                } else if (app->left_down && app->mx >= app->vx && app->mx < app->vx + app->vw &&
                           app->my >= app->vy && app->my < app->vy + app->vh) {
                    int nx = app->mx - app->vx, ny = app->my - app->vy;
                    if (app->draw_prev_x >= 0 && app->draw_prev_x < app->vw &&
                        app->draw_prev_y >= 0 && app->draw_prev_y < app->vh &&
                        (nx != app->draw_prev_x || ny != app->draw_prev_y)) {
                        add_stroke(app, app->draw_prev_x, app->draw_prev_y, nx, ny);
                    }
                    app->draw_prev_x = nx; app->draw_prev_y = ny;
                }
                dirty = 1;
            }
        }
        /* Hardware keyboard stream */
        if (FD_ISSET(kbd_fd, &rfds)) {
            char ch = 0;
            while (read(kbd_fd, &ch, 1) == 1) {
                if (app->drawer_modal) {
                    if (ch == 27) { app->drawer_modal = 0; }
                    else if (ch == '\r' || ch == '\n') {
                        if (app->drawer_len > 0) {
                            append_drawer_note(st, app->drawer_buf);
                            snprintf(app->status_msg, sizeof(app->status_msg), "SEALED NOTE TO NICK'S HARDWARE DRAWER!");
                        }
                        app->drawer_modal = 0;
                    } else if ((ch == 127 || ch == '\b') && app->drawer_len > 0) {
                        app->drawer_buf[--app->drawer_len] = 0;
                    } else if (ch >= 32 && ch <= 126 && app->drawer_len < 88) {
                        app->drawer_buf[app->drawer_len++] = ch;
                        app->drawer_buf[app->drawer_len] = 0;
                    }
                } else {
                    if (ch >= '0' && ch <= '7') {
                        app->active_color = ch - '0';
                        snprintf(app->status_msg, sizeof(app->status_msg), "GEM TOOLKIT PEN COLOR -> #%d", app->active_color);
                    } else if (ch == 'm' || ch == 'M') {
                        app->mirror_on = !app->mirror_on;
                        snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE BILATERAL MIRROR: %s", app->mirror_on ? "ON" : "OFF");
                    } else if (ch == 'c' || ch == 'C') {
                        app->stroke_count = 0;
                        snprintf(app->status_msg, sizeof(app->status_msg), "ARTLINE CANVAS CLEARED");
                    } else if (ch == 's' || ch == 'S') {
                        save_live_canvas_svg(app, "/mnt/zoe-state/artline/live_canvas.svg");
                        snprintf(app->status_msg, sizeof(app->status_msg), "SAVED live_canvas.svg (%d strokes) TO DISK!", app->stroke_count);
                        printf("ZOE_OS_CANVAS_SAVED strokes=%d\n", app->stroke_count);
                        fflush(stdout);
                    } else if (ch == 'd' || ch == 'D') {
                        app->drawer_modal = 1; app->drawer_len = 0; app->drawer_buf[0] = 0;
                    } else if (ch == 't' || ch == 'T' || ch == 27) {
                        app->request_exit = 1;
                    } else if (ch == 'r' || ch == 'R') {
                        app->request_exit = 2;
                    } else if (ch == 'q' || ch == 'Q') {
                        app->request_exit = 3;
                    }
                }
                dirty = 1;
            }
        }
    }
    if (mouse_fd >= 0) close(mouse_fd);
    if (have_tty) tcsetattr(kbd_fd, TCSANOW, &orig_t);
    fcntl(kbd_fd, F_SETFL, flags);
    if (tty_fd >= 0) close(tty_fd);
}

static int dump_ppm(const Canvas *c, const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) return 1;
    fprintf(f, "P6\n%d %d\n255\n", c->w, c->h);
    for (int y = 0; y < c->h; y++) {
        for (int x = 0; x < c->w; x++) {
            uint32_t p = c->pix[y * c->stride + x];
            uint8_t rgb[3] = {
                (uint8_t)(c->bgr ? ((p >> 16) & 0xFF) : (p & 0xFF)),
                (uint8_t)((p >> 8) & 0xFF),
                (uint8_t)(c->bgr ? (p & 0xFF) : ((p >> 16) & 0xFF)),
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
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--state") == 0 && i + 1 < argc) state_path = argv[++i];
        else if (strcmp(argv[i], "--dump-ppm") == 0 && i + 1 < argc) ppm_out = argv[++i];
        else if (strcmp(argv[i], "--interactive") == 0) interactive = 1;
        else if (strcmp(argv[i], "--autotest-sec") == 0 && i + 1 < argc) { interactive = 1; autotest_sec = atoi(argv[++i]); }
    }

    BootState st;
    load_boot_state(state_path, &st);
    DesktopApp app;
    memset(&app, 0, sizeof(app));
    app.active_color = 5; /* Artline Cyan */
    app.mirror_on = 1;
    app.mx = 512; app.my = 340;

    if (ppm_out) {
        Canvas c = {0};
        c.w = 1024; c.h = 768; c.stride = 1024; c.bgr = 1;
        c.pix = (uint32_t *)calloc((size_t)c.w * (size_t)c.h, sizeof(uint32_t));
        if (!c.pix) return 1;
        render_desktop(&c, &app, &st, 1);
        int rc = dump_ppm(&c, ppm_out);
        free(c.pix);
        return rc;
    }

    int fd = open("/dev/fb0", O_RDWR);
    if (fd < 0) { fprintf(stderr, "zoe_gem_fb: /dev/fb0 unavailable\n"); return 2; }
    struct fb_var_screeninfo vinfo;
    struct fb_fix_screeninfo finfo;
    if (ioctl(fd, FBIOGET_VSCREENINFO, &vinfo) < 0 || ioctl(fd, FBIOGET_FSCREENINFO, &finfo) < 0) { close(fd); return 3; }
    if (vinfo.bits_per_pixel != 32) { close(fd); return 4; }
    size_t map_sz = (size_t)finfo.line_length * (size_t)vinfo.yres;
    void *mem = mmap(NULL, map_sz, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mem == MAP_FAILED) { close(fd); return 5; }

    Canvas fb = {(uint32_t *)mem, (int)vinfo.xres, (int)vinfo.yres, (int)(finfo.line_length / 4), (vinfo.red.offset >= 16) ? 1 : 0};
    Canvas back = {(uint32_t *)calloc((size_t)fb.w * (size_t)fb.h, 4), fb.w, fb.h, fb.w, fb.bgr};
    if (!back.pix) { munmap(mem, map_sz); close(fd); return 6; }

    app.mx = fb.w / 2; app.my = fb.h / 2;
    render_desktop(&back, &app, &st, 1);
    for (int y = 0; y < fb.h; y++) memcpy(fb.pix + y * fb.stride, back.pix + y * back.stride, (size_t)fb.w * 4);
    msync(mem, map_sz, MS_SYNC);
    printf("ZOE_OS_FB_OK %dx%d %ubpp interactive=%d\n", fb.w, fb.h, vinfo.bits_per_pixel, interactive);
    fflush(stdout);

    if (interactive) run_interactive_loop(&fb, &back, &app, &st, autotest_sec);

    free(back.pix);
    munmap(mem, map_sz);
    close(fd);
    return app.request_exit; /* 0/1=shell, 2=reboot, 3=poweroff */
}
