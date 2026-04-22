"""
 @file
 @brief This file contains a theme's colors and UI dimensions
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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

from ..base import BaseTheme


class HumanityDarkTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
QToolTip {
    color: #ffffff;
    background-color: #2a82da;
    border: 0px solid white;
}

QComboBox::item {
    height: 24px;
}

QComboBox {
    combobox-popup: 0;
}

.property_value {
    foreground-color: #217dd4;
    background-color: #565656;
}

.zoom_slider_playhead {
    background-color: #ff0024;
}

QWidget#videoPreview {
    background-color: #191919;
}

QLabel#lblMissingFileHint,
QLabel#lblMissingFilePath {
    color: #b8b8b8;
}
        """

    def apply_theme(self):
        super().apply_theme()

        from classes import ui_util
        from classes.logger import log
        from qt_api import QStyleFactory

        log.info("Setting Fusion dark palette")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = ui_util.make_dark_palette(self.app.palette())
        self.app.setPalette(dark_palette)
        self.app.setStyleSheet(self.compose_stylesheet())

        from .styles import HumanityDarkTimelineTheme
        self.app.window.timeline.apply_theme(HumanityDarkTimelineTheme())

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

class Retro(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
QComboBox::item {
    height: 24px;
}

QMainWindow::separator:hover {
    background: #dedede;
}

.property_value {
    foreground-color: #217dd4;
    background-color: #7f7f7f;
}

.zoom_slider_playhead {
    background-color: #ff0024;
}

QWidget#videoPreview {
    background-color: #dedede;
}

QLabel#lblMissingFileHint,
QLabel#lblMissingFilePath {
    color: #5a5a5a;
}

QComboBox {
    combobox-popup: 0;
}
        """

    def apply_theme(self):
        super().apply_theme()

        from .styles import RetroTimelineTheme
        self.app.window.timeline.apply_theme(RetroTimelineTheme())

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)
