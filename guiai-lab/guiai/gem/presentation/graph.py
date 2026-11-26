"""Clean-Room GEM Graph Engine (`GraphDoc`, 8 Chart Families, Evidence Adapters & Auto-Layout).

Inspired by Digital Research GEM Graph (Aug 1987) atop `DrawPlusCanvas` and pure-Python
`PresentationRenderer` — zero external Office/LibreOffice dependency.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
import shlex
from typing import Any, Mapping, Sequence

from .draw_plus import DrawPlusCanvas, petal_points
from .palette import (
    GOLD,
    JADE,
    JADE_SOFT,
    LIGHT_DIVIDER_LINE,
    MARGIN,
    ROSE,
    RUBY,
    SKY,
    SLATE_SOFT,
    STONE,
    WHITE,
    PresentationTheme,
    mix_hex,
    theme_for_sister,
)
from .renderer import PresentationRenderer

CHART_TYPE_ALIASES: dict[str, str] = {
    "pie": "pie",
    "bar": "v_cluster",
    "v_cluster": "v_cluster",
    "clustered": "v_cluster",
    "clustered_bar": "v_cluster",
    "h_cluster": "h_cluster",
    "horizontal_bar": "h_cluster",
    "stacked_bar": "v_stack",
    "v_stack": "v_stack",
    "stacked": "v_stack",
    "h_stack": "h_stack",
    "stacked_100_bar": "v_stack_100",
    "v_stack_100": "v_stack_100",
    "100%": "v_stack_100",
    "100_bar": "v_stack_100",
    "deviation_bar": "deviation_bar",
    "deviation": "deviation_bar",
    "bar_3d": "bar_3d",
    "3d": "bar_3d",
    "3d_bar": "bar_3d",
    "line": "line",
    "area": "area",
    "stacked_area": "stacked_area",
    "bar_line": "bar_line",
    "combo": "bar_line",
    "bar+line": "bar_line",
    "step": "step",
    "stick": "stick",
    "scatter": "scatter",
    "symbol": "symbol",
    "map": "map",
    "choropleth": "map",
}

NON_NEGATIVE_TYPES: set[str] = {
    "pie",
    "area",
    "stacked_area",
    "v_stack",
    "h_stack",
    "v_stack_100",
}

DEFAULT_SERIES_PALETTE: tuple[str, ...] = (RUBY, JADE, GOLD, SKY, ROSE, "#6366F1")


def normalize_chart_type(chart_type: str) -> str:
    """Normalize chart family/subtype alias or raise `ValueError`."""
    key = str(chart_type or "").strip().lower()
    if key not in CHART_TYPE_ALIASES:
        raise ValueError(f"Unsupported chart_type {chart_type!r}; expected {sorted(set(CHART_TYPE_ALIASES.values()))}")
    return CHART_TYPE_ALIASES[key]


def _parse_cell(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        return val if math.isfinite(val) else None
    text = str(raw).strip().strip('"').strip("'")
    if not text or text.lower() in {"na", "n/a", "null", "none", "nan", "-"}:
        return None
    cleaned = text.replace(",", "").rstrip("%").strip()
    val = float(cleaned)
    if not math.isfinite(val):
        raise ValueError(f"Non-finite numeric value: {raw!r}")
    return val


def _format_tick(val: float) -> str:
    av = abs(val)
    if av == 0.0:
        return "0"
    if av >= 1e6 or (0 < av < 1e-3):
        return f"{val:.1e}"
    if abs(val - round(val)) < 1e-6 and av < 10000:
        return str(int(round(val)))
    if av >= 100:
        return f"{val:.1f}"
    return f"{val:.2f}".rstrip("0").rstrip(".")


@dataclass
class DataSeries:
    """One named data series with optional `None` missing-data gaps."""

    name: str
    values: list[float | None]
    color: str | None = None
    marker: str = "circle"
    line_width: float = 24.0
    fill_interior: int = 1
    fill_style: int = 1

    @classmethod
    def from_obj(cls, obj: DataSeries | Mapping[str, Any], idx: int = 0) -> DataSeries:
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, Mapping):
            raw_vals = obj.get("values", [])
            vals = [_parse_cell(v) for v in raw_vals]
            return cls(
                name=str(obj.get("name", f"Series {idx + 1}")),
                values=vals,
                color=obj.get("color"),
                marker=str(obj.get("marker", "circle")),
                line_width=float(obj.get("line_width", 24.0)),
                fill_interior=int(obj.get("fill_interior", 1)),
                fill_style=int(obj.get("fill_style", 1)),
            )
        raise TypeError(f"Unsupported series entry: {type(obj).__name__}")


@dataclass
class AxisOptions:
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    crosses_at: float = 0.0
    scale: str = "linear"
    indent: bool = True
    major_ticks: int = 5
    minor_ticks: int = 0
    label: str = ""


@dataclass
class GridOptions:
    show_x: bool = False
    show_y: bool = True
    style: str = "dashed"


@dataclass
class GraphPreferences:
    accumulate: bool = False
    percent: bool = False
    value_labels: bool = False
    column_labels: str = "legend"
    show_legend: bool = True
    explode_indices: tuple[int, ...] = ()
    allow_negative_abs: bool = False


def _nice_range(lo: float, hi: float, include_zero: bool = True) -> tuple[float, float]:
    if include_zero:
        lo = min(0.0, lo)
        hi = max(0.0, hi)
    if abs(hi - lo) < 1e-12:
        pad = max(1.0, abs(hi) * 0.25)
        return (0.0 if include_zero and lo >= 0 else lo - pad, hi + pad)
    span = hi - lo
    return (lo, hi + span * 0.06 if hi >= 0 else hi)


def _select_json_rows(
    payload: Any,
    metric_key: str | None = None,
) -> tuple[list[str], list[DataSeries]]:
    """Extract `(categories, series)` deterministically from repository evidence JSON schemas."""
    if isinstance(payload, Mapping):
        if "categories" in payload and "series" in payload:
            cats = [str(c) for c in payload["categories"]]
            sers = [DataSeries.from_obj(s, i) for i, s in enumerate(payload["series"])]
            return (cats, sers)
        for key in ("six_baseline_shootout", "by_category", "auroc", "mean_reward"):
            if key in payload and isinstance(payload[key], Mapping):
                return _extract_from_mapping(payload[key], metric_key or key)
        if "causal_closed_loop_systems_ablation" in payload:
            ab = payload["causal_closed_loop_systems_ablation"]
            if isinstance(ab, Mapping) and isinstance(ab.get("mean_reward"), Mapping):
                return _extract_from_mapping(ab["mean_reward"], "mean_reward")
        for list_key in ("pillars", "records", "results", "items"):
            if list_key in payload and isinstance(payload[list_key], list):
                return _extract_from_list(payload[list_key], metric_key)
        return _extract_from_mapping(payload, metric_key or "Value")
    if isinstance(payload, list):
        return _extract_from_list(payload, metric_key)
    raise ValueError("Unsupported JSON structure for GraphDoc")


def _extract_from_mapping(mapping: Mapping[str, Any], label: str) -> tuple[list[str], list[DataSeries]]:
    items = list(mapping.items())
    if not items:
        raise ValueError("Empty JSON mapping for GraphDoc")
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for _, v in items):
        cats = [str(k) for k, _ in items[:12]]
        vals: list[float | None] = [float(v) for _, v in items[:12]]
        return (cats, [DataSeries(name=label, values=vals)])
    dict_items = [(str(k), v) for k, v in items if isinstance(v, Mapping)]
    if dict_items:
        cats = [k for k, _ in dict_items[:12]]
        num_keys = [
            mk for mk, mv in dict_items[0][1].items()
            if isinstance(mv, (int, float)) and not isinstance(mv, bool) and mk != "count"
        ][:4]
        if not num_keys:
            num_keys = [mk for mk, mv in dict_items[0][1].items() if isinstance(mv, (int, float)) and not isinstance(mv, bool)][:3]
        sers = [
            DataSeries(name=str(nk), values=[_parse_cell(d.get(nk)) for _, d in dict_items[:12]])
            for nk in num_keys
        ]
        return (cats, sers)
    raise ValueError("JSON mapping lacks numeric graph fields")


def _extract_from_list(rows: Sequence[Any], metric_key: str | None) -> tuple[list[str], list[DataSeries]]:
    dicts = [r for r in rows if isinstance(r, Mapping)][:12]
    if not dicts:
        raise ValueError("JSON list has no dict rows")
    label_key = next((k for k in ("title", "name", "pillar_id", "id", "category", "step") if k in dicts[0]), None)
    cats = [str(d.get(label_key, f"Item {i + 1}")) if label_key else f"Item {i + 1}" for i, d in enumerate(dicts)]
    if metric_key and metric_key in dicts[0]:
        num_keys = [metric_key]
    else:
        num_keys = [
            k for k, v in dicts[0].items()
            if k != label_key and isinstance(v, (int, float)) and not isinstance(v, bool)
        ][:3]
    if not num_keys and isinstance(dicts[0].get("metrics"), Mapping):
        m0 = dicts[0]["metrics"]
        m_keys = [k for k, v in m0.items() if isinstance(v, (int, float)) and not isinstance(v, bool)][:2]
        return (cats, [DataSeries(name=str(mk), values=[_parse_cell(d.get("metrics", {}).get(mk)) for d in dicts]) for mk in m_keys])
    if not num_keys:
        raise ValueError("JSON list rows lack numeric fields")
    return (cats, [DataSeries(name=str(nk), values=[_parse_cell(d.get(nk)) for d in dicts]) for nk in num_keys])


def _truncate_label(text: str, max_w: float, font_family: str, font_pt: float, *, bold: bool = False) -> str:
    txt = str(text)
    mw, _, _ = PresentationRenderer.measure_text(txt, font_family=font_family, font_pt=font_pt, bold=bold, wrap=False)
    if mw <= max_w:
        return txt
    lo, hi = 1, len(txt)
    best = txt[:1] + "…"
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = txt[:mid].rstrip() + "…"
        cw, _, _ = PresentationRenderer.measure_text(cand, font_family=font_family, font_pt=font_pt, bold=bold, wrap=False)
        if cw <= max_w:
            best = cand
            lo = mid + 1
        else:
            hi = mid - 1
    return best


class GraphDoc:
    """Data-driven chart compiler supporting 8 chart families / 11+ subtypes."""

    def __init__(
        self,
        title: str = "",
        chart_type: str = "bar",
        categories: Sequence[str] = (),
        series: Sequence[DataSeries | Mapping[str, Any]] = (),
        *,
        subtitle: str = "",
        x_values: Sequence[float | None] | None = None,
        x_label: str = "",
        y_label: str = "",
        axis: AxisOptions | None = None,
        grid: GridOptions | None = None,
        preferences: GraphPreferences | None = None,
        show_legend: bool = True,
        show_grid: bool = True,
        value_labels: bool = False,
        explode_indices: Sequence[int] = (),
        theme: PresentationTheme | None = None,
        sister_id: str = "zoe",
        speaker_notes: str = "",
        title_pt: float = 18.0,
        label_pt: float = 9.5,
    ) -> None:
        if float(title_pt) <= 0:
            raise ValueError(f"title_pt must be positive, got {title_pt!r}")
        if float(label_pt) <= 0:
            raise ValueError(f"label_pt must be positive, got {label_pt!r}")
        self.title = str(title)
        self.subtitle = str(subtitle)
        self.chart_type = normalize_chart_type(chart_type)
        self.categories = [str(c) for c in categories]
        self.series = [DataSeries.from_obj(s, i) for i, s in enumerate(series)]
        self.x_values = [_parse_cell(v) for v in x_values] if x_values is not None else None
        self.axis = axis or AxisOptions(label=x_label)
        self.x_label = str(x_label or self.axis.label)
        self.y_label = str(y_label)
        self.grid = grid or GridOptions(show_y=bool(show_grid))
        self.preferences = preferences or GraphPreferences(
            show_legend=bool(show_legend),
            value_labels=bool(value_labels),
            explode_indices=tuple(int(i) for i in explode_indices),
        )
        self.theme = theme or theme_for_sister(sister_id)
        self.sister_id = str(sister_id)
        self.speaker_notes = str(speaker_notes)
        self.title_pt = float(title_pt)
        self.label_pt = float(label_pt)
        self._eff_title_pt = self.title_pt
        self._eff_x_label_pt = self.label_pt
        self._eff_y_label_pt = self.label_pt
        self._eff_tick_pt = min(14.0, max(7.0, self.label_pt * 0.85))
        self._eff_legend_pt = min(13.0, max(8.0, self.label_pt * 0.95))
        self._x_label_box_h = 240.0
        self._y_label_box_w = 240.0
        self._y_lbl_w = 0.0
        self._cat_max_lbl_h = 430.0
        self._max_tick_w = 600.0
        self._tick_box_h = 220.0
        self._outer_x0 = float(MARGIN)
        self.warnings: list[str] = []

    @classmethod
    def from_csv(
        cls,
        path: Path | str,
        *,
        title: str = "",
        chart_type: str = "bar",
        **kwargs: Any,
    ) -> GraphDoc:
        csv_path = Path(path)
        if not csv_path.is_file():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            rows = [r for r in csv.reader(handle) if r and any(c.strip() for c in r)]
        if len(rows) < 2 or len(rows[0]) < 2:
            raise ValueError(f"CSV {csv_path} must have header row and at least 1 data row")
        headers = [h.strip() for h in rows[0][1:]]
        cats = [r[0].strip() for r in rows[1:]]
        sers = [
            DataSeries(name=hdr, values=[_parse_cell(r[i + 1]) if i + 1 < len(r) else None for r in rows[1:]])
            for i, hdr in enumerate(headers)
        ]
        return cls(title=title or csv_path.stem, chart_type=chart_type, categories=cats, series=sers, **kwargs)

    @classmethod
    def from_dif(
        cls,
        path: Path | str,
        *,
        title: str = "",
        chart_type: str = "bar",
        **kwargs: Any,
    ) -> GraphDoc:
        dif_path = Path(path)
        if not dif_path.is_file():
            raise FileNotFoundError(f"DIF file not found: {dif_path}")
        lines = dif_path.read_text(encoding="utf-8").splitlines()
        tuples: list[list[Any]] = []
        current: list[Any] = []
        in_tuple = False
        idx = 0
        while idx < len(lines):
            ln = lines[idx].strip()
            if ln == "-1,0":
                tag = lines[idx + 1].strip().upper() if idx + 1 < len(lines) else ""
                if tag == "BOT":
                    if in_tuple and current:
                        tuples.append(current)
                    current = []
                    in_tuple = True
                elif tag == "EOD":
                    if in_tuple and current:
                        tuples.append(current)
                    break
                idx += 2
            elif in_tuple and ln.startswith("1,0"):
                val_s = lines[idx + 1].strip().strip('"') if idx + 1 < len(lines) else ""
                current.append(val_s)
                idx += 2
            elif in_tuple and ln.startswith("0,"):
                num_tok = ln.split(",", 1)[1].strip()
                tag = lines[idx + 1].strip().upper() if idx + 1 < len(lines) else ""
                current.append(_parse_cell(num_tok) if tag == "V" else None)
                idx += 2
            else:
                idx += 1
        if len(tuples) < 2 or len(tuples[0]) < 2:
            raise ValueError(f"DIF {dif_path} lacks header and data tuples")
        headers = [str(h) for h in tuples[0][1:]]
        cats = [str(r[0]) for r in tuples[1:]]
        sers = [
            DataSeries(name=hdr, values=[_parse_cell(r[i + 1]) if i + 1 < len(r) else None for r in tuples[1:]])
            for i, hdr in enumerate(headers)
        ]
        return cls(title=title or dif_path.stem, chart_type=chart_type, categories=cats, series=sers, **kwargs)

    @classmethod
    def from_prn(
        cls,
        path: Path | str,
        *,
        title: str = "",
        chart_type: str = "line",
        **kwargs: Any,
    ) -> GraphDoc:
        prn_path = Path(path)
        if not prn_path.is_file():
            raise FileNotFoundError(f"PRN file not found: {prn_path}")
        rows = [shlex.split(ln) for ln in prn_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(rows) < 2 or len(rows[0]) < 2:
            raise ValueError(f"PRN {prn_path} must have header row and data rows")
        headers = rows[0][1:]
        cats = [r[0] for r in rows[1:]]
        sers = [
            DataSeries(name=hdr, values=[_parse_cell(r[i + 1]) if i + 1 < len(r) else None for r in rows[1:]])
            for i, hdr in enumerate(headers)
        ]
        return cls(title=title or prn_path.stem, chart_type=chart_type, categories=cats, series=sers, **kwargs)

    @classmethod
    def from_json(
        cls,
        path: Path | str,
        *,
        title: str = "",
        chart_type: str = "bar",
        metric_key: str | None = None,
        **kwargs: Any,
    ) -> GraphDoc:
        json_path = Path(path)
        if not json_path.is_file():
            raise FileNotFoundError(f"JSON evidence file not found: {json_path}")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        cats, sers = _select_json_rows(payload, metric_key=metric_key)
        return cls(title=title or json_path.stem, chart_type=chart_type, categories=cats, series=sers, **kwargs)

    def _validate_data(self) -> None:
        self.warnings.clear()
        if not self.categories or not self.series:
            raise ValueError("GraphDoc requires non-empty categories and series")
        non_none = [v for s in self.series for v in s.values if v is not None]
        if not non_none:
            raise ValueError("GraphDoc requires at least one non-null numeric value")
        if self.chart_type in NON_NEGATIVE_TYPES:
            for s in self.series:
                for idx, val in enumerate(s.values):
                    if val is not None and val < 0:
                        if self.preferences.allow_negative_abs:
                            self.warnings.append(f"Coerced negative value {val} in {s.name}[{idx}] to abs()")
                            s.values[idx] = abs(val)
                        else:
                            raise ValueError(f"Chart type {self.chart_type!r} forbids negative value {val} in {s.name!r}")

    def _series_color(self, idx: int) -> str:
        col = self.series[idx].color
        return col if col else DEFAULT_SERIES_PALETTE[idx % len(DEFAULT_SERIES_PALETTE)]

    def _compute_y_bounds(self) -> tuple[float, float]:
        vals = [v for s in self.series for v in s.values if v is not None]
        if self.chart_type == "v_stack_100":
            return (0.0, 100.0)
        if self.chart_type in ("v_stack", "h_stack", "stacked_area"):
            n = len(self.categories)
            totals = [sum((s.values[i] or 0.0) for s in self.series if i < len(s.values)) for i in range(n)]
            lo, hi = _nice_range(0.0, max(totals or [1.0]), include_zero=True)
        else:
            lo, hi = _nice_range(min(vals), max(vals), include_zero=(self.chart_type != "scatter"))
        if self.axis.minimum is not None:
            lo = float(self.axis.minimum)
        if self.axis.maximum is not None:
            hi = float(self.axis.maximum)
        return (lo, hi if hi > lo else lo + 1.0)

    def _fit_title_font(self, avail_w: float, max_h: float) -> tuple[float, float]:
        if not self.title:
            return (self.title_pt, 0.0)
        pt = self.title_pt
        th = 0.0
        while True:
            mw, th, _ = PresentationRenderer.measure_text(
                self.title, font_family=self.theme.font_serif, font_pt=pt, bold=True, max_width_vdi=avail_w,
            )
            if (mw <= avail_w + 2.0 and (th + 80.0) <= max_h) or pt <= 8.0:
                break
            pt = max(8.0, pt - 1.0)
        return (pt, th + 80.0)

    def _fit_axis_label(self, text: str, base_pt: float, max_w: float, max_h: float) -> tuple[float, float]:
        if not text:
            return (base_pt, 0.0)
        pt = base_pt
        mh = 0.0
        while True:
            mw, mh, _ = PresentationRenderer.measure_text(
                text, font_family=self.theme.font_sans, font_pt=pt, bold=True, wrap=False,
            )
            if (mw <= max_w + 2.0 and mh <= max_h) or pt <= 6.5:
                break
            pt = max(6.5, pt - 1.0)
        return (pt, mh)

    def _fit_tick_metrics(
        self,
        tick_strs: list[str],
        tick_pt: float,
        max_tw: float,
        tick_h: float,
        slot_limit: float,
        avail_bottom_h: float,
        is_horiz: bool,
    ) -> tuple[float, float, float]:
        while tick_pt > 6.5:
            fits_w = max_tw <= slot_limit
            fits_h = (tick_h + 20.0 <= avail_bottom_h) if is_horiz else (tick_h <= slot_limit)
            if (is_horiz and fits_w and fits_h) or (not is_horiz and fits_h):
                break
            tick_pt = max(6.5, tick_pt - 0.5)
            tick_dims = [
                PresentationRenderer.measure_text(t, font_family=self.theme.font_sans, font_pt=tick_pt, wrap=False)
                for t in tick_strs
            ]
            max_tw = max(d[0] for d in tick_dims)
            tick_h = max(d[1] for d in tick_dims)
        return (tick_pt, max_tw, tick_h)

    def _compute_layout_boxes(
        self,
        canvas: DrawPlusCanvas,
        region: tuple[float, float, float, float] | None,
        y_lo: float,
        y_hi: float,
    ) -> dict[str, list[float]]:
        ox0, oy0, ox1, oy1 = (
            [float(v) for v in region]
            if region is not None
            else [float(MARGIN), 340.0, float(canvas.width - MARGIN), float(canvas.height - 260.0)]
        )
        total_w = max(600.0, ox1 - ox0)
        total_h = max(600.0, oy1 - oy0)
        is_horiz = self.chart_type in ("h_cluster", "h_stack")
        is_non_cartesian = self.chart_type in ("pie", "map")
        has_legend = bool(self.preferences.show_legend and self.chart_type != "pie" and self.series)

        tick_pt = min(14.0, max(7.0, self.label_pt * 0.85))
        leg_pt = min(13.0, max(8.0, self.label_pt * 0.95))
        legend_h = max(300.0, leg_pt * 34.0) if has_legend else 0.0
        tick_strs = [_format_tick(y_lo + (y_hi - y_lo) * k / 4.0) for k in range(5)]
        tick_dims = [PresentationRenderer.measure_text(t, font_family=self.theme.font_sans, font_pt=tick_pt, wrap=False) for t in tick_strs]
        max_tw = max(d[0] for d in tick_dims)
        tick_h = max(d[1] for d in tick_dims)

        cat_max_h = (
            max(220.0, tick_h + 40.0)
            if is_horiz
            else min(620.0, 430.0 + max(0.0, self.label_pt - 9.5) * 10.0)
        )
        x_lbl_pt, xl_h = self._fit_axis_label(self.x_label, self.label_pt, max(400.0, total_w * 0.78), max(180.0, total_h * 0.14))
        x_lbl_pad = (xl_h + 90.0) if self.x_label else 0.0
        bottom_pad = (cat_max_h + 70.0 + x_lbl_pad) if not is_non_cartesian else 120.0

        min_plot_h = min(800.0, max(240.0, total_h * 0.32))
        max_title_h = max(240.0, min(total_h * 0.32, total_h - legend_h - bottom_pad - min_plot_h - 60.0))
        t_pt, title_h = self._fit_title_font(total_w, max_title_h)
        if total_h - title_h - legend_h - 60.0 - bottom_pad < min_plot_h:
            if has_legend:
                leg_pt = min(leg_pt, 9.5)
                legend_h = max(270.0, leg_pt * 28.0)
            if not is_horiz and not is_non_cartesian:
                cat_max_h = min(cat_max_h, max(240.0, total_h * 0.12))
            if self.x_label:
                x_lbl_pt, xl_h = self._fit_axis_label(self.x_label, x_lbl_pt, max(400.0, total_w * 0.78), max(140.0, total_h * 0.08))
                x_lbl_pad = xl_h + 90.0
            bottom_pad = (cat_max_h + 70.0 + x_lbl_pad) if not is_non_cartesian else 120.0
            max_title_h = max(220.0, min(total_h * 0.28, total_h - legend_h - bottom_pad - min_plot_h - 60.0))
            t_pt, title_h = self._fit_title_font(total_w, max_title_h)

        py0 = oy0 + title_h + legend_h + 60.0
        py1 = max(py0 + min_plot_h, oy1 - bottom_pad)
        if py1 > oy1 - bottom_pad and not is_non_cartesian:
            py1 = max(py0 + 180.0, oy1 - bottom_pad)
            if py1 > oy1 - bottom_pad:
                cat_max_h = max(160.0, oy1 - py1 - 70.0 - x_lbl_pad)

        avail_plot_h = max(200.0, py1 - py0 - 20.0)
        y_lbl_pt, yl_h = self._fit_axis_label(self.y_label, self.label_pt, avail_plot_h, max(180.0, total_w * 0.14))
        y_lbl_w = (yl_h + 100.0) if self.y_label else 0.0
        if is_horiz:
            h_cat_pt = min(13.0, max(8.5, self.label_pt * 0.9))
            cat_meas_w = max(
                (PresentationRenderer.measure_text(c, font_family=self.theme.font_sans, font_pt=h_cat_pt, wrap=False)[0] for c in self.categories),
                default=0.0,
            )
            cat_lbl_w = max(max_tw + 140.0, min(max(600.0, total_w * 0.30), cat_meas_w + 100.0))
            left_pad = max(max_tw + 140.0, cat_lbl_w) + y_lbl_w
        elif not is_non_cartesian:
            left_pad = max_tw + 140.0 + y_lbl_w
        else:
            left_pad = 100.0
        right_pad = max(140.0, max_tw / 2.0 + 30.0) if is_horiz else 140.0
        max_left = max(300.0, total_w - right_pad - max(400.0, total_w * 0.35))
        if not is_non_cartesian and left_pad > max_left:
            left_pad = max_left

        px0 = ox0 + left_pad
        px1 = max(px0 + 400.0, ox1 - right_pad)
        if self.x_label and not is_non_cartesian:
            x_lbl_pt, xl_h = self._fit_axis_label(self.x_label, x_lbl_pt, max(200.0, px1 - px0 - 20.0), max(140.0, xl_h + 20.0))

        self._eff_title_pt = t_pt
        self._eff_x_label_pt = x_lbl_pt
        self._eff_y_label_pt = y_lbl_pt
        self._eff_tick_pt = tick_pt
        self._eff_legend_pt = leg_pt
        self._x_label_box_h = xl_h + 60.0
        self._y_label_box_w = yl_h
        self._y_lbl_w = y_lbl_w
        self._cat_max_lbl_h = cat_max_h
        self._max_tick_w = max_tw
        self._tick_box_h = max(220.0, tick_h + 40.0)
        self._outer_x0 = ox0

        if not is_non_cartesian:
            slot_limit = ((px1 - px0) / 4.2) if is_horiz else ((py1 - py0) / 4.2)
            avail_bottom_h = max(120.0, oy1 - py1 - 70.0 - x_lbl_pad) if is_horiz else slot_limit
            tick_pt, max_tw, tick_h = self._fit_tick_metrics(
                tick_strs, tick_pt, max_tw, tick_h, slot_limit, avail_bottom_h, is_horiz,
            )
            self._eff_tick_pt = tick_pt
            self._max_tick_w = max_tw
            if is_horiz:
                self._tick_box_h = max(180.0, tick_h + 20.0)
            else:
                self._tick_box_h = min(max(180.0, tick_h + 20.0), max(120.0, (py1 - py0) / 4.2))
        return {
            "outer": [ox0, oy0, ox1, oy1],
            "title": [ox0, oy0, ox1, oy0 + title_h],
            "legend": [ox0, oy0 + title_h, ox1, oy0 + title_h + legend_h],
            "plot": [px0, py0, px1, py1],
        }

    def _draw_chrome_and_legend(self, canvas: DrawPlusCanvas, boxes: dict[str, list[float]]) -> None:
        if self.title:
            tb = boxes["title"]
            canvas.add_text(
                tb, self.title, font_pt=self._eff_title_pt, font_family=self.theme.font_serif,
                bold=True, align="center", valign="top", color=self.theme.title_color,
            )
        if self.preferences.show_legend and self.chart_type != "pie" and self.series:
            lb = boxes["legend"]
            lx0, ly0, lx1, _ = lb
            n = len(self.series)
            slot_w = min(2200.0, (lx1 - lx0) / max(1, n))
            start_x = (lx0 + lx1 - n * slot_w) / 2.0
            for idx, ser in enumerate(self.series):
                col = self._series_color(idx)
                sx = start_x + idx * slot_w
                canvas.add_rectangle([sx, ly0 + 50.0, sx + 150.0, ly0 + 190.0], fill=col, stroke="none", width=0.0)
                lbl = _truncate_label(ser.name, max(60.0, slot_w - 220.0), self.theme.font_sans, self._eff_legend_pt)
                canvas.add_text(
                    [sx + 185.0, ly0 + 25.0, sx + slot_w - 20.0, ly0 + 260.0],
                    lbl, font_pt=self._eff_legend_pt, align="left", valign="middle", color=self.theme.body_color, wrap=False,
                )

    def _draw_horiz_categories(self, canvas: DrawPlusCanvas, px0: float, py0: float, py1: float) -> None:
        n_cats = len(self.categories)
        slot_h = (py1 - py0) / n_cats
        h_cat_pt = min(13.0, max(8.5, self.label_pt * 0.9))
        cat_x0 = self._outer_x0 + self._y_lbl_w
        avail_cat_w = max(120.0, px0 - 60.0 - cat_x0)
        min_cat_h = max(
            (PresentationRenderer.measure_text(c, font_family=self.theme.font_sans, font_pt=6.5, wrap=False)[1] for c in self.categories),
            default=106.0,
        )
        stride = max(1, math.ceil((min_cat_h + 12.0) / max(1.0, slot_h)))
        box_h = max(min_cat_h + 4.0, slot_h * stride * 0.80)
        for i, cat in enumerate(self.categories):
            if i % stride != 0:
                continue
            cy = py0 + (i + 0.5) * slot_h
            pt_use = h_cat_pt
            while pt_use > 6.5:
                mw, mh, _ = PresentationRenderer.measure_text(
                    cat, font_family=self.theme.font_sans, font_pt=pt_use, wrap=False,
                )
                if mw <= avail_cat_w and mh <= box_h:
                    break
                pt_use = max(6.5, pt_use - 0.5)
            txt = _truncate_label(cat, max(80.0, avail_cat_w - 8.0), self.theme.font_sans, pt_use)
            canvas.add_text(
                [cat_x0, cy - box_h / 2.0, px0 - 60.0, cy + box_h / 2.0],
                txt, font_pt=pt_use, align="right", valign="middle", color=self.theme.body_color, wrap=False,
            )

    def _draw_axes_and_grid(
        self,
        canvas: DrawPlusCanvas,
        plot: list[float],
        y_lo: float,
        y_hi: float,
    ) -> None:
        px0, py0, px1, py1 = plot
        is_horiz = self.chart_type in ("h_cluster", "h_stack")
        canvas.add_rectangle(plot, fill=WHITE, stroke=STONE, width=10.0)
        tick_w = max(760.0, self._max_tick_w + 80.0)
        half_th = self._tick_box_h / 2.0
        tick_span = (px1 - px0) if is_horiz else (py1 - py0)
        tick_need = (self._max_tick_w + 20.0) if is_horiz else (self._tick_box_h - 10.0)
        tick_ks = (0, 1, 2, 3, 4) if (tick_span / 4.0 >= tick_need) else ((0, 2, 4) if (tick_span / 2.0 >= tick_need) else (0, 4))
        for k in tick_ks:
            frac = k / 4.0
            val = y_lo + (y_hi - y_lo) * frac
            lbl = _format_tick(val)
            if is_horiz:
                gx = px0 + (px1 - px0) * frac
                if self.grid.show_y and 0 < k < 4:
                    canvas.add_line([gx, py0], [gx, py1], stroke=LIGHT_DIVIDER_LINE, width=8.0, line_type=3)
                canvas.add_text([gx - tick_w / 2.0, py1 + 40.0, gx + tick_w / 2.0, py1 + 40.0 + self._tick_box_h], lbl, font_pt=self._eff_tick_pt, align="center", color=self.theme.muted_color, wrap=False)
            else:
                gy = py1 - (py1 - py0) * frac
                if self.grid.show_y and 0 < k < 4:
                    canvas.add_line([px0, gy], [px1, gy], stroke=LIGHT_DIVIDER_LINE, width=8.0, line_type=3)
                canvas.add_text([px0 - tick_w - 60.0, gy - half_th, px0 - 60.0, gy + half_th], lbl, font_pt=self._eff_tick_pt, align="right", valign="middle", color=self.theme.muted_color, wrap=False)

        n_cats = len(self.categories)
        max_lbl_h = self._cat_max_lbl_h
        if is_horiz:
            self._draw_horiz_categories(canvas, px0, py0, py1)
        else:
            slot_w = (px1 - px0) / n_cats
            base_pt = 8.5 if slot_w >= 1100.0 else (7.5 if slot_w >= 700.0 else 6.5)
            lbl_pt = min(self.label_pt, 14.0 if slot_w >= 1100.0 else (11.0 if slot_w >= 700.0 else 9.0)) if self.label_pt > 9.5 else base_pt
            for i, cat in enumerate(self.categories):
                cx = px0 + (i + 0.5) * slot_w
                box_w = max(140.0, slot_w * 0.90)
                pt_use = lbl_pt
                txt = cat
                use_wrap = True
                while pt_use >= 6.5:
                    mw, mh, _ = PresentationRenderer.measure_text(
                        cat, font_family=self.theme.font_sans, font_pt=pt_use, wrap=True, max_width_vdi=box_w,
                    )
                    if mw <= box_w and mh <= max_lbl_h:
                        break
                    pt_use -= 1.0
                else:
                    pt_use = 6.5
                    txt = _truncate_label(cat, max(80.0, box_w - 8.0), self.theme.font_sans, pt_use)
                    use_wrap = False
                canvas.add_text(
                    [cx - box_w / 2.0, py1 + 40.0, cx + box_w / 2.0, py1 + 40.0 + max_lbl_h],
                    txt, font_pt=pt_use, align="center", valign="top", color=self.theme.body_color, wrap=use_wrap,
                )
        if self.x_label:
            xl_y0 = py1 + 40.0 + (self._tick_box_h if is_horiz else max_lbl_h) + 30.0
            xl_txt = _truncate_label(self.x_label, max(120.0, px1 - px0 - 10.0), self.theme.font_sans, self._eff_x_label_pt, bold=True)
            canvas.add_text([px0, xl_y0, px1, xl_y0 + self._x_label_box_h], xl_txt, font_pt=self._eff_x_label_pt, bold=True, align="center", valign="top", color=self.theme.title_color, wrap=False)
        if self.y_label:
            if is_horiz:
                yl_cx = self._outer_x0 + self._y_label_box_w / 2.0 + 20.0
            else:
                yl_cx = max(self._outer_x0 + self._y_label_box_w / 2.0 + 20.0, px0 - self._max_tick_w - 140.0 - self._y_label_box_w / 2.0)
            yl_txt = _truncate_label(self.y_label, max(120.0, (py1 - py0) - 20.0), self.theme.font_sans, self._eff_y_label_pt, bold=True)
            canvas.add_text([yl_cx, (py0 + py1) / 2.0], yl_txt, font_pt=self._eff_y_label_pt, bold=True, align="center", valign="middle", rotation=90.0, color=self.theme.title_color, wrap=False)

    def _y_px(self, val: float, plot: list[float], y_lo: float, y_hi: float) -> float:
        _, py0, _, py1 = plot
        frac = (val - y_lo) / max(1e-12, y_hi - y_lo)
        return py1 - frac * (py1 - py0)

    def _first_populated_series(self) -> tuple[int, DataSeries]:
        n_cats = len(self.categories)
        for idx, ser in enumerate(self.series):
            if any(v is not None for v in ser.values[:n_cats]):
                return (idx, ser)
        raise ValueError(f"Chart type {self.chart_type!r} requires at least one non-null value in series")

    def _draw_pie(self, canvas: DrawPlusCanvas, plot: list[float]) -> None:
        px0, py0, px1, py1 = plot
        _, ser = self._first_populated_series()
        vals = [ser.values[i] if i < len(ser.values) else None for i in range(len(self.categories))]
        clean = [(i, self.categories[i], v) for i, v in enumerate(vals) if v is not None and v > 0]
        total = sum(v for _, _, v in clean)
        if total <= 0:
            raise ValueError("Pie chart requires positive total value")
        cx = px0 + (px1 - px0) * 0.34
        cy = (py0 + py1) / 2.0
        radius = min((px1 - px0) * 0.28, (py1 - py0) * 0.42)
        cur_deg = 900.0
        explode = set(self.preferences.explode_indices)
        leg_x = px0 + (px1 - px0) * 0.66
        row_h = min(420.0, (py1 - py0) / max(1, len(clean)))
        for row_idx, (idx, name, val) in enumerate(clean):
            sweep = 3600.0 * (val / total)
            end_deg = cur_deg - sweep
            col = DEFAULT_SERIES_PALETTE[idx % len(DEFAULT_SERIES_PALETTE)]
            mid_rad = math.radians(((cur_deg + end_deg) / 2.0) / 10.0)
            off = radius * 0.09 if idx in explode else 0.0
            sx = cx + off * math.cos(mid_rad)
            sy = cy - off * math.sin(mid_rad)
            canvas.add_pieslice(sx, sy, radius, end_deg % 3600.0, cur_deg % 3600.0, fill=col, stroke=WHITE, width=16.0)
            ly = py0 + row_idx * row_h + 40.0
            canvas.add_rectangle([leg_x, ly, leg_x + 140.0, ly + 140.0], fill=col, stroke="none", width=0.0)
            pct = 100.0 * val / total
            lbl = _truncate_label(f"{name}: {pct:.1f}%", max(200.0, px1 - leg_x - 200.0), self.theme.font_sans, 9.0)
            canvas.add_text([leg_x + 180.0, ly - 20.0, px1, ly + row_h - 20.0], lbl, font_pt=9.0, align="left", valign="top", color=self.theme.body_color)
            cur_deg = end_deg

    def _draw_bars(self, canvas: DrawPlusCanvas, plot: list[float], y_lo: float, y_hi: float) -> None:
        px0, py0, px1, py1 = plot
        n_cats, n_ser = len(self.categories), len(self.series)
        is_horiz = self.chart_type in ("h_cluster", "h_stack")
        is_stack = self.chart_type in ("v_stack", "h_stack", "v_stack_100")
        slot = ((py1 - py0) if is_horiz else (px1 - px0)) / n_cats
        zero_y = self._y_px(0.0, plot, y_lo, y_hi)
        if self.chart_type == "deviation_bar":
            canvas.add_line([px0, zero_y], [px1, zero_y], stroke=self.theme.title_color, width=14.0)

        for i in range(n_cats):
            col_tot = sum((s.values[i] or 0.0) for s in self.series if i < len(s.values)) or 1.0
            acc = 0.0
            for s_idx, ser in enumerate(self.series):
                val = ser.values[i] if i < len(ser.values) else None
                if val is None:
                    continue
                col = self._series_color(s_idx)
                if is_horiz:
                    bw = (slot * 0.72) if is_stack else (slot * 0.72 / n_ser)
                    by0 = py0 + i * slot + slot * 0.14 + (0.0 if is_stack else s_idx * bw)
                    v_use = (100.0 * val / col_tot) if self.chart_type == "v_stack_100" else val
                    base_v = acc if is_stack else 0.0
                    x_start = px0 + ((base_v - y_lo) / max(1e-12, y_hi - y_lo)) * (px1 - px0)
                    x_end = px0 + ((base_v + v_use - y_lo) / max(1e-12, y_hi - y_lo)) * (px1 - px0)
                    canvas.add_rectangle([min(x_start, x_end), by0, max(x_start, x_end), by0 + bw], fill=col, stroke=WHITE, width=8.0)
                    if is_stack:
                        acc += v_use
                else:
                    bw = (slot * 0.66) if is_stack else (slot * 0.72 / n_ser)
                    bx0 = px0 + i * slot + (slot * 0.17 if is_stack else slot * 0.14 + s_idx * bw)
                    v_use = (100.0 * val / col_tot) if self.chart_type == "v_stack_100" else val
                    y_top = self._y_px(acc + v_use if is_stack else v_use, plot, y_lo, y_hi)
                    y_bot = self._y_px(acc, plot, y_lo, y_hi) if is_stack else zero_y
                    if self.chart_type == "deviation_bar":
                        col = JADE if val >= 0 else RUBY
                    canvas.add_rectangle([bx0, min(y_top, y_bot), bx0 + bw, max(y_top, y_bot)], fill=col, stroke=WHITE, width=8.0)
                    if self.chart_type == "bar_3d":
                        dx, dy = min(140.0, bw * 0.25), min(120.0, bw * 0.22)
                        top_poly = [[bx0, y_top], [bx0 + dx, y_top - dy], [bx0 + bw + dx, y_top - dy], [bx0 + bw, y_top]]
                        side_poly = [[bx0 + bw, y_top], [bx0 + bw + dx, y_top - dy], [bx0 + bw + dx, y_bot - dy], [bx0 + bw, y_bot]]
                        canvas.add_polygon(top_poly, fill=mix_hex(col, WHITE, 0.3), stroke=WHITE, width=6.0)
                        canvas.add_polygon(side_poly, fill=mix_hex(col, "#000000", 0.25), stroke=WHITE, width=6.0)
                    acc += v_use

    def _draw_stacked_area(self, canvas: DrawPlusCanvas, plot: list[float], y_lo: float, y_hi: float) -> None:
        px0, _, px1, _ = plot
        n_cats = len(self.categories)
        slot_w = (px1 - px0) / n_cats
        prev_vals = [0.0] * n_cats
        for s_idx, ser in enumerate(self.series):
            col = self._series_color(s_idx)
            upper_pts: list[list[float]] = []
            lower_pts: list[list[float]] = []
            for i in range(n_cats):
                v = ser.values[i] if i < len(ser.values) else None
                if v is None:
                    if len(upper_pts) >= 2:
                        canvas.add_polygon([*upper_pts, *reversed(lower_pts)], fill=mix_hex(col, WHITE, 0.35), stroke=col, width=14.0, alpha=0.80)
                    elif len(upper_pts) == 1:
                        half_bw = max(35.0, slot_w * 0.14)
                        ux, uy = upper_pts[0]
                        ly = lower_pts[0][1]
                        canvas.add_rectangle([ux - half_bw, min(uy, ly), ux + half_bw, max(uy, ly)], fill=mix_hex(col, WHITE, 0.35), stroke=col, width=14.0, alpha=0.80)
                        canvas.add_circle(ux, uy, 55.0, fill=col, stroke=WHITE, width=10.0)
                    upper_pts, lower_pts = [], []
                    continue
                xv = px0 + (i + 0.5) * slot_w
                top_v = prev_vals[i] + v
                upper_pts.append([xv, self._y_px(top_v, plot, y_lo, y_hi)])
                lower_pts.append([xv, self._y_px(prev_vals[i], plot, y_lo, y_hi)])
                prev_vals[i] = top_v
            if len(upper_pts) >= 2:
                canvas.add_polygon([*upper_pts, *reversed(lower_pts)], fill=mix_hex(col, WHITE, 0.35), stroke=col, width=14.0, alpha=0.80)
            elif len(upper_pts) == 1:
                half_bw = max(35.0, slot_w * 0.14)
                ux, uy = upper_pts[0]
                ly = lower_pts[0][1]
                canvas.add_rectangle([ux - half_bw, min(uy, ly), ux + half_bw, max(uy, ly)], fill=mix_hex(col, WHITE, 0.35), stroke=col, width=14.0, alpha=0.80)
                canvas.add_circle(ux, uy, 55.0, fill=col, stroke=WHITE, width=10.0)

    def _draw_series_lines_and_points(self, canvas: DrawPlusCanvas, plot: list[float], y_lo: float, y_hi: float) -> None:
        px0, _, px1, py1 = plot
        n_cats = len(self.categories)
        slot_w = (px1 - px0) / n_cats
        zero_y = self._y_px(0.0, plot, y_lo, y_hi)
        bar_series = self.series[:-1] if (self.chart_type == "bar_line" and len(self.series) > 1) else []
        for s_idx, ser in enumerate(bar_series):
            col = self._series_color(s_idx)
            bw = slot_w * 0.62 / max(1, len(bar_series))
            for i in range(n_cats):
                v = ser.values[i] if i < len(ser.values) else None
                if v is None:
                    continue
                bx0 = px0 + i * slot_w + slot_w * 0.19 + s_idx * bw
                yt = self._y_px(v, plot, y_lo, y_hi)
                canvas.add_rectangle([bx0, min(yt, zero_y), bx0 + bw, max(yt, zero_y)], fill=col, stroke=WHITE, width=8.0)

        line_indices = [len(self.series) - 1] if (self.chart_type == "bar_line" and len(self.series) > 1) else list(range(len(self.series)))
        for s_idx in line_indices:
            ser = self.series[s_idx]
            col = self._series_color(s_idx)
            segments: list[list[list[float]]] = []
            cur_seg: list[list[float]] = []
            for i in range(n_cats):
                v = ser.values[i] if i < len(ser.values) else None
                if v is None:
                    if cur_seg:
                        segments.append(cur_seg)
                        cur_seg = []
                    continue
                xv = px0 + (i + 0.5) * slot_w
                if self.chart_type == "scatter" and self.x_values and i < len(self.x_values):
                    x_raw = self.x_values[i]
                    if x_raw is not None:
                        x_nums = [x for x in self.x_values if x is not None]
                        x_min, x_max = min(x_nums), max(x_nums)
                        frac_x = (float(x_raw) - x_min) / max(1e-12, x_max - x_min) if x_max > x_min else 0.5
                        xv = px0 + slot_w * 0.3 + frac_x * ((px1 - px0) - slot_w * 0.6)
                yv = self._y_px(v, plot, y_lo, y_hi)
                cur_seg.append([xv, yv])
            if cur_seg:
                segments.append(cur_seg)

            for seg in segments:
                if self.chart_type in ("area", "stacked_area"):
                    if len(seg) >= 2:
                        poly = [[seg[0][0], zero_y], *seg, [seg[-1][0], zero_y]]
                        canvas.add_polygon(poly, fill=mix_hex(col, WHITE, 0.45), stroke=col, width=16.0, alpha=0.75)
                    elif len(seg) == 1:
                        half_bw = max(35.0, slot_w * 0.14)
                        px, py = seg[0]
                        canvas.add_rectangle([px - half_bw, min(py, zero_y), px + half_bw, max(py, zero_y)], fill=mix_hex(col, WHITE, 0.45), stroke=col, width=14.0, alpha=0.75)
                        canvas.add_circle(px, py, 55.0, fill=col, stroke=WHITE, width=10.0)
                elif self.chart_type == "step":
                    if len(seg) >= 2:
                        step_pts: list[list[float]] = [seg[0]]
                        for p in seg[1:]:
                            step_pts.append([p[0], step_pts[-1][1]])
                            step_pts.append(p)
                        canvas.add_polyline(step_pts, stroke=col, width=ser.line_width)
                elif self.chart_type == "stick":
                    for pt in seg:
                        canvas.add_line([pt[0], zero_y], pt, stroke=col, width=18.0)
                        canvas.add_circle(pt[0], pt[1], 55.0, fill=col, stroke=WHITE, width=10.0)
                elif self.chart_type != "scatter" and len(seg) >= 2:
                    canvas.add_polyline(seg, stroke=col, width=ser.line_width)
                if self.chart_type in ("line", "scatter", "bar_line", "step"):
                    for pt in seg:
                        canvas.add_circle(pt[0], pt[1], 55.0, fill=col, stroke=WHITE, width=10.0)

    def _draw_symbol(self, canvas: DrawPlusCanvas, plot: list[float], y_hi: float) -> None:
        px0, py0, px1, py1 = plot
        n_cats = len(self.categories)
        slot_w = (px1 - px0) / n_cats
        s_idx, ser = self._first_populated_series()
        col = self._series_color(s_idx)
        for i in range(n_cats):
            v = ser.values[i] if i < len(ser.values) else None
            if v is None:
                continue
            count = max(1, min(6, round(6.0 * max(0.0, v) / max(1e-12, y_hi))))
            cx = px0 + (i + 0.5) * slot_w
            step_y = (py1 - py0) / 7.0
            for k in range(count):
                cy = py1 - (k + 0.7) * step_y
                canvas.add_polygon(petal_points(cx - 110.0, cy, 0.0, 220.0, 75.0, n=12), fill=col, stroke=WHITE, width=8.0)

    def _draw_map(self, canvas: DrawPlusCanvas, plot: list[float]) -> None:
        px0, py0, px1, py1 = plot
        n = len(self.categories)
        cols = min(4, max(1, math.ceil(math.sqrt(n))))
        rows = max(1, math.ceil(n / cols))
        rw = (px1 - px0) / cols
        rh = (py1 - py0) / rows
        _, ser = self._first_populated_series()
        vals = [ser.values[i] if i < len(ser.values) else None for i in range(n)]
        non_none = [v for v in vals if v is not None]
        vmin, vmax = (min(non_none), max(non_none)) if non_none else (0.0, 1.0)
        bands = (JADE_SOFT, JADE, GOLD, ROSE, RUBY)
        for i, cat in enumerate(self.categories):
            c, r = i % cols, i // cols
            rx0, ry0 = px0 + c * rw + 50.0, py0 + r * rh + 50.0
            rx1, ry1 = px0 + (c + 1) * rw - 50.0, py0 + (r + 1) * rh - 50.0
            poly = [[rx0 + 40.0, ry0], [rx1, ry0 + 30.0], [rx1 - 35.0, ry1], [rx0, ry1 - 25.0]]
            v = vals[i]
            t = 0.0 if (v is None or vmax <= vmin) else (v - vmin) / (vmax - vmin)
            fill = SLATE_SOFT if v is None else bands[min(4, int(t * 4.99))]
            canvas.add_polygon(poly, fill=fill, stroke=WHITE, width=16.0)
            txt = f"{cat}\n{_format_tick(v) if v is not None else 'N/A'}"
            canvas.add_text([rx0 + 80.0, ry0 + 80.0, rx1 - 80.0, ry1 - 80.0], txt, font_pt=9.0, bold=True, align="center", valign="middle", color="#111827")

    def compile(
        self,
        canvas: DrawPlusCanvas,
        *,
        region: tuple[float, float, float, float] | None = None,
    ) -> DrawPlusCanvas:
        """Compile this graph into `canvas` with collision-free auto-sized plot area."""
        self._validate_data()
        y_lo, y_hi = self._compute_y_bounds()
        boxes = self._compute_layout_boxes(canvas, region, y_lo, y_hi)
        self._draw_chrome_and_legend(canvas, boxes)
        plot = boxes["plot"]

        if self.chart_type == "pie":
            self._draw_pie(canvas, plot)
        elif self.chart_type == "map":
            self._draw_map(canvas, plot)
        else:
            self._draw_axes_and_grid(canvas, plot, y_lo, y_hi)
            if self.chart_type in ("v_cluster", "h_cluster", "v_stack", "h_stack", "v_stack_100", "deviation_bar", "bar_3d"):
                self._draw_bars(canvas, plot, y_lo, y_hi)
            elif self.chart_type == "stacked_area":
                self._draw_stacked_area(canvas, plot, y_lo, y_hi)
            elif self.chart_type == "symbol":
                self._draw_symbol(canvas, plot, y_hi)
            else:
                self._draw_series_lines_and_points(canvas, plot, y_lo, y_hi)

        if self.speaker_notes and not canvas.speaker_notes:
            canvas.speaker_notes = self.speaker_notes
        return canvas


__all__ = [
    "CHART_TYPE_ALIASES",
    "DEFAULT_SERIES_PALETTE",
    "NON_NEGATIVE_TYPES",
    "AxisOptions",
    "DataSeries",
    "GraphDoc",
    "GraphPreferences",
    "GridOptions",
    "normalize_chart_type",
]
