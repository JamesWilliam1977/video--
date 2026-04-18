"""
 @file
 @brief Rich popup editors for ColorGrade curve and wheel properties
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

import copy
import math

from qt_api import Qt, QPointF, QRectF, QSize, pyqtSignal, QShortcut, QKeySequence, QTimer
from qt_api import QColor, QPainter, QPen, QBrush, QPainterPath, QConicalGradient
from qt_api import QWidget, QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QAction
from qt_api import QDialogButtonBox, QFrame, QSlider, QDoubleSpinBox, QGridLayout

from classes.app import get_app
from windows.views.menu import StyledContextMenu
from windows.color_picker import ColorPicker


def default_curve_data():
    return {"enabled": True, "points": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]}


def normalize_curve_data(data):
    data = data or {}
    points = data.get("points") or []
    parsed = []
    for point in points:
        try:
            x = max(0.0, min(1.0, float(point.get("x", 0.0))))
            y = max(0.0, min(1.0, float(point.get("y", 0.0))))
            parsed.append({"x": x, "y": y})
        except (TypeError, ValueError, AttributeError):
            continue
    if not parsed:
        return default_curve_data()
    parsed.sort(key=lambda point: point["x"])
    if parsed[0]["x"] > 0.0:
        parsed.insert(0, {"x": 0.0, "y": parsed[0]["y"]})
    else:
        parsed[0]["x"] = 0.0
    if parsed[-1]["x"] < 1.0:
        parsed.append({"x": 1.0, "y": parsed[-1]["y"]})
    else:
        parsed[-1]["x"] = 1.0
    return {"enabled": bool(data.get("enabled", True)), "points": parsed}


def default_wheels_data():
    return {
        "enabled": True,
        "global": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
        "shadows": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
        "midtones": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
        "highlights": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
    }


NEUTRAL_WHEEL_COLOR = "#ffffff"
NEUTRAL_PUCK_COLOR = "#ffffff"
ACHROMATIC_SATURATION_THRESHOLD = 0.02


def is_neutral_wheel(data):
    try:
        return float((data or {}).get("amount", 0.0)) <= 0.0001
    except (TypeError, ValueError, AttributeError):
        return True


def display_wheel_color(data):
    if is_neutral_wheel(data):
        return QColor(Qt.white)
    color = QColor((data or {}).get("color", NEUTRAL_WHEEL_COLOR))
    return color if color.isValid() else QColor(Qt.white)


def selected_wheel_color(data):
    color = QColor((data or {}).get("color", NEUTRAL_WHEEL_COLOR))
    return color if color.isValid() else QColor(Qt.white)


def is_achromatic_color(color):
    if not isinstance(color, QColor) or not color.isValid():
        return True
    saturation = color.hsvSaturationF()
    if saturation < 0.0:
        saturation = color.saturationF()
    return saturation < ACHROMATIC_SATURATION_THRESHOLD


def puck_display_color(data):
    amount = 0.0
    try:
        amount = max(0.0, min(1.0, float((data or {}).get("amount", 0.0))))
    except (TypeError, ValueError, AttributeError):
        pass

    base = QColor(NEUTRAL_PUCK_COLOR)
    if amount <= 0.0001:
        return base

    target = display_wheel_color(data)
    return QColor(
        int(round(base.red() + ((target.red() - base.red()) * amount))),
        int(round(base.green() + ((target.green() - base.green()) * amount))),
        int(round(base.blue() + ((target.blue() - base.blue()) * amount))),
    )


def normalize_single_wheel_data(data):
    normalized = normalize_wheels_data({"global": data})
    return copy.deepcopy(normalized["global"])


def normalize_wheels_data(data):
    data = copy.deepcopy(data or {})
    normalized = default_wheels_data()
    normalized["enabled"] = bool(data.get("enabled", True))
    for name, wheel in normalized.items():
        if name == "enabled":
            continue
        source = data.get(name) or {}
        color = QColor(source.get("color", wheel["color"]))
        wheel["color"] = color.name() if color.isValid() else "#ffffff"
        try:
            wheel["amount"] = max(0.0, min(1.0, float(source.get("amount", wheel["amount"]))))
        except (TypeError, ValueError):
            pass
        try:
            wheel["luma"] = max(-1.0, min(1.0, float(source.get("luma", wheel["luma"]))))
        except (TypeError, ValueError):
            pass
        if wheel["amount"] <= 0.0001:
            wheel["amount"] = 0.0
            wheel["color"] = NEUTRAL_WHEEL_COLOR
    return normalized


class ColorWheelControl(QWidget):
    changed = pyqtSignal()
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, wheel_data=None, parent=None):
        super().__init__(parent)
        self._data = normalize_single_wheel_data(wheel_data)
        self._dragging = False
        self.setMinimumSize(QSize(96, 96))

    def wheel_data(self):
        return copy.deepcopy(self._data)

    def set_wheel_data(self, wheel_data):
        self._data = normalize_single_wheel_data(wheel_data)
        self.update()
        self.changed.emit()

    def _center_and_radius(self):
        radius = min(self.width(), self.height()) * 0.42
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        return center, radius

    def _inner_radius(self):
        _, radius = self._center_and_radius()
        ring_width = max(6.0, radius * 0.16)
        return max(1.0, radius - ring_width - 1.0)

    def _puck_position(self):
        center, _ = self._center_and_radius()
        radius = self._inner_radius()
        color = display_wheel_color(self._data)
        hue = color.hueF() if color.hueF() >= 0 else 0.0
        angle = math.radians(hue * 360.0)
        amount = float(self._data["amount"]) * radius
        return QPointF(center.x() + math.cos(angle) * amount, center.y() - math.sin(angle) * amount)

    def _normalize_neutral_state(self):
        if float(self._data.get("amount", 0.0)) <= 0.0001:
            self._data["amount"] = 0.0
            self._data["color"] = NEUTRAL_WHEEL_COLOR

    def _update_from_position(self, pos):
        center, _ = self._center_and_radius()
        radius = self._inner_radius()
        dx = pos.x() - center.x()
        dy = center.y() - pos.y()
        angle = math.atan2(dy, dx)
        if angle < 0:
            angle += math.tau
        distance = min(radius, math.hypot(dx, dy))
        hue = angle / math.tau
        color = QColor.fromHsvF(hue, 1.0, 1.0)
        self._data["color"] = color.name()
        self._data["amount"] = 0.0 if radius <= 0 else (distance / radius)
        self._normalize_neutral_state()
        self.update()
        self.changed.emit()

    def mousePressEvent(self, event):
        self._dragging = True
        self.dragStarted.emit()
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        self._update_from_position(pos)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        self._update_from_position(pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.dragFinished.emit()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._data["amount"] = 0.0
        self._data["color"] = NEUTRAL_WHEEL_COLOR
        self.update()
        self.changed.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        center, radius = self._center_and_radius()
        color = display_wheel_color(self._data)

        ring_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0)
        ring_width = max(6.0, radius * 0.16)
        hue_ring = QConicalGradient(center, 0.0)
        for stop, hue in (
            (0.00, 0), (1.0 / 6.0, 60), (2.0 / 6.0, 120),
            (3.0 / 6.0, 180), (4.0 / 6.0, 240), (5.0 / 6.0, 300),
            (1.00, 360),
        ):
            hue_ring.setColorAt(stop, QColor.fromHsv(hue % 360, 255, 255))
        ring_path = QPainterPath()
        ring_path.addEllipse(ring_rect)
        inner_path = QPainterPath()
        inner_radius = radius - ring_width
        inner_path.addEllipse(QRectF(center.x() - inner_radius, center.y() - inner_radius, inner_radius * 2.0, inner_radius * 2.0))
        ring_path = ring_path.subtracted(inner_path)
        painter.setPen(Qt.NoPen)
        painter.fillPath(ring_path, QBrush(hue_ring))

        painter.setPen(QPen(self.palette().mid().color(), 1.0))
        painter.setBrush(QBrush(self.palette().base()))
        painter.drawEllipse(center, inner_radius - 1.0, inner_radius - 1.0)

        painter.setPen(QPen(self.palette().mid().color(), 1.0, Qt.DashLine))
        painter.drawLine(QPointF(center.x() - inner_radius, center.y()), QPointF(center.x() + inner_radius, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - inner_radius), QPointF(center.x(), center.y() + inner_radius))

        puck = self._puck_position()
        painter.setPen(QPen(Qt.white, 1.0))
        painter.setBrush(QBrush(puck_display_color(self._data)))
        painter.drawEllipse(puck, 5.0, 5.0)
        painter.end()


class CurvePreviewWidget(QWidget):
    curveChanged = pyqtSignal(dict)
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, curve_data=None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(QSize(240, 240))
        self._curve_data = normalize_curve_data(curve_data)
        self._drag_index = None
        self._padding = 18.0

    def curve_data(self):
        return normalize_curve_data(self._curve_data)

    def set_curve_data(self, curve_data):
        self._curve_data = normalize_curve_data(curve_data)
        self.update()
        self.curveChanged.emit(self.curve_data())

    def reset(self):
        self.set_curve_data(default_curve_data())

    def _graph_rect(self):
        return QRectF(
            self._padding,
            self._padding,
            max(10.0, self.width() - (self._padding * 2.0)),
            max(10.0, self.height() - (self._padding * 2.0)),
        )

    def _point_to_screen(self, point):
        rect = self._graph_rect()
        x = rect.left() + (point["x"] * rect.width())
        y = rect.bottom() - (point["y"] * rect.height())
        return QPointF(x, y)

    def _screen_to_point(self, pos):
        rect = self._graph_rect()
        x = max(0.0, min(1.0, (pos.x() - rect.left()) / rect.width()))
        y = max(0.0, min(1.0, (rect.bottom() - pos.y()) / rect.height()))
        return {"x": x, "y": y}

    def _find_point_index(self, pos, radius=10.0):
        for idx, point in enumerate(self._curve_data["points"]):
            if (self._point_to_screen(point) - pos).manhattanLength() <= radius:
                return idx
        return None

    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        hit_index = self._find_point_index(pos)
        if hit_index is not None:
            self._drag_index = hit_index
            self.dragStarted.emit()
            return

        new_point = self._screen_to_point(pos)
        points = list(self._curve_data["points"])
        points.append(new_point)
        self._curve_data = normalize_curve_data({"points": points})
        for idx, point in enumerate(self._curve_data["points"]):
            if abs(point["x"] - new_point["x"]) < 0.0001 and abs(point["y"] - new_point["y"]) < 0.0001:
                self._drag_index = idx
                break
        self.dragStarted.emit()
        self.update()
        self.curveChanged.emit(self.curve_data())

    def mouseMoveEvent(self, event):
        if self._drag_index is None:
            return
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        point = self._screen_to_point(pos)
        points = list(self._curve_data["points"])
        if self._drag_index in (0, len(points) - 1):
            point["x"] = 0.0 if self._drag_index == 0 else 1.0
        points[self._drag_index] = point
        self._curve_data = normalize_curve_data({"points": points})
        self.update()
        self.curveChanged.emit(self.curve_data())

    def mouseReleaseEvent(self, event):
        if self._drag_index is not None:
            self._drag_index = None
            self.dragFinished.emit()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        hit_index = self._find_point_index(pos)
        points = list(self._curve_data["points"])
        if hit_index is not None and hit_index not in (0, len(points) - 1):
            self.dragStarted.emit()
            points.pop(hit_index)
            self._curve_data = normalize_curve_data({"points": points})
            self.update()
            self.curveChanged.emit(self.curve_data())
            self.dragFinished.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self._graph_rect()
        painter.fillRect(self.rect(), self.palette().window())
        painter.fillRect(rect, self.palette().base())

        grid_pen = QPen(self.palette().mid().color(), 1)
        painter.setPen(grid_pen)
        for tick in range(5):
            x = rect.left() + (tick * rect.width() / 4.0)
            y = rect.top() + (tick * rect.height() / 4.0)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        painter.setPen(QPen(self.palette().text().color(), 1.5))
        path = QPainterPath()
        points = self._curve_data["points"]
        if points:
            path.moveTo(self._point_to_screen(points[0]))
            for point in points[1:]:
                path.lineTo(self._point_to_screen(point))
            painter.drawPath(path)

        point_brush = QBrush(self.palette().highlight())
        painter.setBrush(point_brush)
        for point in points:
            p = self._point_to_screen(point)
            painter.drawEllipse(p, 4.0, 4.0)

        painter.end()


class ColorGradeCurveDialog(QDialog):
    changeStarted = pyqtSignal()
    changeFinished = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, curve_data=None, channel="master", parent=None):
        super().__init__(parent)
        _ = get_app()._tr
        self.setWindowTitle(_("Edit Color Curve"))
        self.setModal(False)
        self._widget = CurvePreviewWidget(curve_data, self)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Double-click to remove points. Drag to reshape the curve."), self))
        layout.addWidget(self._widget)

        button_row = QHBoxLayout()
        self.toggle_button = QPushButton(_("Disable"), self)
        self.toggle_button.clicked.connect(self._toggle_enabled)
        button_row.addWidget(self.toggle_button)

        button_row.addStretch(1)

        reset_button = QPushButton(_("Reset"), self)
        reset_button.clicked.connect(self._reset)
        button_row.addWidget(reset_button)
        layout.addLayout(button_row)
        self.channel = channel
        self._widget.dragStarted.connect(self.changeStarted)
        self._widget.dragFinished.connect(self.changeFinished)

        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(get_app().window.actionUndo_trigger)
        redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        redo_shortcut.activated.connect(get_app().window.actionRedo_trigger)
        self._shortcuts = [undo_shortcut, redo_shortcut]
        self._update_enabled_state()

    def curve_data(self):
        return self._widget.curve_data()

    def curve_widget(self):
        return self._widget

    def _apply_curve_change(self, curve_data):
        self.changeStarted.emit()
        self._widget.set_curve_data(curve_data)
        self.changeFinished.emit()

    def _reset(self):
        reset_curve = default_curve_data()
        reset_curve["enabled"] = self.curve_data().get("enabled", True)
        self._apply_curve_change(reset_curve)

    def _toggle_enabled(self):
        updated = copy.deepcopy(self.curve_data())
        updated["enabled"] = not updated.get("enabled", True)
        self._apply_curve_change(updated)
        self._update_enabled_state()

    def _update_enabled_state(self):
        enabled = self.curve_data().get("enabled", True)
        _ = get_app()._tr
        self.toggle_button.setText(_("Disable") if enabled else _("Enable"))
        self._widget.setEnabled(enabled)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class WheelsPreviewWidget(QWidget):
    def __init__(self, wheels_data=None, parent=None):
        super().__init__(parent)
        self._wheels_data = normalize_wheels_data(wheels_data)
        self.setMinimumHeight(72)

    def set_wheels_data(self, wheels_data):
        self._wheels_data = normalize_wheels_data(wheels_data)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        names = ["global", "shadows", "midtones", "highlights"]
        labels = ["G", "S", "M", "H"]
        slot_width = self.width() / float(len(names))
        for idx, name in enumerate(names):
            wheel = self._wheels_data[name]
            center_x = (idx * slot_width) + (slot_width / 2.0)
            center = QPointF(center_x, 28.0)
            radius = 19.0
            painter.setPen(QPen(self.palette().mid().color(), 1))
            painter.setBrush(QBrush(self.palette().base()))
            painter.drawEllipse(center, radius, radius)
            tint = display_wheel_color(wheel)
            if is_neutral_wheel(wheel):
                tint = QColor(self.palette().base())
            else:
                tint.setAlpha(26)
            painter.setBrush(QBrush(tint))
            painter.drawEllipse(center, radius * 0.92, radius * 0.92)

            wheel_color = display_wheel_color(wheel)
            angle = math.radians((wheel_color.hueF() if wheel_color.hueF() >= 0 else 0.0) * 360.0)
            amount = float(wheel["amount"]) * radius * 0.85
            puck = QPointF(center.x() + math.cos(angle) * amount, center.y() - math.sin(angle) * amount)
            painter.setPen(QPen(Qt.white, 1.0))
            painter.setBrush(QBrush(puck_display_color(wheel)))
            painter.drawEllipse(puck, 5.0, 5.0)

            luma_rect = QRectF(center_x - 20.0, 55.0, 40.0, 3.0)
            painter.setPen(QPen(self.palette().mid().color(), 1.0))
            painter.drawLine(QPointF(luma_rect.left(), luma_rect.center().y()), QPointF(luma_rect.right(), luma_rect.center().y()))
            value = (float(wheel["luma"]) + 1.0) / 2.0
            marker_x = luma_rect.left() + (luma_rect.width() * value)
            painter.setPen(QPen(self.palette().highlight().color(), 2.0))
            painter.drawLine(QPointF(marker_x, luma_rect.top() - 2.0), QPointF(marker_x, luma_rect.bottom() + 2.0))

            painter.setPen(QPen(self.palette().text().color(), 1))
            painter.drawText(QRectF(center_x - 16.0, 61.0, 32.0, 16.0), Qt.AlignCenter, labels[idx])

        painter.end()


class WheelRow(QWidget):
    changed = pyqtSignal()
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, title, wheel_data, parent=None):
        super().__init__(parent)
        self.title = title
        self._data = copy.deepcopy(wheel_data)
        self._spin_change_active = False
        self._spin_change_timer = QTimer(self)
        self._spin_change_timer.setSingleShot(True)
        self._spin_change_timer.setInterval(500)
        self._spin_change_timer.timeout.connect(self._finish_spin_change_burst)

        layout = QGridLayout(self)
        title_label = QLabel(title, self)
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label, 0, 0)

        self.wheel_control = ColorWheelControl(self._data, self)
        self.wheel_control.changed.connect(self._on_wheel_control_changed)
        self.wheel_control.dragStarted.connect(self.dragStarted)
        self.wheel_control.dragFinished.connect(self.dragFinished)
        layout.addWidget(self.wheel_control, 0, 1, 3, 1)

        self.color_button = QPushButton(self)
        self.color_button.clicked.connect(self.pick_color)
        self.color_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.color_button.customContextMenuRequested.connect(self._show_color_button_menu)
        layout.addWidget(self.color_button, 0, 2)

        self.amount_slider, self.amount_spin = self._make_slider_pair()
        self.luma_slider, self.luma_spin = self._make_luma_pair()

        layout.addWidget(QLabel("Amount", self), 1, 0)
        layout.addWidget(self.amount_slider, 1, 2)
        layout.addWidget(self.amount_spin, 1, 3)
        layout.addWidget(QLabel("Luma", self), 2, 0)
        layout.addWidget(self.luma_slider, 2, 2)
        layout.addWidget(self.luma_spin, 2, 3)

        self.amount_slider.valueChanged.connect(lambda value: self._on_slider_changed("amount", value))
        self.luma_slider.valueChanged.connect(lambda value: self._on_slider_changed("luma", value))
        self.amount_spin.valueChanged.connect(lambda value: self._on_spin_changed("amount", value))
        self.luma_spin.valueChanged.connect(lambda value: self._on_spin_changed("luma", value))
        self.amount_slider.sliderPressed.connect(self.dragStarted)
        self.amount_slider.sliderReleased.connect(self.dragFinished)
        self.luma_slider.sliderPressed.connect(self.dragStarted)
        self.luma_slider.sliderReleased.connect(self.dragFinished)

        self._apply_data(self._data)

    def _make_slider_pair(self):
        slider = QSlider(Qt.Horizontal, self)
        slider.setRange(0, 100)
        spin = QDoubleSpinBox(self)
        spin.setObjectName("colorGradeSpinBox")
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setRange(0.0, 1.0)
        return slider, spin

    def _make_luma_pair(self):
        slider = QSlider(Qt.Horizontal, self)
        slider.setRange(-100, 100)
        spin = QDoubleSpinBox(self)
        spin.setObjectName("colorGradeSpinBox")
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setRange(-1.0, 1.0)
        return slider, spin

    def _apply_data(self, data):
        color = selected_wheel_color(data)
        if is_achromatic_color(color):
            self.color_button.setText(get_app()._tr("Neutral"))
            self.color_button.setStyleSheet("")
        else:
            self.color_button.setText(color.name())
            self.color_button.setStyleSheet("background-color: %s;" % color.name())
        self.wheel_control.blockSignals(True)
        self.wheel_control.set_wheel_data(data)
        self.wheel_control.blockSignals(False)

        amount = float(data["amount"])
        luma = float(data["luma"])
        for value, slider, spin in (
            (amount, self.amount_slider, self.amount_spin),
            (luma, self.luma_slider, self.luma_spin),
        ):
            slider.blockSignals(True)
            spin.blockSignals(True)
            slider.setValue(int(round(value * 100.0)))
            spin.setValue(value)
            slider.blockSignals(False)
            spin.blockSignals(False)

    def _on_slider_changed(self, key, value):
        self._data[key] = value / 100.0
        spin = self.amount_spin if key == "amount" else self.luma_spin
        spin.blockSignals(True)
        spin.setValue(self._data[key])
        spin.blockSignals(False)
        if key == "amount":
            self.wheel_control.blockSignals(True)
            self.wheel_control.set_wheel_data(self._data)
            self.wheel_control.blockSignals(False)
        self.changed.emit()

    def _on_spin_changed(self, key, value):
        self._start_spin_change_burst()
        self._data[key] = float(value)
        slider = self.amount_slider if key == "amount" else self.luma_slider
        slider.blockSignals(True)
        slider.setValue(int(round(value * 100.0)))
        slider.blockSignals(False)
        if key == "amount":
            self.wheel_control.blockSignals(True)
            self.wheel_control.set_wheel_data(self._data)
            self.wheel_control.blockSignals(False)
        self.changed.emit()
        self._spin_change_timer.start()

    def _on_wheel_control_changed(self):
        self._data.update(self.wheel_control.wheel_data())
        self._apply_data(self._data)
        self.changed.emit()

    def pick_color(self):
        current = QColor(self._data["color"])

        def callback(color):
            if is_achromatic_color(color):
                self._data["color"] = NEUTRAL_WHEEL_COLOR
                self._data["amount"] = 0.0
            else:
                self._data["color"] = color.name()
            self._apply_data(self._data)
            self.changed.emit()

        ColorPicker(current, parent=self, title=get_app()._tr("Select a Color"), callback=callback)

    def reset_to_neutral(self):
        self._data["color"] = NEUTRAL_WHEEL_COLOR
        self._data["amount"] = 0.0
        self._apply_data(self._data)
        self.changed.emit()

    def _show_color_button_menu(self, pos):
        menu = StyledContextMenu(parent=self)
        menu.setStyleSheet("")
        reset_action = QAction(get_app()._tr("Reset"), self)
        reset_action.triggered.connect(self.reset_to_neutral)
        menu.addAction(reset_action)
        menu.exec_(self.color_button.mapToGlobal(pos))

    def value(self):
        return copy.deepcopy(self._data)

    def _start_spin_change_burst(self):
        if self._spin_change_active:
            return
        self._spin_change_active = True
        self.dragStarted.emit()

    def _finish_spin_change_burst(self):
        if not self._spin_change_active:
            return
        self._spin_change_active = False
        self.dragFinished.emit()


class ColorGradeWheelsDialog(QDialog):
    def __init__(self, wheels_data=None, parent=None):
        super().__init__(parent)
        _ = get_app()._tr
        self.setWindowTitle(_("Edit Color Wheels"))
        self._data = normalize_wheels_data(wheels_data)

        layout = QVBoxLayout(self)
        self.preview = WheelsPreviewWidget(self._data, self)
        layout.addWidget(self.preview)

        self.rows = {}
        for name, title in (
            ("global", _("Global")),
            ("shadows", _("Shadows")),
            ("midtones", _("Midtones")),
            ("highlights", _("Highlights")),
        ):
            row = WheelRow(title, self._data[name], self)
            row.changed.connect(self._refresh_preview)
            self.rows[name] = row
            layout.addWidget(row)

        reset_button = QPushButton(_("Reset"), self)
        reset_button.clicked.connect(self._reset)
        layout.addWidget(reset_button)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_preview(self):
        self.preview.set_wheels_data(self.wheels_data())

    def _reset(self):
        reset_data = default_wheels_data()
        for name, row in self.rows.items():
            row._data = copy.deepcopy(reset_data[name])
            row._apply_data(row._data)
        self._refresh_preview()

    def wheels_data(self):
        payload = {}
        for name, row in self.rows.items():
            payload[name] = row.value()
        return normalize_wheels_data(payload)


class ColorGradeWheelsPanel(QWidget):
    wheelsChanged = pyqtSignal(dict)
    dragStarted = pyqtSignal()
    dragFinished = pyqtSignal()

    def __init__(self, wheels_data=None, parent=None):
        super().__init__(parent)
        _ = get_app()._tr
        self._data = normalize_wheels_data(wheels_data)

        layout = QVBoxLayout(self)

        self.rows = {}
        for name, title in (
            ("global", _("Global")),
            ("shadows", _("Shadows")),
            ("midtones", _("Midtones")),
            ("highlights", _("Highlights")),
        ):
            row = WheelRow(title, self._data[name], self)
            row.changed.connect(self._refresh_preview)
            row.dragStarted.connect(self.dragStarted)
            row.dragFinished.connect(self.dragFinished)
            self.rows[name] = row
            layout.addWidget(row)

        button_row = QHBoxLayout()
        self.toggle_button = QPushButton(_("Disable"), self)
        self.toggle_button.clicked.connect(self._toggle_enabled)
        button_row.addWidget(self.toggle_button)

        button_row.addStretch(1)

        reset_button = QPushButton(_("Reset"), self)
        reset_button.clicked.connect(self._reset)
        button_row.addWidget(reset_button)
        layout.addLayout(button_row)
        self._update_enabled_state()

    def set_wheels_data(self, wheels_data):
        self._data = normalize_wheels_data(wheels_data)
        for name, row in self.rows.items():
            row._data = copy.deepcopy(self._data[name])
            row._apply_data(row._data)
        self._update_enabled_state()

    def _refresh_preview(self):
        wheels = self.wheels_data()
        self.wheelsChanged.emit(wheels)

    def _reset(self):
        reset_data = default_wheels_data()
        reset_data["enabled"] = self.wheels_data().get("enabled", True)
        self.set_wheels_data(reset_data)
        self.wheelsChanged.emit(self.wheels_data())

    def _toggle_enabled(self):
        updated = self.wheels_data()
        updated["enabled"] = not updated.get("enabled", True)
        self.set_wheels_data(updated)
        self.wheelsChanged.emit(updated)
        self._update_enabled_state()

    def _update_enabled_state(self):
        enabled = self.wheels_data().get("enabled", True)
        _ = get_app()._tr
        self.toggle_button.setText(_("Disable") if enabled else _("Enable"))
        for row in self.rows.values():
            row.setEnabled(enabled)

    def wheels_data(self):
        payload = {"enabled": self._data.get("enabled", True)}
        for name, row in self.rows.items():
            payload[name] = row.value()
        return normalize_wheels_data(payload)
