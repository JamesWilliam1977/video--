"""
 @file
 @brief Scope dock panels: luma/RGB waveform, RGB histogram, and audio meters.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import math

from qt_api import (
    Qt, pyqtSlot,
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QImage, QPainter, QColor, QPen, QBrush,
    QComboBox, QRect,
)

# ─── Persistent settings keys ────────────────────────────────────────────────
_S_WAVE_MODE  = "scope-waveform-mode"     # luma|red|green|blue|rgb_overlay|rgb_parade
_S_WAVE_COLOR = "scope-waveform-color"    # green|white|orange
_S_WAVE_IRE   = "scope-waveform-ire"      # True|False
_S_HIST_CH    = "scope-histogram-channel" # rgba|luma|red|green|blue
_S_HIST_SCALE = "scope-histogram-scale"   # log|linear


def _settings():
    try:
        from classes.app import get_app
        return get_app().get_settings()
    except Exception:
        return None


def _get(key, default):
    s = _settings()
    if s is None:
        return default
    v = s.get(key)
    return v if v is not None else default


def _set(key, value):
    s = _settings()
    if s is not None:
        s.set(key, value)


# ─── Waveform painter ────────────────────────────────────────────────────────

class WaveformWidget(QWidget):
    """Luma / RGB waveform density heatmap painter."""

    _LUMA_COLORS = {
        "green":  (0,   220,  80),
        "white":  (220, 220, 220),
        "orange": (255, 160,   0),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data  = None
        self._mode  = _get(_S_WAVE_MODE,  "luma")
        self._color = _get(_S_WAVE_COLOR, "green")
        self._ire   = _get(_S_WAVE_IRE,   True)
        self.setMinimumSize(120, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)

    def set_mode(self,  v): self._mode  = v; _set(_S_WAVE_MODE,  v); self.update()
    def set_color(self, v): self._color = v; _set(_S_WAVE_COLOR, v); self.update()
    def set_ire(self,   v): self._ire   = v; _set(_S_WAVE_IRE,   v); self.update()

    def update_data(self, video_data):
        self._data = video_data
        self.update()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _build_img(self, flat, columns, bins, rgb):
        """Build a columns×bins RGB888 QImage from a waveform flat array."""
        if not flat or len(flat) != columns * bins:
            return None
        max_val = max(flat) or 1
        r0, g0, b0 = rgb
        buf = bytearray(columns * bins * 3)
        for col in range(columns):
            base = col * bins
            for b in range(bins):
                count = flat[base + b]
                if not count:
                    continue
                t = min(255, count * 255 // max_val)
                row = bins - 1 - b
                idx = (row * columns + col) * 3
                buf[idx]     = r0 * t // 255
                buf[idx + 1] = g0 * t // 255
                buf[idx + 2] = b0 * t // 255
        return QImage(bytes(buf), columns, bins, columns * 3, QImage.Format_RGB888)

    # ── paint ────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(0, 0, 0))

        if not self._data or not self._data.get("present"):
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Video")
            return

        wf      = self._data.get("waveform", {})
        columns = wf.get("columns", 256)
        bins    = wf.get("bins",    256)
        mode    = self._mode

        if mode == "rgb_parade":
            band_w = w // 3
            for i, (key, rgb) in enumerate([
                ("red",   (220,  60,  60)),
                ("green", ( 60, 190,  60)),
                ("blue",  ( 60, 120, 220)),
            ]):
                img = self._build_img(wf.get(key, []), columns, bins, rgb)
                if img:
                    painter.drawImage(QRect(i * band_w, 0, band_w, h), img)

            # Thin dividers between bands
            painter.setPen(QPen(QColor(50, 50, 50), 1))
            painter.drawLine(band_w,     0, band_w,     h)
            painter.drawLine(band_w * 2, 0, band_w * 2, h)

        elif mode == "rgb_overlay":
            r_flat = wf.get("red",   [])
            g_flat = wf.get("green", [])
            b_flat = wf.get("blue",  [])
            if r_flat and len(r_flat) == columns * bins:
                max_val = max(max(r_flat), max(g_flat) if g_flat else 0,
                              max(b_flat) if b_flat else 0) or 1
                buf = bytearray(columns * bins * 3)
                for col in range(columns):
                    base = col * bins
                    for b in range(bins):
                        rv = r_flat[base + b]
                        gv = g_flat[base + b] if g_flat else 0
                        bv = b_flat[base + b] if b_flat else 0
                        if not (rv or gv or bv):
                            continue
                        row = bins - 1 - b
                        idx = (row * columns + col) * 3
                        buf[idx]     = min(255, rv * 220 // max_val)
                        buf[idx + 1] = min(255, gv * 190 // max_val)
                        buf[idx + 2] = min(255, bv * 220 // max_val)
                img = QImage(bytes(buf), columns, bins, columns * 3,
                             QImage.Format_RGB888)
                painter.drawImage(self.rect(), img)

        else:
            # Single-channel modes: luma, red, green, blue
            rgb_map = {
                "luma":  self._LUMA_COLORS.get(self._color, (0, 220, 80)),
                "red":   (220,  60,  60),
                "green": ( 60, 190,  60),
                "blue":  ( 60, 120, 220),
            }
            flat = wf.get(mode if mode != "luma" else "luma", [])
            img  = self._build_img(flat, columns, bins, rgb_map.get(mode, (200, 200, 200)))
            if img:
                painter.drawImage(self.rect(), img)

        # IRE reference lines at 10 / 50 / 90 %
        if self._ire:
            painter.setPen(QPen(QColor(60, 60, 60), 1, Qt.DashLine))
            for pct in (0.1, 0.5, 0.9):
                y = int(h * (1.0 - pct))
                painter.drawLine(0, y, w, y)


# ─── Histogram painter ───────────────────────────────────────────────────────

class HistogramWidget(QWidget):
    """RGB + luma overlay histogram with channel and scale filters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data    = None
        self._channel = _get(_S_HIST_CH,    "rgba")
        self._scale   = _get(_S_HIST_SCALE, "log")
        self.setMinimumSize(120, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)

    def set_channel(self, v): self._channel = v; _set(_S_HIST_CH,    v); self.update()
    def set_scale(self,   v): self._scale   = v; _set(_S_HIST_SCALE, v); self.update()

    def update_data(self, video_data):
        self._data = video_data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(20, 20, 20))

        if not self._data or not self._data.get("present"):
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Video")
            return

        hist  = self._data.get("histogram", {})
        luma  = hist.get("luma",  [])
        red   = hist.get("red",   [])
        green = hist.get("green", [])
        blue  = hist.get("blue",  [])

        if not luma:
            return

        ch = self._channel
        if ch == "rgba":
            to_draw = [
                (blue,  QColor(60,  60,  220, 140)),
                (green, QColor(60,  190,  60, 140)),
                (red,   QColor(220,  60,  60, 140)),
                (luma,  QColor(210, 210, 210,  70)),
            ]
        elif ch == "luma":
            to_draw = [(luma,  QColor(210, 210, 210, 200))]
        elif ch == "red":
            to_draw = [(red,   QColor(220,  60,  60, 200))]
        elif ch == "green":
            to_draw = [(green, QColor( 60, 190,  60, 200))]
        elif ch == "blue":
            to_draw = [(blue,  QColor( 60,  60, 220, 200))]
        else:
            return

        all_vals = [v for vals, _ in to_draw for v in vals]
        max_val  = max(all_vals) if all_vals else 1
        if not max_val:
            max_val = 1
        use_log  = (self._scale == "log")
        log_max  = math.log1p(max_val)
        bins     = len(luma)
        bar_w    = max(1, w // bins)

        painter.setPen(Qt.NoPen)
        for vals, color in to_draw:
            painter.setBrush(QBrush(color))
            for i, v in enumerate(vals):
                if not v:
                    continue
                x     = i * w // bins
                bar_h = int(math.log1p(v) / log_max * h) if use_log else v * h // max_val
                painter.drawRect(x, h - bar_h, bar_w, bar_h)


# ─── Audio meter painter ─────────────────────────────────────────────────────

class AudioMeterWidget(QWidget):
    """Per-channel RMS/peak VU bars with clip indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self.setMinimumSize(60, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)

    def update_data(self, audio_data):
        self._data = audio_data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(20, 20, 20))

        if not self._data or not self._data.get("present"):
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Audio")
            return

        summary   = self._data.get("summary", {})
        peak_vals = summary.get("peak", [])
        rms_vals  = summary.get("rms", [])
        clipped   = summary.get("clipped_samples", [])
        channels  = self._data.get("channels", 0)

        if not channels:
            return

        gap   = 4
        bar_w = max(8, (w - (channels + 1) * gap) // channels)

        for ch in range(channels):
            x             = gap + ch * (bar_w + gap)
            rms           = rms_vals[ch]  if ch < len(rms_vals)  else 0.0
            peak          = peak_vals[ch] if ch < len(peak_vals) else 0.0
            clipped_count = clipped[ch]   if ch < len(clipped)   else 0

            painter.fillRect(x, 0, bar_w, h, QColor(40, 40, 40))

            rms_h = int(rms * h)
            for row in range(rms_h):
                ratio = row / h
                if ratio > 0.8:
                    color = QColor(220, 50, 50)
                elif ratio > 0.6:
                    color = QColor(220, 200, 50)
                else:
                    color = QColor(50, 200, 50)
                painter.fillRect(x, h - row - 1, bar_w, 1, color)

            if peak > 0:
                peak_y = int((1.0 - peak) * h)
                painter.setPen(QPen(QColor(255, 240, 80), 2))
                painter.drawLine(x, peak_y, x + bar_w - 1, peak_y)

            if clipped_count > 0:
                painter.fillRect(x, 0, bar_w, 5, QColor(255, 40, 40))


# ─── Filter toolbar helpers ──────────────────────────────────────────────────

def _make_combo(parent, items):
    """Create a QComboBox from a list of (data_key, display_label) tuples."""
    cb = QComboBox(parent)
    cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    for key, label in items:
        cb.addItem(label, key)
    return cb


def _restore_combo(combo, value):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return


# ─── Waveform dock content (painter + toolbar) ───────────────────────────────

class WaveformDockContent(QWidget):
    """Waveform dock widget: filter toolbar above the waveform painter."""

    _MODES = [
        ("luma",        "Luma"),
        ("rgb_overlay", "RGB Overlay"),
        ("rgb_parade",  "RGB Parade"),
        ("red",         "Red"),
        ("green",       "Green"),
        ("blue",        "Blue"),
    ]
    _COLORS = [
        ("green",  "Green"),
        ("white",  "White"),
        ("orange", "Orange"),
    ]
    _IRE = [
        (True,  "IRE: On"),
        (False, "IRE: Off"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.setSpacing(4)

        toolbar = QWidget(self)
        toolbar.setFocusPolicy(Qt.NoFocus)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        self._mode_cb  = _make_combo(toolbar, self._MODES)
        self._color_cb = _make_combo(toolbar, self._COLORS)
        self._ire_cb   = _make_combo(toolbar, self._IRE)
        tl.addWidget(self._mode_cb)
        tl.addWidget(self._color_cb)
        tl.addWidget(self._ire_cb)
        tl.addStretch()

        self.waveform = WaveformWidget(self)
        layout.addWidget(toolbar)
        layout.addWidget(self.waveform)

        # Restore saved state
        _restore_combo(self._mode_cb,  _get(_S_WAVE_MODE,  "luma"))
        _restore_combo(self._color_cb, _get(_S_WAVE_COLOR, "green"))
        _restore_combo(self._ire_cb,   _get(_S_WAVE_IRE,   True))
        self._sync_color_visibility()

        self._mode_cb.currentIndexChanged.connect(self._on_mode)
        self._color_cb.currentIndexChanged.connect(self._on_color)
        self._ire_cb.currentIndexChanged.connect(self._on_ire)

    def _sync_color_visibility(self):
        self._color_cb.setVisible(self._mode_cb.currentData() == "luma")

    def _on_mode(self):
        self.waveform.set_mode(self._mode_cb.currentData())
        self._sync_color_visibility()

    def _on_color(self):
        self.waveform.set_color(self._color_cb.currentData())

    def _on_ire(self):
        self.waveform.set_ire(self._ire_cb.currentData())

    @pyqtSlot(dict)
    def update_data(self, video_data):
        self.waveform.update_data(video_data)


# ─── Histogram dock content (painter + toolbar) ──────────────────────────────

class HistogramDockContent(QWidget):
    """Histogram dock widget: filter toolbar above the histogram painter."""

    _CHANNELS = [
        ("rgba",  "All Channels"),
        ("luma",  "Luma"),
        ("red",   "Red"),
        ("green", "Green"),
        ("blue",  "Blue"),
    ]
    _SCALES = [
        ("log",    "Logarithmic"),
        ("linear", "Linear"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.setSpacing(4)

        toolbar = QWidget(self)
        toolbar.setFocusPolicy(Qt.NoFocus)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        self._ch_cb    = _make_combo(toolbar, self._CHANNELS)
        self._scale_cb = _make_combo(toolbar, self._SCALES)
        tl.addWidget(self._ch_cb)
        tl.addWidget(self._scale_cb)
        tl.addStretch()

        self.histogram = HistogramWidget(self)
        layout.addWidget(toolbar)
        layout.addWidget(self.histogram)

        _restore_combo(self._ch_cb,    _get(_S_HIST_CH,    "rgba"))
        _restore_combo(self._scale_cb, _get(_S_HIST_SCALE, "log"))

        self._ch_cb.currentIndexChanged.connect(self._on_channel)
        self._scale_cb.currentIndexChanged.connect(self._on_scale)

    def _on_channel(self):
        self.histogram.set_channel(self._ch_cb.currentData())

    def _on_scale(self):
        self.histogram.set_scale(self._scale_cb.currentData())

    @pyqtSlot(dict)
    def update_data(self, video_data):
        self.histogram.update_data(video_data)
