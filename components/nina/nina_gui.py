#!/usr/bin/env python3
"""nina GUI — open source neural TTS desktop app."""

import asyncio
import json
import random
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog, simpledialog

import audio_fx
import tts as _tts

# ── Colours ──────────────────────────────────────────────────────────────────
BG      = "#1c1c2e"
BG2     = "#2a2a40"
BG3     = "#363650"
BG_PLOT = "#141424"
FG      = "#ffffff"
FG2     = "#aab0cc"
ACCENT  = "#5a8aff"
ACCENT2 = "#c084fc"
RED     = "#ff6677"
GREEN   = "#44ee88"
FONT    = ("Inter", 11) if sys.platform != "darwin" else ("SF Pro Text", 11)
MONO    = ("JetBrains Mono", 10)

PROGRESS_FILE = Path.home() / ".config" / "nina" / "progress.json"
LIBRARY_DIR   = Path.home() / "VDT" / "books"

AUDITION_LINES = [
    "Good evening. Starlight gathers gently over the quiet hills while our story begins.",
    "Precision and warmth together turn plain text into an effortless midnight broadcast.",
    "Notice the velvet room air, the crisp articulation, and the smooth studio presence.",
    "Every voice can be sculpted, saved, and shared right in the repository.",
]


# ── Visual branding icon: Exact Zoe from the App (zoe_emblem.xml, no sprout) ──
class ZoeGemIcon(tk.Canvas):
    """Exact faceted red GEM with smiling (^ ◡ ^) crown table from the Zoe App."""

    _ASSETS_DIR = Path(__file__).resolve().parent / "assets"

    def __init__(self, parent, width: int = 56, height: int = 56, bg: str = "#141426"):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=0,
        )
        self._icon_w = width
        self._icon_h = height
        self._photo: tk.PhotoImage | None = None
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self._icon_w, self._icon_h
        png_name = "zoe-app-emblem-42.png" if max(w, h) <= 46 else "zoe-app-emblem-56.png"
        png_path = self._ASSETS_DIR / png_name
        if png_path.is_file():
            try:
                self._photo = tk.PhotoImage(file=str(png_path))
                self.create_image(w / 2.0, h / 2.0, image=self._photo, anchor="center")
                return
            except Exception:
                self._photo = None

        # Vector fallback matching zoe_emblem.xml (100x100 viewport, no sprout)
        scale = min((w - 2) / 100.0, (h - 2) / 100.0)
        ox = (w - 100.0 * scale) / 2.0
        oy = (h - 100.0 * scale) / 2.0

        def pt(gx: float, gy: float) -> tuple[float, float]:
            return ox + gx * scale, oy + gy * scale

        self.create_polygon(*pt(24, 10), *pt(76, 10), *pt(69, 18), *pt(31, 18), fill="#F35670", outline="")
        self.create_polygon(*pt(24, 10), *pt(31, 18), *pt(19, 35), *pt(5, 35), fill="#EB4561", outline="")
        self.create_polygon(*pt(76, 10), *pt(95, 35), *pt(81, 35), *pt(69, 18), fill="#CF2946", outline="")
        self.create_polygon(*pt(31, 18), *pt(50, 35), *pt(19, 35), fill="#F3879D", outline="")
        self.create_polygon(*pt(31, 18), *pt(69, 18), *pt(50, 35), fill="#FAB2C0", outline="")
        self.create_polygon(*pt(69, 18), *pt(81, 35), *pt(50, 35), fill="#EA637E", outline="")
        self.create_polygon(*pt(5, 35), *pt(19, 35), *pt(50, 77), *pt(50, 92), fill="#D2314F", outline="")
        self.create_polygon(*pt(81, 35), *pt(95, 35), *pt(50, 92), *pt(50, 77), fill="#DA3B59", outline="")
        self.create_polygon(*pt(19, 35), *pt(50, 35), *pt(50, 77), fill="#F07B92", outline="")
        self.create_polygon(*pt(50, 35), *pt(81, 35), *pt(50, 77), fill="#E15873", outline="")
        self.create_polygon(*pt(24, 10), *pt(76, 10), *pt(95, 35), *pt(50, 92), *pt(5, 35), fill="", outline="#FFE0E8", width=1.1)
        self.create_line(*pt(5, 35), *pt(95, 35), fill="#FFE0E8", width=1.0)
        self.create_polygon(*pt(31, 18), *pt(69, 18), *pt(81, 35), *pt(50, 77), *pt(19, 35), fill="", outline="#FFE0E8", width=1.0)
        self.create_line(*pt(50, 35), *pt(50, 77), fill="#FFE0E8", width=1.0)
        self.create_line(*pt(31, 18), *pt(50, 35), fill="#FFE0E8", width=0.8)
        self.create_line(*pt(69, 18), *pt(50, 35), fill="#FFE0E8", width=0.8)
        face_w = max(1.4, 2.7 * scale)
        self.create_line(*pt(37.8, 29.4), *pt(41.5, 23.2), *pt(45.2, 29.4), fill="#3B242E", width=face_w, smooth=True, capstyle="round")
        self.create_line(*pt(54.8, 29.4), *pt(58.5, 23.2), *pt(62.2, 29.4), fill="#3B242E", width=face_w, smooth=True, capstyle="round")
        self.create_line(*pt(46.9, 31.8), *pt(50.0, 36.2), *pt(53.1, 31.8), fill="#3B242E", width=face_w, smooth=True, capstyle="round")


# ── Bookmark bar (vertical chapter tabs on text right edge) ──────────────────
class BookmarkBar(tk.Canvas):
    """
    Vertical strip of stacked chapter tabs on the right edge of the text area.
    Each chapter gets a tab shaped like a metal page-marker (rectangle body,
    triangular point to the left). Current chapter highlighted in ACCENT.
    Click any tab to jump to that chapter.
    """
    W = 22   # canvas width in pixels
    MARGIN = 8

    def __init__(self, parent, on_seek):
        super().__init__(parent, width=self.W, bg=BG,
                         highlightthickness=0, cursor="hand2")
        self._on_seek  = on_seek
        self._total    = 0
        self._current  = 0
        self._hover    = None

        self.bind("<Configure>",       lambda e: self._draw())
        self.bind("<Motion>",          self._on_motion)
        self.bind("<Leave>",           self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_click)

    # ── Public API ────────────────────────────────────────────────────────────
    def set_chapters(self, current: int, total: int):
        self._current = current
        self._total   = total
        self._hover   = None
        self._draw()

    def clear(self):
        self._total   = 0
        self._current = 0
        self._hover   = None
        self.delete("all")

    # ── Drawing ───────────────────────────────────────────────────────────────
    def _y_for(self, idx):
        h  = max(1, self.winfo_height())
        t  = max(1, self._total - 1)
        return self.MARGIN + idx / t * (h - 2 * self.MARGIN)

    def _idx_for(self, y):
        h  = max(1, self.winfo_height())
        t  = max(1, self._total - 1)
        frac = (y - self.MARGIN) / max(1, h - 2 * self.MARGIN)
        return max(0, min(t, round(frac * t)))

    def _draw(self):
        self.delete("all")
        if self._total < 1:
            return

        W = self.W
        for i in range(self._total):
            y   = self._y_for(i)
            cur = (i == self._current)
            hov = (i == self._hover)

            if cur:
                color = ACCENT
                tip_x = 0              # point reaches left edge
            elif hov:
                color = FG2
                tip_x = 3
            else:
                color = BG3
                tip_x = 5

            half = 5 if cur else 4

            # Tab shape: right-anchored arrowhead pointing left
            pts = [
                tip_x, y,            # pointed tip (left)
                W // 2, y - half,    # upper shoulder
                W,      y - half,    # upper right
                W,      y + half,    # lower right
                W // 2, y + half,    # lower shoulder
            ]
            self.create_polygon(pts, fill=color, outline="", smooth=False)

    # ── Events ────────────────────────────────────────────────────────────────
    def _on_motion(self, event):
        if self._total < 1:
            return
        idx = self._idx_for(event.y)
        if idx != self._hover:
            self._hover = idx
            self._draw()

    def _on_leave(self, _event):
        if self._hover is not None:
            self._hover = None
            self._draw()

    def _on_click(self, event):
        if self._total < 1:
            return
        idx = self._idx_for(event.y)
        self._on_seek(idx)


# ── Library window ────────────────────────────────────────────────────────────
class LibraryWindow(tk.Toplevel):
    """Scrollable panel listing all books in ~/VDT/books/."""

    def __init__(self, parent, progress: dict, on_open):
        super().__init__(parent)
        self.title("Nina — Library")
        self.geometry("540x520")
        self.minsize(400, 300)
        self.configure(bg=BG)
        self.resizable(True, True)
        self._on_open = on_open
        self._progress = progress
        self._all_books: list[tuple[str, str]] = []  # [(display_label, path)]

        self._build()
        self._populate()
        self.grab_set()   # modal

    def _build(self):
        # Search row
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(top, text="🔍", bg=BG, fg=FG2, font=("Inter", 11)).pack(side="left")
        self._q = tk.StringVar()
        self._q.trace_add("write", lambda *_: self._filter())
        tk.Entry(top, textvariable=self._q, bg=BG2, fg=FG, insertbackground=FG,
                 relief="flat", font=("Inter", 11), width=36).pack(side="left", padx=(6, 0), fill="x", expand=True)

        # Listbox + scrollbar
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        sb = tk.Scrollbar(frame, bg=BG3, troughcolor=BG, relief="flat")
        sb.pack(side="right", fill="y")
        self._lb = tk.Listbox(frame, bg=BG2, fg=FG, selectbackground=ACCENT,
                              selectforeground="#ffffff", relief="flat",
                              font=("Inter", 11), activestyle="none",
                              yscrollcommand=sb.set, borderwidth=0,
                              highlightthickness=0)
        self._lb.pack(side="left", fill="both", expand=True)
        sb.config(command=self._lb.yview)
        self._lb.bind("<Double-Button-1>", self._open_selected)
        self._lb.bind("<Return>", self._open_selected)

        # Bottom buttons
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(bot, text="▶ Open", command=self._open_selected,
                  bg=ACCENT, fg=FG, activebackground="#6a9aff", activeforeground=FG,
                  relief="flat", font=("Inter", 11), padx=14, pady=5,
                  cursor="hand2").pack(side="left", padx=(0, 8))
        tk.Button(bot, text="Browse for file…", command=self._browse,
                  bg=BG3, fg=FG, activebackground=ACCENT, activeforeground=FG,
                  relief="flat", font=("Inter", 11), padx=10, pady=5,
                  cursor="hand2").pack(side="left")
        tk.Button(bot, text="Cancel", command=self.destroy,
                  bg=BG3, fg=FG2, activebackground=BG3, activeforeground=FG,
                  relief="flat", font=("Inter", 11), padx=10, pady=5,
                  cursor="hand2").pack(side="right")

    def _dir_to_title(self, name: str) -> str:
        """'gray-hat-hacking-the-ethical-hacker-s-handbook-6e' → readable title."""
        name = re.sub(r'^\d{10,13}-', '', name)   # strip ISBN prefix
        return name.replace('-', ' ').replace('_', ' ').title()

    def _populate(self):
        self._all_books = []
        if not LIBRARY_DIR.exists():
            self._lb.insert("end", f"  Library not found: {LIBRARY_DIR}")
            return

        for entry in sorted(LIBRARY_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith('.'):
                continue
            subdirs = [c for c in entry.iterdir() if c.is_dir()]
            md_files = [f for f in entry.iterdir() if f.suffix in ('.md', '.txt')]
            if md_files:
                label = f"Other / {self._dir_to_title(entry.name)}"
                saved = self._progress.get(str(entry))
                if saved:
                    label += f"  [ch {saved + 1}]"
                self._all_books.append((label, str(entry)))
            elif subdirs:
                cat = entry.name.replace('-', ' ').replace('_', ' ').title()
                for book_dir in sorted(subdirs):
                    label = f"{cat} / {self._dir_to_title(book_dir.name)}"
                    saved = self._progress.get(str(book_dir))
                    if saved:
                        label += f"  [ch {saved + 1}]"
                    self._all_books.append((label, str(book_dir)))

        self._refresh_list(self._all_books)

    def _filter(self):
        q = self._q.get().lower()
        if not q:
            self._refresh_list(self._all_books)
        else:
            filtered = [(l, p) for l, p in self._all_books if q in l.lower()]
            self._refresh_list(filtered)

    def _refresh_list(self, items):
        self._lb.delete(0, "end")
        self._shown = items
        for label, _ in items:
            self._lb.insert("end", f"  {label}")
        if items:
            self._lb.selection_set(0)

    def _open_selected(self, _event=None):
        sel = self._lb.curselection()
        if not sel:
            return
        _, path = self._shown[sel[0]]
        self.destroy()
        self._on_open(path)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Open Book",
            filetypes=[("Books", "*.txt *.pdf *.epub"), ("All files", "*.*")],
            initialdir=str(LIBRARY_DIR) if LIBRARY_DIR.exists() else str(Path.home()),
        )
        if path:
            self.destroy()
            self._on_open(path)


# ── Book loader ───────────────────────────────────────────────────────────────
class BookLoader:
    """Parse books into (title, text) chapter lists from TXT, PDF, or EPUB."""

    CHAINSAW_RE = re.compile(r'\n===== FILE \d+/\d+: (.+?) =====\n')
    CHAPTER_RE  = re.compile(
        r'\n(?=(?:Chapter|CHAPTER|Part|PART|Section|SECTION)\s+\d+)', re.M
    )
    SKIP_NAMES  = {'toc', 'cover', 'nav', 'ncx', 'opf', 'copyright',
                   'title', 'titlepage', 'colophon', 'halftitle',
                   'fm', 'fm2', 'ata', 'gla', 'ack', 'contents',
                   'dedication', 'about', 'copy', 'pre', 'int', 'p1', 'p2'}

    def load(self, path: str):
        p = Path(path)
        if p.is_dir():
            return self._load_book_dir(p)
        ext = p.suffix.lower()
        if ext == '.pdf':
            return self._load_pdf(path)
        if ext == '.epub':
            return self._load_epub(path)
        return self._load_txt(path)

    # ── Directory of .md / .txt files ────────────────────────────────────────
    def _load_book_dir(self, dirpath: Path):
        all_files = sorted(
            f for f in dirpath.iterdir()
            if f.suffix in ('.md', '.txt') and f.is_file()
        )
        chapters = []
        for f in all_files:
            stem = re.sub(r'^\d+-', '', f.stem).lower()
            stem = re.sub(r'^[a-z]+-ch\d+-', '', stem)
            if stem in self.SKIP_NAMES:
                continue
            text = f.read_text(encoding='utf-8', errors='replace').strip()
            if len(text) < 150:
                continue
            title = stem.replace('-', ' ').replace('_', ' ').title()
            chapters.append((title, text))
        if not chapters:
            chapters = [(re.sub(r'^.*?-', '', f.stem).title(),
                         f.read_text(errors='replace').strip())
                        for f in all_files if f.stat().st_size > 50]
        return chapters

    # ── TXT ──────────────────────────────────────────────────────────────────
    def _load_txt(self, path):
        text = Path(path).read_text(encoding='utf-8', errors='replace')
        if '===== FILE' in text:
            return self._parse_chainsaw(text, Path(path).stem)
        parts = self.CHAPTER_RE.split(text)
        if len(parts) > 2:
            chapters = []
            for i, p in enumerate(parts):
                p = p.strip()
                if not p:
                    continue
                first = p.split('\n')[0].strip()
                title = first if first else f"Section {i + 1}"
                chapters.append((title, p))
            return chapters
        return self._chunk_plain(Path(path).stem, text)

    def _parse_chainsaw(self, text, stem):
        m = re.search(r'^TITLE:\s*(.+)$', text, re.M)
        book_title = m.group(1).strip() if m else stem
        parts = self.CHAINSAW_RE.split(text)
        chapters = []
        for i in range(1, len(parts) - 1, 2):
            fname   = parts[i].strip()
            content = parts[i + 1].strip()
            if len(content) < 200:
                continue
            base = re.sub(r'\.(x?html?|xhtml)$', '', fname, flags=re.I).lower()
            if any(skip in base for skip in self.SKIP_NAMES):
                continue
            title = (fname.replace('.xhtml', '').replace('.html', '')
                         .replace('-', ' ').replace('_', ' ').title())
            chapters.append((title, content))
        return chapters or [(book_title, text.strip())]

    def _chunk_plain(self, stem, text, words=1500):
        word_list = text.split()
        chunks = []
        for i in range(0, len(word_list), words):
            part = ' '.join(word_list[i:i + words])
            n = i // words + 1
            chunks.append((f"{stem} — Part {n}", part))
        return chunks or [(stem, text.strip())]

    # ── PDF ──────────────────────────────────────────────────────────────────
    def _load_pdf(self, path):
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            per_chunk, chunks = 8, []
            for i in range(0, len(reader.pages), per_chunk):
                batch = reader.pages[i:i + per_chunk]
                text  = '\n\n'.join(p.extract_text() or '' for p in batch)
                if text.strip():
                    end = min(i + per_chunk, len(reader.pages))
                    chunks.append((f"Pages {i + 1}–{end}", text))
            return chunks or [("Document", "Could not extract text.")]
        except Exception as e:
            return [("Error", f"PDF load failed: {e}")]

    # ── EPUB ─────────────────────────────────────────────────────────────────
    def _load_epub(self, path):
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
            book     = epub.read_epub(path)
            chapters = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                soup  = BeautifulSoup(item.get_content(), 'html.parser')
                text  = soup.get_text('\n', strip=True)
                if len(text) < 200:
                    continue
                h     = soup.find(['h1', 'h2', 'h3'])
                title = h.get_text().strip() if h else item.get_name()
                chapters.append((title, text))
            return chapters
        except ImportError:
            return [("Error", "pip install ebooklib beautifulsoup4")]
        except Exception as e:
            return [("Error", f"EPUB load failed: {e}")]


# ── Async TTS worker ──────────────────────────────────────────────────────────
class TTSWorker:
    """Runs TTS in a background thread with its own asyncio loop."""

    def __init__(self, on_chunk, on_done, on_error):
        self._loop        = asyncio.new_event_loop()
        self._thread      = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._proc        = None
        self._cancel_flag = threading.Event()
        self.on_chunk     = on_chunk
        self.on_done      = on_done
        self.on_error     = on_error
        self._voices      = []

    def load_voices(self, callback):
        async def _load():
            try:
                voices = await _tts.list_voices()
                self._voices = sorted(voices, key=lambda v: v["ShortName"])
                callback(self._voices)
            except Exception:
                callback(None)
        asyncio.run_coroutine_threadsafe(_load(), self._loop)

    def play(
        self,
        text: str,
        voice_id: str,
        rate: str,
        pitch: str = "+0Hz",
        volume: str = "+0%",
        filtergraph: str = "",
    ):
        self._cancel_flag.clear()

        async def _speak():
            chunks = text.strip().split("\n\n")
            total  = len(chunks)
            try:
                for idx, chunk in enumerate(chunks):
                    if self._cancel_flag.is_set():
                        break
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    self.on_chunk(idx + 1, total, chunk[:60] + ("…" if len(chunk) > 60 else ""))
                    communicate = _tts.Communicate(
                        chunk, voice_id, rate=rate, pitch=pitch, volume=volume
                    )
                    proc = subprocess.Popen(
                        audio_fx.mpv_args(filtergraph),
                        stdin=subprocess.PIPE,
                    )
                    self._proc = proc
                    async for seg in communicate.stream():
                        if self._cancel_flag.is_set():
                            proc.kill()   # SIGKILL — immediate, no buffer drain
                            break
                        if seg["type"] == "audio" and proc.stdin is not None:
                            try:
                                proc.stdin.write(seg["data"])
                            except BrokenPipeError:
                                break
                    if proc.stdin is not None:
                        try:
                            proc.stdin.close()
                        except Exception:
                            pass
                    proc.wait()
                    self._proc = None
                self.on_done()
            except Exception as e:
                self.on_error(str(e))

        asyncio.run_coroutine_threadsafe(_speak(), self._loop)

    def play_song(self, song: str = "zoe", filtergraph: str = ""):
        """Synthesize and stream Zoe's built-in App soprano song through mpv."""
        self._cancel_flag.clear()

        async def _sing():
            try:
                wav_bytes = await asyncio.to_thread(_tts.synthesize_zoe_song_wav, song)
                if not wav_bytes or self._cancel_flag.is_set():
                    self.on_done()
                    return
                proc = subprocess.Popen(
                    audio_fx.mpv_args(filtergraph),
                    stdin=subprocess.PIPE,
                )
                self._proc = proc
                if proc.stdin is not None:
                    try:
                        proc.stdin.write(wav_bytes)
                        proc.stdin.close()
                    except Exception:
                        pass
                proc.wait()
                self._proc = None
                self.on_done()
            except Exception as e:
                self.on_error(str(e))

        asyncio.run_coroutine_threadsafe(_sing(), self._loop)

    def stop(self):
        self._cancel_flag.set()
        if self._proc:
            try:
                self._proc.kill()   # SIGKILL — cut audio immediately
            except Exception:
                pass
            self._proc = None


# ── Interactive 5-Band EQ Curve Canvas ────────────────────────────────────────
class EQCurveCanvas(tk.Canvas):
    """Interactive dark-studio frequency response curve for the 5 EQ bands."""

    PAD_X = 36
    PAD_Y = 18

    def __init__(self, parent, bands: list[dict], eq: dict[str, float], on_band_change):
        super().__init__(
            parent,
            height=136,
            bg=BG_PLOT,
            highlightthickness=1,
            highlightbackground=BG3,
            cursor="hand2",
        )
        self._bands = bands
        self._eq = audio_fx.normalize_eq(eq)
        self._on_band_change = on_band_change
        self._drag_idx: int | None = None
        self._hover_idx: int | None = None

        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)

    def set_eq(self, eq: dict[str, float]):
        self._eq = audio_fx.normalize_eq(eq)
        self._draw()

    def _plot_bounds(self):
        w = max(220, self.winfo_width() or 560)
        h = max(100, self.winfo_height() or 136)
        return self.PAD_X, self.PAD_Y, w - self.PAD_X, h - self.PAD_Y - 12

    def _band_xy(self, idx: int) -> tuple[float, float]:
        x0, y0, x1, y1 = self._plot_bounds()
        n = max(1, len(self._bands) - 1)
        x = x0 + (idx / n) * (x1 - x0)
        gain = self._eq.get(self._bands[idx]["key"], 0.0)
        frac = (12.0 - gain) / 24.0
        y = y0 + frac * (y1 - y0)
        return x, y

    def _gain_from_y(self, y: float) -> float:
        _x0, y0, _x1, y1 = self._plot_bounds()
        frac = audio_fx.clamp((y - y0) / max(1.0, (y1 - y0)), 0.0, 1.0)
        gain = 12.0 - frac * 24.0
        return round(gain * 2.0) / 2.0

    def _catmull_rom_points(self, pts: list[tuple[float, float]], y_min: float, y_max: float):
        if len(pts) < 2:
            return pts
        padded = [pts[0]] + pts + [pts[-1]]
        out: list[tuple[float, float]] = []
        steps = 14
        for i in range(1, len(padded) - 2):
            p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
            for s in range(steps):
                t = s / steps
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * (
                    (2 * p1[0])
                    + (-p0[0] + p2[0]) * t
                    + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                    + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                )
                y = 0.5 * (
                    (2 * p1[1])
                    + (-p0[1] + p2[1]) * t
                    + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                    + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                )
                out.append((x, audio_fx.clamp(y, y_min, y_max)))
        out.append(pts[-1])
        return out

    def _draw(self):
        self.delete("all")
        x0, y0, x1, y1 = self._plot_bounds()
        y_zero = (y0 + y1) / 2.0

        # Grid lines at -12, -6, 0, +6, +12 dB
        for db in (12, 6, 0, -6, -12):
            y = y0 + ((12.0 - db) / 24.0) * (y1 - y0)
            color = "#3a4066" if db == 0 else "#22243a"
            self.create_line(x0, y, x1, y, fill=color, width=1)
            if db in (12, 0, -12):
                lbl = f"{db:+d}" if db != 0 else "0 dB"
                self.create_text(x0 - 6, y, text=lbl, fill="#6e7699",
                                 anchor="e", font=("Inter", 8))

        pts = [self._band_xy(i) for i in range(len(self._bands))]

        # Vertical band guides + Hz labels
        for i, (px, _py) in enumerate(pts):
            self.create_line(px, y0, px, y1, fill="#22243a", dash=(2, 3))
            self.create_text(px, y1 + 12, text=self._bands[i]["hz_label"],
                             fill=FG2, font=("Inter", 8))

        # Smooth curve + under-curve shaded fill toward 0 dB line
        smooth = self._catmull_rom_points(pts, y0, y1)
        poly_coords: list[float] = [smooth[0][0], y_zero]
        line_coords: list[float] = []
        for sx, sy in smooth:
            poly_coords.extend((sx, sy))
            line_coords.extend((sx, sy))
        poly_coords.extend((smooth[-1][0], y_zero))

        self.create_polygon(poly_coords, fill="#263159", outline="")
        self.create_line(line_coords, fill="#7c9cff", width=2.5, smooth=False)

        # Control dots
        for i, (px, py) in enumerate(pts):
            active = (i == self._drag_idx or i == self._hover_idx)
            r = 6 if active else 5
            fill = ACCENT2 if active else ACCENT
            self.create_oval(px - r, py - r, px + r, py + r,
                             fill=fill, outline="#ffffff", width=1.5)
            if active:
                gain = self._eq.get(self._bands[i]["key"], 0.0)
                ty = py - 14 if py > y0 + 18 else py + 14
                self.create_text(px, ty, text=f"{gain:+.1f} dB",
                                 fill="#ffffff", font=("Inter", 8, "bold"))

    def _nearest_band(self, x: float) -> int:
        pts = [self._band_xy(i)[0] for i in range(len(self._bands))]
        return min(range(len(pts)), key=lambda i: abs(pts[i] - x))

    def _on_motion(self, event):
        if self._drag_idx is not None:
            return
        idx = self._nearest_band(event.x)
        px, py = self._band_xy(idx)
        new_hover = idx if abs(px - event.x) <= 20 and abs(py - event.y) <= 20 else None
        if new_hover != self._hover_idx:
            self._hover_idx = new_hover
            self._draw()

    def _on_leave(self, _event):
        if self._hover_idx is not None and self._drag_idx is None:
            self._hover_idx = None
            self._draw()

    def _on_press(self, event):
        self._drag_idx = self._nearest_band(event.x)
        self._apply_drag(event.y)

    def _on_drag(self, event):
        if self._drag_idx is not None:
            self._apply_drag(event.y)

    def _on_release(self, _event):
        self._drag_idx = None
        self._draw()

    def _apply_drag(self, y: float):
        if self._drag_idx is None:
            return
        key = self._bands[self._drag_idx]["key"]
        val = self._gain_from_y(y)
        self._eq[key] = val
        self._draw()
        self._on_band_change(key, val)


# ── Voice Studio & Equalizer window ───────────────────────────────────────────
class VoiceStudioWindow(tk.Toplevel):
    """Interactive 5-band Equalizer, Prosody, and Creative Audio FX Studio."""

    def __init__(
        self,
        parent,
        store: audio_fx.ProfileStore,
        voice_id: str,
        voice_label: str,
        initial_state: dict,
        on_change,
        on_saved,
        voice_choices: list[str] | None = None,
        on_select_voice=None,
    ):
        super().__init__(parent)
        self.title("Lume 1.0 — Voice Studio & Equalizer")
        self.geometry("780x640")
        self.minsize(700, 580)
        self.configure(bg=BG)

        self._store = store
        self._voice_id = voice_id
        self._voice_label = voice_label
        self._on_change = on_change
        self._on_saved = on_saved
        self._on_select_voice = on_select_voice
        self._updating_ui = False
        self._audition_idx = 0

        self._preview_worker = TTSWorker(
            on_chunk=self._on_preview_chunk,
            on_done=self._on_preview_done,
            on_error=self._on_preview_error,
        )
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        if voice_choices:
            self.set_voice_choices(voice_choices, voice_label)
        self.sync_voice(voice_id, voice_label, initial_state)

    def _build_ui(self):
        # ── Top bar ───────────────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=14, pady=(12, 6))

        ZoeGemIcon(top, width=42, height=42, bg=BG).pack(side="left", padx=(0, 10))

        title_col = tk.Frame(top, bg=BG)
        title_col.pack(side="left", fill="x", expand=True)

        voice_pick_row = tk.Frame(title_col, bg=BG)
        voice_pick_row.pack(fill="x")
        tk.Label(
            voice_pick_row, text="Voice", bg=BG, fg=FG2,
            font=("Inter", 10, "bold"),
        ).pack(side="left", padx=(0, 6))
        self._studio_voice_var = tk.StringVar()
        self._studio_voice_box = ttk.Combobox(
            voice_pick_row, textvariable=self._studio_voice_var,
            state="readonly", width=32,
        )
        self._studio_voice_box.pack(side="left", padx=(0, 6))
        self._studio_voice_box.bind("<<ComboboxSelected>>", self._on_studio_voice_picked)
        tk.Button(
            voice_pick_row,
            text="⭐ Set Default",
            command=self._set_as_default_voice,
            bg=BG3, fg=FG, activebackground=ACCENT, activeforeground="#ffffff",
            relief="flat", font=("Inter", 9), padx=8, pady=2, cursor="hand2",
        ).pack(side="left")

        self._tagline_lbl = tk.Label(
            title_col, text="", bg=BG, fg=FG2,
            font=("Inter", 9), anchor="w",
        )
        self._tagline_lbl.pack(fill="x", pady=(3, 0))

        self._enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            top,
            text="Enable Fine-Tuning & EQ",
            variable=self._enabled_var,
            command=self._emit_change,
            bg=BG, fg=FG, selectcolor=BG2,
            activebackground=BG, activeforeground=FG,
            font=("Inter", 10, "bold"),
            cursor="hand2",
        ).pack(side="right")

        # ── EQ Curve + 5 Band Sliders ─────────────────────────────────────────
        eq_card = tk.Frame(self, bg=BG2, padx=10, pady=8)
        eq_card.pack(fill="x", padx=14, pady=(0, 8))

        eq_hdr = tk.Frame(eq_card, bg=BG2)
        eq_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(eq_hdr, text="5-Band Equalizer (drag curve or sliders)",
                 bg=BG2, fg=FG, font=("Inter", 10, "bold")).pack(side="left")

        self._bands = self._store.eq_bands
        self._curve_canvas = EQCurveCanvas(
            eq_card, self._bands, dict(audio_fx.DEFAULT_EQ), self._on_canvas_band
        )
        self._curve_canvas.pack(fill="x", pady=(0, 8))

        sliders_row = tk.Frame(eq_card, bg=BG2)
        sliders_row.pack(fill="x")
        self._eq_vars: dict[str, tk.DoubleVar] = {}
        self._eq_val_lbls: dict[str, tk.Label] = {}

        for band in self._bands:
            key = band["key"]
            col = tk.Frame(sliders_row, bg=BG2)
            col.pack(side="left", fill="x", expand=True)
            tk.Label(col, text=band["label"], bg=BG2, fg=FG,
                     font=("Inter", 9, "bold")).pack()
            tk.Label(col, text=band["hz_label"], bg=BG2, fg=FG2,
                     font=("Inter", 8)).pack()
            var = tk.DoubleVar(value=0.0)
            sc = tk.Scale(
                col,
                from_=12.0,
                to=-12.0,
                resolution=0.5,
                orient="vertical",
                length=104,
                variable=var,
                showvalue=False,
                bg=BG2,
                fg=FG,
                troughcolor=BG,
                activebackground=ACCENT,
                highlightthickness=0,
                bd=0,
                command=lambda v, k=key: self._on_slider_band(k, float(v)),
            )
            sc.pack(pady=2)
            val_lbl = tk.Label(col, text="+0.0 dB", bg=BG2, fg=ACCENT, font=MONO)
            val_lbl.pack()
            self._eq_vars[key] = var
            self._eq_val_lbls[key] = val_lbl

        # ── Prosody & Creative Presets (2-column) ─────────────────────────────
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="x", padx=14, pady=(0, 8))

        # Left: Pitch / Pace / Volume
        pros_card = tk.Frame(mid, bg=BG2, padx=10, pady=8)
        pros_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(pros_card, text="Voice Prosody", bg=BG2, fg=FG,
                 font=("Inter", 10, "bold")).pack(anchor="w", pady=(0, 4))

        self._pitch_var = tk.IntVar(value=0)
        self._rate_var = tk.IntVar(value=0)
        self._vol_var = tk.IntVar(value=0)
        self._pitch_lbl = self._add_hslider(
            pros_card, "Pitch", self._pitch_var, -30, 30, "Hz"
        )
        self._rate_lbl = self._add_hslider(
            pros_card, "Pace", self._rate_var, -30, 40, "%"
        )
        self._vol_lbl = self._add_hslider(
            pros_card, "Volume", self._vol_var, -25, 25, "%"
        )

        # Right: EQ Curves & Audio Effect Presets
        fx_card = tk.Frame(mid, bg=BG2, padx=10, pady=8)
        fx_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(fx_card, text="EQ Curves & Audio Effects", bg=BG2, fg=FG,
                 font=("Inter", 10, "bold")).pack(anchor="w", pady=(0, 6))

        r1 = tk.Frame(fx_card, bg=BG2)
        r1.pack(fill="x", pady=3)
        tk.Label(r1, text="EQ Curve", bg=BG2, fg=FG2, width=10, anchor="w",
                 font=("Inter", 10)).pack(side="left")
        self._eq_curve_var = tk.StringVar()
        self._eq_curve_box = ttk.Combobox(
            r1, textvariable=self._eq_curve_var, state="readonly", width=22
        )
        self._eq_curve_box.pack(side="left", fill="x", expand=True)
        self._eq_curve_box.bind("<<ComboboxSelected>>", self._on_curve_selected)

        r2 = tk.Frame(fx_card, bg=BG2)
        r2.pack(fill="x", pady=3)
        tk.Label(r2, text="Effect", bg=BG2, fg=FG2, width=10, anchor="w",
                 font=("Inter", 10)).pack(side="left")
        self._effect_var = tk.StringVar()
        self._effect_box = ttk.Combobox(
            r2, textvariable=self._effect_var, state="readonly", width=22
        )
        self._effect_box.pack(side="left", fill="x", expand=True)
        self._effect_box.bind("<<ComboboxSelected>>", self._on_effect_selected)

        self._fx_desc_lbl = tk.Label(
            fx_card, text="", bg=BG2, fg=FG2,
            font=("Inter", 9), wraplength=310, justify="left", anchor="w",
        )
        self._fx_desc_lbl.pack(fill="x", pady=(6, 6))

        tk.Button(
            fx_card,
            text="🎲 Surprise Me (Creative Blend)",
            command=self._surprise_me,
            bg=ACCENT2,
            fg="#11111e",
            activebackground="#d8a8ff",
            activeforeground="#11111e",
            relief="flat",
            font=("Inter", 10, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(anchor="w")

        self._refresh_preset_boxes()

        # ── Audition Bar ──────────────────────────────────────────────────────
        aud_row = tk.Frame(self, bg=BG)
        aud_row.pack(fill="x", padx=14, pady=(0, 8))

        self._mk_studio_btn(aud_row, "🎧 Preview Tuned", self._preview_tuned, ACCENT)
        self._mk_studio_btn(aud_row, "🔊 Compare Raw",   self._preview_raw,   BG3)
        if _tts.has_native_zoe_voice():
            self._mk_studio_btn(aud_row, "🎵 Sing Zoe",  self._sing_zoe,      "#b91c4a")
        self._mk_studio_btn(aud_row, "■ Stop",           self._preview_worker.stop, BG3)

        self._preview_status = tk.Label(aud_row, text="Ready", bg=BG, fg=FG2,
                                        font=("Inter", 9), anchor="e")
        self._preview_status.pack(side="right", fill="x", expand=True)

        # ── Persistence & Repo Sharing Bar ────────────────────────────────────
        save_row = tk.Frame(self, bg=BG)
        save_row.pack(fill="x", padx=14, pady=(0, 12))

        self._mk_studio_btn(save_row, "💾 Save for Voice", self._save_for_voice, "#2f7d5b")
        self._mk_studio_btn(save_row, "★ Save Preset…",   self._save_preset,    BG3)
        self._mk_studio_btn(save_row, "↺ Zoe's Tune",     self._reset_zoe_tune, BG3)
        self._mk_studio_btn(save_row, "Flat",             self._set_flat,       BG3)
        self._mk_studio_btn(save_row, "📥 Import",        self._import_json,    BG3)
        self._mk_studio_btn(save_row, "📤 Export",        self._export_json,    BG3)

    def _mk_studio_btn(self, parent, text, cmd, bg):
        b = tk.Button(
            parent, text=text, command=cmd, bg=bg, fg=FG,
            activebackground=ACCENT, activeforeground="#ffffff",
            relief="flat", font=("Inter", 10), padx=9, pady=4, cursor="hand2",
        )
        b.pack(side="left", padx=(0, 6))
        return b

    def _add_hslider(self, parent, label, var, lo, hi, unit):
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=BG2, fg=FG2, width=7, anchor="w",
                 font=("Inter", 9)).pack(side="left")
        val_lbl = tk.Label(row, text=f"+0{unit}", bg=BG2, fg=ACCENT,
                           width=6, anchor="e", font=MONO)
        sc = tk.Scale(
            row,
            from_=lo,
            to=hi,
            resolution=1,
            orient="horizontal",
            variable=var,
            showvalue=False,
            bg=BG2,
            fg=FG,
            troughcolor=BG,
            activebackground=ACCENT,
            highlightthickness=0,
            bd=0,
            command=lambda _v, u=unit, vr=var, lb=val_lbl: self._on_prosody_slide(vr, lb, u),
        )
        sc.pack(side="left", fill="x", expand=True, padx=4)
        val_lbl.pack(side="right")
        return val_lbl

    def _refresh_preset_boxes(self):
        curves = self._store.list_eq_curves()
        self._curve_label_to_key = {v.get("label", k): k for k, v in curves.items()}
        self._curve_key_to_label = {k: v.get("label", k) for k, v in curves.items()}
        self._eq_curve_box["values"] = list(self._curve_label_to_key.keys())

        effects = self._store.list_effect_presets()
        self._effect_label_to_key = {v.get("label", k): k for k, v in effects.items()}
        self._effect_key_to_label = {k: v.get("label", k) for k, v in effects.items()}
        self._effect_box["values"] = list(self._effect_label_to_key.keys())

    def set_voice_choices(self, choices: list[str], current_label: str | None = None):
        """Populate the in-Studio Voice Selector so users can pick any voice right here."""
        self._studio_voice_box["values"] = list(choices)
        if current_label:
            self._studio_voice_var.set(current_label)

    def _on_studio_voice_picked(self, _event=None):
        if self._updating_ui:
            return
        picked = self._studio_voice_var.get()
        if picked and self._on_select_voice:
            self._on_select_voice(picked)

    def _set_as_default_voice(self):
        path = self._store.save_default_voice(self._voice_id)
        self._on_saved()
        self._preview_status.config(text=f"Saved default voice in {path.name}")

    def sync_voice(self, voice_id: str, voice_label: str, state: dict):
        """Sync Voice Studio UI with the active voice and state from NinaApp."""
        self._voice_id = voice_id
        self._voice_label = voice_label
        prof = self._store.get_voice_profile(voice_id, tuned=True)
        tagline = prof.get("tagline") or f"Voice ID: {voice_id}"

        self._updating_ui = True
        try:
            self._studio_voice_var.set(voice_label)
            self._tagline_lbl.config(text=tagline)
            self._enabled_var.set(bool(state.get("enabled", True)))
            self._apply_state_to_widgets(state)
        finally:
            self._updating_ui = False

    def _apply_state_to_widgets(self, state: dict):
        eq = audio_fx.normalize_eq(state.get("eq"))
        for key, var in self._eq_vars.items():
            val = eq.get(key, 0.0)
            var.set(val)
            self._eq_val_lbls[key].config(text=f"{val:+.1f} dB")
        self._curve_canvas.set_eq(eq)

        pitch = int(state.get("pitch", 0))
        rate = int(state.get("rate", 0))
        vol = int(state.get("volume", 0))
        self._pitch_var.set(pitch)
        self._rate_var.set(rate)
        self._vol_var.set(vol)
        self._pitch_lbl.config(text=f"{pitch:+d}Hz")
        self._rate_lbl.config(text=f"{rate:+d}%")
        self._vol_lbl.config(text=f"{vol:+d}%")

        eff_key = str(state.get("effect", "flat"))
        eff_label = self._effect_key_to_label.get(
            eff_key, self._effect_key_to_label.get("flat", "Clean / Dry")
        )
        self._effect_var.set(eff_label)
        eff_info = self._store.list_effect_presets().get(eff_key, {})
        self._fx_desc_lbl.config(text=eff_info.get("description", ""))

        # Highlight matching EQ curve if one matches
        matched_curve = ""
        for k, cfg in self._store.list_eq_curves().items():
            if audio_fx.normalize_eq(cfg.get("eq")) == eq:
                matched_curve = self._curve_key_to_label.get(k, "")
                break
        self._eq_curve_var.set(matched_curve or "Custom")

    def current_state(self) -> dict:
        eq = {k: round(float(v.get()), 2) for k, v in self._eq_vars.items()}
        eff_key = self._effect_label_to_key.get(self._effect_var.get(), "flat")
        return {
            "enabled": bool(self._enabled_var.get()),
            "pitch": int(self._pitch_var.get()),
            "rate": int(self._rate_var.get()),
            "volume": int(self._vol_var.get()),
            "eq": eq,
            "effect": eff_key,
        }

    def _emit_change(self):
        if self._updating_ui:
            return
        self._on_change(self.current_state())

    def _on_canvas_band(self, key: str, val: float):
        if self._updating_ui:
            return
        self._updating_ui = True
        try:
            self._eq_vars[key].set(val)
            self._eq_val_lbls[key].config(text=f"{val:+.1f} dB")
            self._eq_curve_var.set("Custom")
        finally:
            self._updating_ui = False
        self._emit_change()

    def _on_slider_band(self, key: str, val: float):
        if self._updating_ui:
            return
        self._eq_val_lbls[key].config(text=f"{val:+.1f} dB")
        eq = {k: round(float(v.get()), 2) for k, v in self._eq_vars.items()}
        self._curve_canvas.set_eq(eq)
        self._eq_curve_var.set("Custom")
        self._emit_change()

    def _on_prosody_slide(self, var, lbl, unit):
        val = int(var.get())
        lbl.config(text=f"{val:+d}{unit}")
        self._emit_change()

    def _on_curve_selected(self, _event=None):
        key = self._curve_label_to_key.get(self._eq_curve_var.get())
        if not key:
            return
        curve = self._store.list_eq_curves().get(key)
        if not curve:
            return
        eq = audio_fx.normalize_eq(curve.get("eq"))
        self._updating_ui = True
        try:
            for band_key, var in self._eq_vars.items():
                val = eq[band_key]
                var.set(val)
                self._eq_val_lbls[band_key].config(text=f"{val:+.1f} dB")
            self._curve_canvas.set_eq(eq)
        finally:
            self._updating_ui = False
        self._emit_change()

    def _on_effect_selected(self, _event=None):
        key = self._effect_label_to_key.get(self._effect_var.get(), "flat")
        eff_info = self._store.list_effect_presets().get(key, {})
        self._fx_desc_lbl.config(text=eff_info.get("description", ""))
        self._emit_change()

    def _surprise_me(self):
        effects = [k for k in self._store.list_effect_presets() if k != "flat"]
        chosen_fx = random.choice(effects) if effects else "zoe_velvet"
        rand_eq = {
            b["key"]: round(random.uniform(-4.5, 5.5) * 2.0) / 2.0
            for b in self._bands
        }
        state = self.current_state()
        state["enabled"] = True
        state["eq"] = rand_eq
        state["effect"] = chosen_fx
        self._updating_ui = True
        try:
            self._enabled_var.set(True)
            self._apply_state_to_widgets(state)
        finally:
            self._updating_ui = False
        self._emit_change()
        self._preview_status.config(text="Rolled a fresh creative EQ + effect blend!")

    def _preview_line(self) -> str:
        line = AUDITION_LINES[self._audition_idx % len(AUDITION_LINES)]
        self._audition_idx += 1
        return line

    def _preview_tuned(self):
        self._preview_worker.stop()
        st = self.current_state()
        fg = audio_fx.build_filtergraph(st["eq"], st["effect"], store=self._store)
        self._preview_status.config(text=f"Previewing Tuned ({st['effect']})…")
        self._preview_worker.play(
            self._preview_line(),
            self._voice_id,
            audio_fx.format_rate(st["rate"]),
            pitch=audio_fx.format_pitch(st["pitch"]),
            volume=audio_fx.format_volume(st["volume"]),
            filtergraph=fg,
        )

    def _preview_raw(self):
        self._preview_worker.stop()
        self._preview_status.config(text="Comparing Raw (Flat, 0 dB)…")
        self._preview_worker.play(
            AUDITION_LINES[(self._audition_idx - 1) % len(AUDITION_LINES)],
            self._voice_id,
            "+0%",
            pitch="+0Hz",
            volume="+0%",
            filtergraph="",
        )

    def _sing_zoe(self):
        self._preview_worker.stop()
        st = self.current_state()
        fg = (
            audio_fx.build_filtergraph(st["eq"], st["effect"], store=self._store)
            if st.get("enabled", True)
            else ""
        )
        self._preview_status.config(text=f"Singing Zoe's App soprano theme ({st['effect']})…")
        self._preview_worker.play_song("zoe", filtergraph=fg)

    def _on_preview_chunk(self, _idx, _total, _preview):
        pass

    def _on_preview_done(self):
        self.after(0, lambda: self._preview_status.config(text="Ready"))

    def _on_preview_error(self, msg):
        self.after(0, lambda: self._preview_status.config(text=f"Error: {msg}"))

    def _save_for_voice(self):
        st = self.current_state()
        path = self._store.save_voice_override(self._voice_id, st)
        self._on_saved()
        self._preview_status.config(text=f"Saved override to {path.name}")

    def _save_preset(self):
        name = simpledialog.askstring(
            "Save Custom Preset",
            "Preset name (e.g. midnight_velvet):",
            parent=self,
        )
        if not name or not name.strip():
            return
        st = self.current_state()
        st["voice_id"] = self._voice_id
        self._store.save_custom_profile(name.strip(), st)
        self._on_saved()
        self._preview_status.config(text=f"Saved preset '{name.strip()}'")

    def _reset_zoe_tune(self):
        self._store.reset_voice_override(self._voice_id)
        repo_def = self._store.get_repo_voice_default(self._voice_id)
        state = {
            "enabled": True,
            "pitch": repo_def["pitch"],
            "rate": repo_def["rate"],
            "volume": repo_def["volume"],
            "eq": repo_def["eq"],
            "effect": repo_def["effect"],
        }
        self._updating_ui = True
        try:
            self._enabled_var.set(True)
            self._apply_state_to_widgets(state)
        finally:
            self._updating_ui = False
        self._emit_change()
        self._on_saved()
        self._preview_status.config(text="Restored Zoe's calibrated defaults")

    def _set_flat(self):
        state = {
            "enabled": self._enabled_var.get(),
            "pitch": 0,
            "rate": 0,
            "volume": 0,
            "eq": dict(audio_fx.DEFAULT_EQ),
            "effect": "flat",
        }
        self._updating_ui = True
        try:
            self._apply_state_to_widgets(state)
        finally:
            self._updating_ui = False
        self._emit_change()
        self._preview_status.config(text="Set flat (0 dB / Clean)")

    def _export_json(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export Voice Profile JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        st = self.current_state()
        st["voice_id"] = self._voice_id
        self._store.export_profile(path, st)
        self._preview_status.config(text=f"Exported {Path(path).name}")

    def _import_json(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Import Voice Profile JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            imported = self._store.import_profile(path)
        except Exception as exc:
            messagebox.showerror("Nina", f"Could not import profile:\n{exc}", parent=self)
            return
        imported["enabled"] = True
        self._updating_ui = True
        try:
            self._enabled_var.set(True)
            self._apply_state_to_widgets(imported)
        finally:
            self._updating_ui = False
        self._emit_change()
        self._preview_status.config(text=f"Imported {Path(path).name}")

    def _on_close(self):
        self._preview_worker.stop()
        self.destroy()


# ── Main window ───────────────────────────────────────────────────────────────
class NinaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lume 1.0 — Nina")
        self.geometry("820x640")
        self.minsize(560, 460)
        self.configure(bg=BG)
        self._configure_style()

        self._store      = audio_fx.ProfileStore()
        self._playing    = False
        self._voices     = []
        self._voice_map: dict[str, str] = {}
        self._voice_meta: dict[str, dict] = {}
        self._fx_enabled = True
        self._studio_win: VoiceStudioWindow | None = None

        pref_id = self._store.preferred_voice_id
        pref_prof = self._store.get_voice_profile(pref_id, tuned=True)
        self._active_tuning = {
            "enabled": True,
            "pitch": pref_prof["pitch"],
            "rate": pref_prof["rate"],
            "volume": pref_prof["volume"],
            "eq": pref_prof["eq"],
            "effect": pref_prof["effect"],
        }

        # ── book state
        self._book_chapters: list   = []   # [(title, text), …]
        self._chapter_idx: int      = 0
        self._book_path: str | None = None
        self._progress: dict        = self._load_progress()

        self._loader = BookLoader()
        self._worker = TTSWorker(
            on_chunk=self._on_chunk,
            on_done=self._on_done,
            on_error=self._on_error,
        )

        self._build_ui()
        self._load_voices()

    # ── Style ─────────────────────────────────────────────────────────────────
    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".",
            background=BG, foreground=FG,
            fieldbackground=BG2, selectbackground=ACCENT,
            selectforeground="#ffffff", insertcolor=FG, font=FONT)
        style.configure("TCombobox",
            background=BG3, foreground=FG, fieldbackground=BG2,
            arrowcolor=FG, selectforeground=FG, selectbackground=BG2)
        style.map("TCombobox",
            fieldbackground=[("readonly", BG2), ("disabled", BG)],
            foreground=[("readonly", FG), ("disabled", FG2)],
            selectforeground=[("readonly", FG)],
            selectbackground=[("readonly", BG2)])
        style.configure("TLabel",  background=BG,  foreground=FG)
        style.configure("TFrame",  background=BG)
        style.configure("Status.TLabel",  background=BG, foreground=FG2, font=(*FONT[:1], 10))
        style.configure("Book.TLabel",    background=BG2, foreground=FG,  font=(*FONT[:1], 10))
        style.configure("TScrollbar", background=BG3, troughcolor=BG, arrowcolor=FG2)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Lume 1.0 Header Banner with Zoe's smiling ruby GEM
        header = tk.Frame(self, bg="#141426", highlightthickness=1, highlightbackground="#2d304e")
        header.pack(fill="x", padx=16, pady=(12, 8))

        header_inner = tk.Frame(header, bg="#141426")
        header_inner.pack(fill="x", padx=12, pady=8)

        ZoeGemIcon(header_inner, width=56, height=56, bg="#141426").pack(side="left", padx=(0, 12))

        brand_col = tk.Frame(header_inner, bg="#141426")
        brand_col.pack(side="left")
        tk.Label(
            brand_col, text="Lume 1.0", bg="#141426", fg="#ff7a90",
            font=("Inter", 15, "bold", "italic"), anchor="w",
        ).pack(anchor="w")
        tk.Label(
            brand_col, text="Zoe Voice Studio  ·  Nina Neural TTS",
            bg="#141426", fg=FG2, font=("Inter", 9), anchor="w",
        ).pack(anchor="w")

        self._status_lbl = tk.Label(
            header_inner, text="Loading voices…", bg="#141426", fg=FG2,
            font=(*FONT[:1], 10), anchor="e",
        )
        self._status_lbl.pack(side="right", padx=(8, 0))

        # Controls row (voice / speed / effect)
        ctrl = ttk.Frame(self)
        ctrl.pack(fill="x", padx=16, pady=4)
        ttk.Label(ctrl, text="Voice", foreground=FG2).pack(side="left")
        self._voice_var = tk.StringVar(value="Loading…")
        self._voice_box = ttk.Combobox(ctrl, textvariable=self._voice_var,
                                       state="readonly", width=30)
        self._voice_box.pack(side="left", padx=(6, 12))
        self._voice_box.bind("<<ComboboxSelected>>", self._on_voice_selected)

        ttk.Label(ctrl, text="Speed", foreground=FG2).pack(side="left")
        self._rate_var = tk.StringVar(value="+0%")
        rate_box = ttk.Combobox(ctrl, textvariable=self._rate_var, state="readonly", width=7,
                                values=["-25%", "-15%", "+0%", "+15%", "+25%", "+50%", "+75%"])
        rate_box.pack(side="left", padx=(6, 12))

        ttk.Label(ctrl, text="Effect", foreground=FG2).pack(side="left")
        self._effect_var = tk.StringVar()
        self._effect_box = ttk.Combobox(ctrl, textvariable=self._effect_var,
                                        state="readonly", width=20)
        self._effect_box.pack(side="left", padx=(6, 0), fill="x", expand=True)
        self._effect_box.bind("<<ComboboxSelected>>", self._on_quick_effect_selected)
        self._refresh_effect_dropdown()

        # Filter row
        search_row = ttk.Frame(self)
        search_row.pack(fill="x", padx=16, pady=(4, 2))
        ttk.Label(search_row, text="Filter voices:", foreground=FG2).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._filter_voices)
        tk.Entry(search_row, textvariable=self._search_var,
                 bg=BG2, fg=FG, insertbackground=FG,
                 relief="flat", font=FONT, width=26).pack(side="left", padx=(6, 12))

        self._female_only_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            search_row,
            text="Female voices only",
            variable=self._female_only_var,
            command=self._filter_voices,
            bg=BG, fg=FG2, selectcolor=BG2,
            activebackground=BG, activeforeground=FG,
            font=("Inter", 10), cursor="hand2",
        ).pack(side="left")

        self._tuning_lbl = ttk.Label(search_row, text="", style="Status.TLabel")
        self._tuning_lbl.pack(side="right")
        self._update_tuning_badge()

        # ── Book bar (hidden until a book is loaded) ──────────────────────────
        self._book_bar = tk.Frame(self, bg=BG2)

        bar_row = tk.Frame(self._book_bar, bg=BG2)
        bar_row.pack(fill="x", padx=10, pady=(6, 6))

        self._book_title_lbl = tk.Label(bar_row, text="", bg=BG2, fg=ACCENT,
                                        font=(*FONT[:1], 10, "bold"), anchor="w")
        self._book_title_lbl.pack(side="left")

        nav_frame = tk.Frame(bar_row, bg=BG2)
        nav_frame.pack(side="right")

        self._prev_ch_btn = tk.Button(nav_frame, text="◀", command=self._prev_chapter,
                                      bg=BG3, fg=FG, activebackground=ACCENT,
                                      activeforeground=FG, relief="flat",
                                      font=FONT, padx=6, pady=2, cursor="hand2")
        self._prev_ch_btn.pack(side="left", padx=(0, 3))

        self._chapter_var = tk.StringVar()
        self._chapter_box = ttk.Combobox(nav_frame, textvariable=self._chapter_var,
                                         state="readonly", width=26)
        self._chapter_box.pack(side="left", padx=(0, 3))
        self._chapter_box.bind("<<ComboboxSelected>>", self._on_chapter_selected)

        self._next_ch_btn = tk.Button(nav_frame, text="▶", command=self._next_chapter,
                                      bg=BG3, fg=FG, activebackground=ACCENT,
                                      activeforeground=FG, relief="flat",
                                      font=FONT, padx=6, pady=2, cursor="hand2")
        self._next_ch_btn.pack(side="left")

        # ── Button row ────────────────────────────────────────────────────────
        self._btn_row = ttk.Frame(self)
        self._btn_row.pack(fill="x", padx=16, pady=(6, 6))

        self._play_btn   = self._mk_btn(self._btn_row, "▶  Play",      self._toggle_play,     ACCENT)
        self._stop_btn   = self._mk_btn(self._btn_row, "■  Stop",      self._stop,            BG3)
        self._clip_btn   = self._mk_btn(self._btn_row, "📋 Clipboard", self._paste_clipboard, BG3)
        self._clear_btn  = self._mk_btn(self._btn_row, "✕ Clear",      self._clear_text,      BG3)
        self._open_btn   = self._mk_btn(self._btn_row, "📚 Open Book", self._open_book,       BG3)
        self._studio_btn = self._mk_btn(self._btn_row, "🎛 Studio / EQ", self._open_studio,   BG3)

        self._chunk_lbl = ttk.Label(self._btn_row, text="", style="Status.TLabel")
        self._chunk_lbl.pack(side="right")

        # ── Text area + vertical bookmark tabs ────────────────────────────────
        self._text_frame = ttk.Frame(self)
        self._text_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        self._bm_bar = BookmarkBar(self._text_frame, on_seek=self._on_scrub)
        self._bm_bar.pack(side="right", fill="y", padx=(2, 0))

        scrollbar = tk.Scrollbar(self._text_frame, command=None,
                                 bg=BG3, troughcolor=BG, relief="flat")

        self._text = tk.Text(
            self._text_frame, bg=BG2, fg=FG, insertbackground=FG,
            selectbackground=ACCENT, relief="flat", font=FONT,
            padx=10, pady=8, wrap="word", undo=True,
        )
        self._text.pack(side="left", fill="both", expand=True)
        self._text.insert("1.0", "Paste or type text here, or click 📚 Open Book.")
        self._text.bind("<FocusIn>", self._clear_placeholder)

        scrollbar.config(command=self._text.yview)
        scrollbar.pack(side="right", fill="y")
        self._text.config(yscrollcommand=scrollbar.set)

    def _mk_btn(self, parent, label, cmd, bg):
        b = tk.Button(parent, text=label, command=cmd,
                      bg=bg, fg=FG, activebackground=ACCENT, activeforeground="white",
                      relief="flat", font=FONT, padx=10, pady=4, cursor="hand2")
        b.pack(side="left", padx=(0, 6))
        return b

    # ── Tuning & Studio sync ──────────────────────────────────────────────────
    def _refresh_effect_dropdown(self):
        presets = self._store.list_effect_presets()
        self._fx_label_to_key = {cfg.get("label", k): k for k, cfg in presets.items()}
        self._fx_key_to_label = {k: cfg.get("label", k) for k, cfg in presets.items()}
        self._effect_box["values"] = list(self._fx_label_to_key.keys())
        cur_fx = self._active_tuning.get("effect", "zoe_velvet")
        self._effect_var.set(self._fx_key_to_label.get(cur_fx, "Zoe's Velvet Studio"))

    def _update_tuning_badge(self):
        if not self._fx_enabled:
            self._tuning_lbl.config(text="Raw (FX Off)")
            return
        eff_key = self._active_tuning.get("effect", "flat")
        eff_lbl = self._fx_key_to_label.get(eff_key, eff_key)
        self._tuning_lbl.config(text=f"🎛 Tuned · {eff_lbl}")

    def _on_quick_effect_selected(self, _event=None):
        eff_key = self._fx_label_to_key.get(self._effect_var.get(), "flat")
        self._active_tuning["effect"] = eff_key
        self._fx_enabled = True
        self._active_tuning["enabled"] = True
        self._update_tuning_badge()
        if self._studio_win and self._studio_win.winfo_exists():
            label = self._voice_var.get()
            vid = self._voice_map.get(label, self._store.preferred_voice_id)
            self._studio_win.sync_voice(vid, label, self._active_tuning)

    def _on_voice_selected(self, _event=None):
        label = self._voice_var.get()
        meta = self._voice_meta.get(label)
        if not meta:
            return
        voice_id = meta["voice_id"]
        if meta.get("is_custom") and meta.get("custom_name"):
            prof = self._store.get_custom_profile(meta["custom_name"]) or {}
        else:
            prof = self._store.get_voice_profile(voice_id, tuned=True)

        self._active_tuning = {
            "enabled": self._fx_enabled,
            "pitch": int(prof.get("pitch", 0)),
            "rate": int(prof.get("rate", 0)),
            "volume": int(prof.get("volume", 0)),
            "eq": audio_fx.normalize_eq(prof.get("eq")),
            "effect": str(prof.get("effect", "flat")),
        }
        self._effect_var.set(
            self._fx_key_to_label.get(self._active_tuning["effect"], "Clean / Dry")
        )
        self._update_tuning_badge()
        if self._studio_win and self._studio_win.winfo_exists():
            self._studio_win.sync_voice(voice_id, label, self._active_tuning)

    def _on_studio_change(self, state: dict):
        self._fx_enabled = bool(state.get("enabled", True))
        self._active_tuning = dict(state)
        self._effect_var.set(
            self._fx_key_to_label.get(state.get("effect", "flat"), "Clean / Dry")
        )
        self._update_tuning_badge()

    def _on_studio_saved(self):
        if self._voices:
            self._rebuild_voice_list(self._voices, keep_selection=True)

    def _on_studio_voice_selected(self, label: str):
        if label in self._voice_map:
            self._voice_var.set(label)
            self._on_voice_selected()

    def _open_studio(self):
        label = self._voice_var.get()
        if not label or label == "Loading…":
            label = "★ Zoe × Natasha (Native 3D)"
        voice_id = self._voice_map.get(label, self._store.preferred_voice_id)
        choices = list(self._voice_box["values"]) or list(self._voice_map.keys())
        if self._studio_win and self._studio_win.winfo_exists():
            self._studio_win.set_voice_choices(choices, label)
            self._studio_win.sync_voice(voice_id, label, self._active_tuning)
            self._studio_win.lift()
            return
        self._studio_win = VoiceStudioWindow(
            self,
            store=self._store,
            voice_id=voice_id,
            voice_label=label,
            initial_state=self._active_tuning,
            on_change=self._on_studio_change,
            on_saved=self._on_studio_saved,
            voice_choices=choices,
            on_select_voice=self._on_studio_voice_selected,
        )

    # ── Book bar show/hide ────────────────────────────────────────────────────
    def _show_book_bar(self):
        self._book_bar.pack(fill="x", padx=0, pady=0, before=self._btn_row)

    def _hide_book_bar(self):
        self._book_bar.pack_forget()

    # ── Open book ─────────────────────────────────────────────────────────────
    def _open_book(self):
        LibraryWindow(self, self._progress, self._open_book_path)

    def _open_book_path(self, path: str):
        if not path:
            return

        self._status(f"Loading {Path(path).name}…")
        self.update_idletasks()

        chapters = self._loader.load(path)
        if not chapters:
            messagebox.showerror("Nina", "Could not extract any text from this file.")
            return

        self._book_path     = path
        self._book_chapters = chapters
        saved = self._progress.get(path, 0)
        self._chapter_idx   = min(saved, len(chapters) - 1)

        titles = [f"{i+1}. {t}" for i, (t, _) in enumerate(chapters)]
        self._chapter_box["values"] = titles
        self._chapter_var.set(titles[self._chapter_idx])

        short = Path(path).stem[:50]
        self._book_title_lbl.config(text=f"📖  {short}")
        self._show_book_bar()

        self._load_chapter(self._chapter_idx)
        self._status(f"{Path(path).name}  •  {len(chapters)} chapters")

    def _load_chapter(self, idx):
        _title, text = self._book_chapters[idx]
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._text.see("1.0")

        total = len(self._book_chapters)

        titles = self._chapter_box["values"]
        if titles:
            self._chapter_var.set(titles[idx])

        self._bm_bar.set_chapters(idx, total)
        self._chunk_lbl.config(text=f"ch {idx+1}/{total}")
        self._prev_ch_btn.config(state="normal" if idx > 0 else "disabled")
        self._next_ch_btn.config(state="normal" if idx < total - 1 else "disabled")

    def _on_scrub(self, idx: int):
        if idx == self._chapter_idx:
            return
        self._stop()
        self._chapter_idx = idx
        self._load_chapter(idx)
        self._save_progress()

    def _on_chapter_selected(self, _event=None):
        idx = self._chapter_box.current()
        if idx < 0:
            return
        self._stop()
        self._chapter_idx = idx
        self._load_chapter(idx)
        self._save_progress()

    def _prev_chapter(self):
        if self._chapter_idx > 0:
            self._stop()
            self._chapter_idx -= 1
            self._load_chapter(self._chapter_idx)
            self._save_progress()

    def _next_chapter(self):
        if self._chapter_idx < len(self._book_chapters) - 1:
            self._stop()
            self._chapter_idx += 1
            self._load_chapter(self._chapter_idx)
            self._save_progress()

    # ── Progress persistence ──────────────────────────────────────────────────
    def _load_progress(self):
        try:
            if PROGRESS_FILE.exists():
                return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
        return {}

    def _save_progress(self):
        if not self._book_path:
            return
        self._progress[self._book_path] = self._chapter_idx
        try:
            PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
            PROGRESS_FILE.write_text(json.dumps(self._progress, indent=2))
        except Exception:
            pass

    # ── Voice loading ─────────────────────────────────────────────────────────
    def _load_voices(self):
        def callback(voices):
            if not voices:
                self.after(0, lambda: self._status("Failed to load voices — check connection"))
                return
            self._voices = voices
            self._rebuild_voice_list(voices)
        self._worker.load_voices(callback)

    # Display-name overrides: ShortName fragment → label shown in the dropdown
    _DISPLAY_NAMES = {
        "EmilyNeural":  "Helen",
        "AndrewNeural": "Alex",
    }

    def _rebuild_voice_list(self, voices, keep_selection: bool = False):
        prev_sel = self._voice_var.get()
        en_voices = [v for v in voices if v.get("Locale", "").startswith("en-")]
        display_names = self._store.get_display_names()
        pref_id = self._store.preferred_voice_id

        entries = []
        native_entries = []
        new_map: dict[str, str] = {}
        new_meta: dict[str, dict] = {}
        pref_entry = None

        for v in en_voices:
            name = v["ShortName"]
            is_native = bool(v.get("NativeApp") or name in _tts.NATIVE_VOICE_IDS)
            if is_native:
                display = display_names.get(name) or v.get("FriendlyName") or name
                label = f"★ {display}"
            else:
                parts = name.split("-")
                frag = parts[2] if len(parts) > 2 else name
                raw = frag.replace('Neural', '').replace('Multilingual', ' (ML)')
                display = display_names.get(name) or self._DISPLAY_NAMES.get(frag, raw)
                prefix = "★ " if name == pref_id else ""
                label = f"{prefix}{display} · {v['Locale']}"
            meta = {
                "voice_id": name,
                "gender": v.get("Gender", "Unknown"),
                "is_custom": False,
                "custom_name": None,
                "is_native": is_native,
            }
            if name == pref_id:
                pref_entry = (label, name, meta)
            elif is_native:
                native_entries.append((label, name, meta))
            else:
                entries.append(label)
                new_map[label] = name
                new_meta[label] = meta

        # Put preferred default first, then Zoe's offline App voices, custom recipes, then English voices
        ordered: list[str] = []
        if pref_entry:
            lbl, vid, meta = pref_entry
            ordered.append(lbl)
            new_map[lbl] = vid
            new_meta[lbl] = meta

        for lbl, vid, meta in native_entries:
            ordered.append(lbl)
            new_map[lbl] = vid
            new_meta[lbl] = meta

        for cname, cfg in self._store.list_custom_profiles().items():
            vid = cfg.get("voice_id", pref_id)
            lbl = f"✦ {cname} (Preset)"
            ordered.append(lbl)
            new_map[lbl] = vid
            new_meta[lbl] = {
                "voice_id": vid,
                "gender": "Female",
                "is_custom": True,
                "custom_name": cname,
            }

        ordered.extend(entries)

        def _update():
            self._voice_map = new_map
            self._voice_meta = new_meta
            self._filter_voices()
            if keep_selection and prev_sel in self._voice_map:
                self._voice_var.set(prev_sel)
            elif pref_entry and pref_entry[0] in self._voice_box["values"]:
                self._voice_var.set(pref_entry[0])
                self._on_voice_selected()
            elif ordered:
                self._voice_var.set(ordered[0])
                self._on_voice_selected()
            if self._studio_win and self._studio_win.winfo_exists():
                self._studio_win.set_voice_choices(
                    list(self._voice_box["values"]), self._voice_var.get()
                )
            self._status(f"Ready  •  {len(en_voices)} English voices")
        self.after(0, _update)

    def _filter_voices(self, *_):
        q = self._search_var.get().lower()
        fem_only = self._female_only_var.get()
        filtered = [
            k for k, meta in self._voice_meta.items()
            if (q in k.lower()) and (not fem_only or meta.get("gender") == "Female")
        ]
        self._voice_box["values"] = filtered
        if filtered and self._voice_var.get() not in filtered:
            self._voice_var.set(filtered[0])
            self._on_voice_selected()
        if self._studio_win and self._studio_win.winfo_exists():
            self._studio_win.set_voice_choices(filtered, self._voice_var.get())

    def _effective_tts_params(self) -> tuple[str, str, str, str]:
        """Compute (rate, pitch, volume, filtergraph) from Speed box + Voice Studio state."""
        user_rate = audio_fx.parse_signed_int(self._rate_var.get(), "%")
        if not self._fx_enabled:
            return audio_fx.format_rate(user_rate), "+0Hz", "+0%", ""
        prof_rate = int(self._active_tuning.get("rate", 0))
        eff_rate = audio_fx.format_rate(audio_fx.clamp(user_rate + prof_rate, -60, 120))
        eff_pitch = audio_fx.format_pitch(self._active_tuning.get("pitch", 0))
        eff_vol = audio_fx.format_volume(self._active_tuning.get("volume", 0))
        fg = audio_fx.build_filtergraph(
            self._active_tuning.get("eq"),
            self._active_tuning.get("effect", "flat"),
            store=self._store,
        )
        return eff_rate, eff_pitch, eff_vol, fg

    # ── Playback ──────────────────────────────────────────────────────────────
    def _toggle_play(self):
        if self._playing:
            self._worker.stop()
            self._playing = False
            self._play_btn.config(text="▶  Play", bg=ACCENT)
            self._status("Paused")
            return

        text = self._text.get("1.0", "end").strip()
        if not text or text == "Paste or type text here, or click 📚 Open Book.":
            messagebox.showwarning("Nina", "Paste text or open a book first.")
            return

        voice_label = self._voice_var.get()
        voice_id    = self._voice_map.get(voice_label)
        if not voice_id:
            messagebox.showerror("Nina", f"Voice not found: {voice_label}")
            return

        rate, pitch, volume, fg = self._effective_tts_params()
        self._playing = True
        self._play_btn.config(text="⏸  Pause", bg=BG3)
        self._status("Playing…")
        self._worker.play(text, voice_id, rate, pitch=pitch, volume=volume, filtergraph=fg)

    def _stop(self):
        self._worker.stop()
        self._playing = False
        self._play_btn.config(text="▶  Play", bg=ACCENT)
        self._chunk_lbl.config(
            text=f"ch {self._chapter_idx+1}/{len(self._book_chapters)}"
                 if self._book_chapters else ""
        )
        self._status("Ready")

    # ── Worker callbacks ──────────────────────────────────────────────────────
    def _on_chunk(self, idx, total, preview):
        self.after(0, lambda: (
            self._chunk_lbl.config(text=f"{idx}/{total}"),
            self._status(f"Reading: {preview}"),
        ))

    def _on_done(self):
        def _done():
            if self._book_chapters and self._chapter_idx < len(self._book_chapters) - 1:
                self._chapter_idx += 1
                self._load_chapter(self._chapter_idx)
                self._save_progress()
                _, text = self._book_chapters[self._chapter_idx]
                voice_id = self._voice_map.get(self._voice_var.get())
                if voice_id:
                    rate, pitch, volume, fg = self._effective_tts_params()
                    self._status(f"Chapter {self._chapter_idx + 1}…")
                    self._worker.play(
                        text, voice_id, rate, pitch=pitch, volume=volume, filtergraph=fg
                    )
                    return
            self._playing = False
            self._play_btn.config(text="▶  Play", bg=ACCENT)
            self._chunk_lbl.config(text="")
            self._status("Done" if not self._book_chapters else "Book complete")
        self.after(0, _done)

    def _on_error(self, msg):
        def _err():
            self._playing = False
            self._play_btn.config(text="▶  Play", bg=ACCENT)
            self._status(f"Error: {msg}")
        self.after(0, _err)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _status(self, msg):
        self._status_lbl.config(text=msg)

    def _clear_placeholder(self, _event):
        placeholder = "Paste or type text here, or click 📚 Open Book."
        if self._text.get("1.0", "end").strip() == placeholder:
            self._text.delete("1.0", "end")

    def _paste_clipboard(self):
        try:
            text = self.clipboard_get()
            self._stop()
            self._text.delete("1.0", "end")
            self._text.insert("1.0", text)
        except tk.TclError:
            messagebox.showinfo("Nina", "Clipboard is empty.")

    def _clear_text(self):
        self._stop()
        self._book_chapters = []
        self._book_path     = None
        self._hide_book_bar()
        self._bm_bar.clear()
        self._text.delete("1.0", "end")
        self._text.insert("1.0", "Paste or type text here, or click 📚 Open Book.")
        self._chunk_lbl.config(text="")


def main():
    import argparse
    p = argparse.ArgumentParser(prog="nina-gui")
    p.add_argument("--book", metavar="PATH", help="Pre-load a book on startup")
    p.add_argument(
        "--studio", action="store_true",
        help="Open the Voice Studio & Equalizer window on startup",
    )
    args = p.parse_args()

    app = NinaApp()
    if args.book:
        app.after(200, lambda: app._open_book_path(args.book))
    if args.studio:
        app.after(250, app._open_studio)
    app.mainloop()


if __name__ == "__main__":
    main()
