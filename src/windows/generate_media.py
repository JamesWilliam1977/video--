"""
 @file
 @brief Simple Generate dialog for ComfyUI pipeline jobs.
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QTextEdit, QTabWidget, QWidget, QPushButton
)

from classes import info
from classes.thumbnail import GetThumbPath


class GenerateMediaDialog(QDialog):
    """Minimal generate dialog with a simple default-first layout."""

    PREVIEW_WIDTH = 180
    PREVIEW_HEIGHT = 128

    def __init__(self, source_file=None, templates=None, parent=None):
        super().__init__(parent)
        self.source_file = source_file
        self.templates = templates or []
        self.setObjectName("generateDialog")
        self.setWindowTitle("Generate")
        self.setMinimumWidth(620)
        self.setMinimumHeight(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        root.addLayout(self._build_top_block())

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("generateTabs")
        self.tabs.addTab(self._build_prompt_tab(), "Prompt")
        self.tabs.addTab(self._build_mask_tab(), "Mask")
        self.tabs.addTab(self._build_advanced_tab(), "Advanced")
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

    def get_payload(self):
        return {
            "name": self.name_edit.text().strip(),
            "template_id": self.template_combo.currentData() or self.template_combo.currentText(),
            "prompt": self.prompt_edit.toPlainText().strip(),
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

    def _build_mask_tab(self):
        tab = QWidget(self)
        tab.setObjectName("pageMask")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        label = QLabel("Mask tools will appear for templates that support drawing.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
        return tab

    def _build_advanced_tab(self):
        tab = QWidget(self)
        tab.setObjectName("pageAdvanced")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        label = QLabel("Advanced controls are template-driven and will appear here.")
        label.setWordWrap(True)
        layout.addWidget(label)
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
        self.accept()

    def _apply_dialog_theme(self):
        self.setStyleSheet("""
QDialog#generateDialog {
    background-color: #192332;
    color: #91C3FF;
}
QDialog#generateDialog QTabWidget#generateTabs QWidget#pagePrompt,
QDialog#generateDialog QTabWidget#generateTabs QWidget#pageMask,
QDialog#generateDialog QTabWidget#generateTabs QWidget#pageAdvanced {
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
