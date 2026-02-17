"""
 @file
 @brief This file contains the Generate media dialog.
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

import os
import json

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QTextEdit, QTabWidget, QWidget, QPushButton, QMessageBox
)

from classes import info
from classes.logger import log
from classes.thumbnail import GetThumbPath
from windows.region import SelectRegion


class GenerateMediaDialog(QDialog):
    """Minimal generate dialog with a simple default-first layout."""

    PREVIEW_WIDTH = 180
    PREVIEW_HEIGHT = 128

    def __init__(
        self,
        source_file=None,
        templates=None,
        preselected_template_id=None,
        dialog_title=None,
        parent=None,
    ):
        super().__init__(parent)
        self.source_file = source_file
        self.templates = templates or []
        self.preselected_template_id = str(preselected_template_id or "").strip()
        self._coordinates_positive_text = ""
        self._coordinates_negative_text = ""
        self.setObjectName("generateDialog")
        self.setWindowTitle(str(dialog_title or "AI Tools"))
        self.setMinimumWidth(620)
        self.setMinimumHeight(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        root.addLayout(self._build_top_block())

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("generateTabs")
        self.page_prompt = self._build_prompt_tab()
        self.page_points = self._build_points_tab()
        self.prompt_tab_index = self.tabs.addTab(self.page_prompt, "Prompt")
        self.points_tab_index = self.tabs.addTab(self.page_points, "Points")
        root.addWidget(self.tabs, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.generate_button = QPushButton("Generate")
        self.generate_button.setIcon(QIcon(":/icons/Humanity/actions/16/star.svg"))
        self.cancel_button.clicked.connect(self.reject)
        self.generate_button.clicked.connect(self._on_generate_clicked)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.generate_button)
        root.addLayout(button_row)
        self._apply_dialog_theme()

    def _current_coordinates_text(self):
        coordinates_positive = str(self._coordinates_positive_text or "").strip()
        coordinates_negative = str(self._coordinates_negative_text or "").strip()
        if not coordinates_positive and hasattr(self, "points_preview"):
            preview_text = self.points_preview.toPlainText().strip()
            if preview_text.startswith("{"):
                try:
                    payload = json.loads(preview_text.replace("'", "\""))
                    coordinates_positive = str(payload.get("positive", "")).strip() or coordinates_positive
                    coordinates_negative = str(payload.get("negative", "")).strip() or coordinates_negative
                except Exception:
                    pass
        prompt_text = self.prompt_edit.toPlainText().strip()
        # Backward-compatible fallback: if prompt itself contains point JSON, treat it as coordinates.
        if (not coordinates_positive) and prompt_text.startswith("[") and ("\"x\"" in prompt_text or "'x'" in prompt_text):
            coordinates_positive = prompt_text
        return coordinates_positive, coordinates_negative, prompt_text

    def get_payload(self):
        coordinates_positive, coordinates_negative, prompt_text = self._current_coordinates_text()
        return {
            "name": self.name_edit.text().strip(),
            "template_id": self.template_combo.currentData() or self.template_combo.currentText(),
            "prompt": prompt_text,
            "coordinates_positive": coordinates_positive,
            "coordinates_negative": coordinates_negative,
        }

    def _build_top_block(self):
        block = QHBoxLayout()
        block.setSpacing(12)

        if self.source_file:
            self.thumbnail_label = QLabel()
            self.thumbnail_label.setFixedSize(self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT)
            self.thumbnail_label.setAlignment(Qt.AlignCenter)
            self.thumbnail_label.setStyleSheet("border: 1px solid palette(mid);")
            self._load_thumbnail()
            block.addWidget(self.thumbnail_label, 0)

        setup_form = QFormLayout()
        setup_form.setContentsMargins(0, 0, 0, 0)
        setup_form.setVerticalSpacing(8)

        default_name = "generation"
        if self.source_file:
            path = self.source_file.data.get("path", "")
            if path:
                default_name = "{}_gen".format(os.path.splitext(os.path.basename(path))[0])

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Output file name")
        self.name_edit.setText(default_name)
        setup_form.addRow("Name", self.name_edit)

        self.template_combo = QComboBox()
        if self.templates:
            for template in self.templates:
                self.template_combo.addItem(template.get("name", ""), template.get("id", ""))
        else:
            self.template_combo.addItem("Basic Text to Image", "txt2img-basic")
        if self.preselected_template_id:
            index = self.template_combo.findData(self.preselected_template_id)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        setup_form.addRow("Template", self.template_combo)

        if self.source_file:
            source_path = self.source_file.data.get("path", "")
            source_label = QLabel(os.path.basename(source_path))
            source_label.setToolTip(source_path)
            setup_form.addRow("Source", source_label)

        right_container = QWidget(self)
        right_container.setLayout(setup_form)
        block.addWidget(right_container, 1)
        return block

    def _build_prompt_tab(self):
        tab = QWidget(self)
        tab.setObjectName("pagePrompt")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Describe what to generate...")
        self.prompt_edit.setMinimumHeight(140)
        layout.addWidget(self.prompt_edit)
        return tab

    def _build_points_tab(self):
        tab = QWidget(self)
        tab.setObjectName("pagePoints")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        self.mask_hint = QLabel(
            "Select one or more tracking points on the source frame."
        )
        self.mask_hint.setWordWrap(True)
        layout.addWidget(self.mask_hint)

        controls = QHBoxLayout()
        self.pick_points_button = QPushButton("Pick Point(s) on Source")
        self.clear_points_button = QPushButton("Clear")
        self.pick_points_button.clicked.connect(self._pick_points_clicked)
        self.clear_points_button.clicked.connect(self._clear_points_clicked)
        controls.addWidget(self.pick_points_button)
        controls.addWidget(self.clear_points_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.points_preview = QTextEdit()
        self.points_preview.setReadOnly(True)
        self.points_preview.setMinimumHeight(90)
        layout.addWidget(self.points_preview)
        layout.addStretch(1)
        return tab

    def _load_thumbnail(self):
        path = ""
        media_type = self.source_file.data.get("media_type")
        if media_type in ["video", "image"]:
            path = GetThumbPath(self.source_file.id, 1)
        elif media_type == "audio":
            path = os.path.join(info.PATH, "images", "AudioThumbnail.svg")

        pix = QPixmap(path) if path else QPixmap()
        if not pix.isNull():
            pix = pix.scaled(
                self.PREVIEW_WIDTH - 2,
                self.PREVIEW_HEIGHT - 2,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.thumbnail_label.setPixmap(pix)
        else:
            self.thumbnail_label.setText("No Preview")

    def _on_generate_clicked(self):
        if not self.name_edit.text().strip():
            self.name_edit.setFocus(Qt.TabFocusReason)
            return
        if self._is_sam2_point_template():
            coordinates_positive, _coordinates_negative, _prompt_text = self._current_coordinates_text()
            if not coordinates_positive:
                QMessageBox.warning(
                    self,
                    "Missing Points",
                    "No SAM2 points were provided. Use the Points tab and click Pick Point(s) on Source.",
                )
                self.tabs.setCurrentWidget(self.page_points)
                return
        self.accept()

    def _is_sam2_point_template(self):
        template_id = str(self.template_combo.currentData() or "").strip().lower()
        return "sam2" in template_id and "blur-anything" in template_id

    def _on_template_changed(self, index):
        _ = index
        is_point_template = self._is_sam2_point_template()
        self._set_tab_visible(self.prompt_tab_index, not is_point_template)
        self._set_tab_visible(self.points_tab_index, is_point_template)
        self.pick_points_button.setEnabled(bool(self.source_file) and is_point_template)
        self.clear_points_button.setEnabled(is_point_template)
        if is_point_template:
            self.mask_hint.setText(
                "Select one or more tracking points on the source frame."
            )
            self.tabs.setCurrentWidget(self.page_points)
        else:
            self.mask_hint.setText(
                "Point selection is available for SAM2 Blur Anything templates."
            )
            self.tabs.setCurrentWidget(self.page_prompt)

    def _pick_points_clicked(self):
        if not self.source_file:
            return

        win = SelectRegion(file=self.source_file, clip=None, selection_mode="point")
        if win.exec_() != QDialog.Accepted:
            return

        raw_points_pos = win.selected_points()
        raw_points_neg = win.selected_points_negative()
        log.info(
            "Generate dialog captured raw SAM2 points positive=%s negative=%s",
            len(raw_points_pos or []),
            len(raw_points_neg or []),
        )
        points_pos = []
        points_neg = []
        frame_size = win.videoPreview.curr_frame_size
        if not frame_size:
            frame_w = float(max(win.viewport_rect.width(), 1))
            frame_h = float(max(win.viewport_rect.height(), 1))
        else:
            frame_w = float(max(frame_size.width(), 1))
            frame_h = float(max(frame_size.height(), 1))
        for point in raw_points_pos:
            x_norm = max(min(float(point["x"]), float(max(frame_w - 1.0, 0.0))), 0.0)
            y_norm = max(min(float(point["y"]), float(max(frame_h - 1.0, 0.0))), 0.0)
            x_abs = int(round((x_norm / frame_w) * float(win.width)))
            y_abs = int(round((y_norm / frame_h) * float(win.height)))
            points_pos.append({"x": x_abs, "y": y_abs})
        for point in raw_points_neg:
            x_norm = max(min(float(point["x"]), float(max(frame_w - 1.0, 0.0))), 0.0)
            y_norm = max(min(float(point["y"]), float(max(frame_h - 1.0, 0.0))), 0.0)
            x_abs = int(round((x_norm / frame_w) * float(win.width)))
            y_abs = int(round((y_norm / frame_h) * float(win.height)))
            points_neg.append({"x": x_abs, "y": y_abs})

        if not points_pos:
            QMessageBox.warning(
                self,
                "No Points Found",
                "No positive points were captured. Use Shift+Click to add positive points.",
            )
            return

        points_pos_text = json.dumps(points_pos)
        points_neg_text = json.dumps(points_neg) if points_neg else ""
        log.info(
            "Generate dialog normalized SAM2 points positive=%s negative=%s",
            len(points_pos),
            len(points_neg),
        )
        self._coordinates_positive_text = points_pos_text
        self._coordinates_negative_text = points_neg_text
        self.points_preview.setPlainText(
            json.dumps({"positive": points_pos_text, "negative": points_neg_text}, indent=2)
        )
        self.tabs.setCurrentWidget(self.page_points)

    def _clear_points_clicked(self):
        self._coordinates_positive_text = ""
        self._coordinates_negative_text = ""
        self.points_preview.clear()

    def _set_tab_visible(self, index, visible):
        bar = self.tabs.tabBar()
        if hasattr(bar, "setTabVisible"):
            bar.setTabVisible(index, bool(visible))
        else:
            self.tabs.setTabEnabled(index, bool(visible))

    def _apply_dialog_theme(self):
        self.setStyleSheet("""
QDialog#generateDialog {
    background-color: #192332;
    color: #91C3FF;
}
QDialog#generateDialog QTabWidget#generateTabs QWidget#pagePrompt,
QDialog#generateDialog QTabWidget#generateTabs QWidget#pagePoints {
    background-color: #141923;
    border: none;
}
QDialog#generateDialog QTabWidget#generateTabs QTabBar::tab {
    margin-left: 14px;
    margin-top: 10px;
    padding: 6px 2px;
    color: rgba(145, 195, 255, 0.5);
}
QDialog#generateDialog QTabWidget#generateTabs QTabBar::tab:selected {
    color: rgba(145, 195, 255, 1.0);
    border-bottom: 1.2px solid #53a0ed;
}
QDialog#generateDialog QLineEdit,
QDialog#generateDialog QTextEdit,
QDialog#generateDialog QComboBox {
    background-color: #141923;
    color: #91C3FF;
    border: 1px solid rgba(145, 195, 255, 0.20);
    border-radius: 4px;
    padding: 6px 8px;
}
QDialog#generateDialog QPushButton {
    background-color: #283241;
    color: #91C3FF;
    border: 1px solid rgba(145, 195, 255, 0.20);
    border-radius: 4px;
    padding: 6px 10px;
}
QDialog#generateDialog QPushButton:hover {
    background-color: #323C50;
}
QDialog#generateDialog QPushButton:focus,
QDialog#generateDialog QLineEdit:focus,
QDialog#generateDialog QTextEdit:focus,
QDialog#generateDialog QComboBox:focus {
    border: 1px solid #53a0ed;
}
""")
        self._on_template_changed(self.template_combo.currentIndex())
