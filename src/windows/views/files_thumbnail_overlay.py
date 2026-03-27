"""
 @file
 @brief Dynamic media-type overlay painter for project file thumbnails.
"""

import os

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainter
from PyQt5.QtSvg import QSvgRenderer

from classes import info


_VIDEO_OVERLAY_ICON = "tool-media-play.svg"


def _overlay_icon_path(media_type):
    if str(media_type or "").strip().lower() != "video":
        return ""
    return os.path.join(info.PATH, "themes", "cosmic", "images", _VIDEO_OVERLAY_ICON)


def paint_media_overlay(painter, deco_rect, media_type):
    """Paint a centered translucent play glyph for video thumbnails."""
    if not deco_rect or not deco_rect.isValid():
        return

    icon_path = _overlay_icon_path(media_type)
    if not icon_path or not os.path.exists(icon_path):
        return

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setOpacity(0.7)

    glyph_size = max(16.0, min(deco_rect.width(), deco_rect.height()) * 0.36)
    glyph_rect = QRectF(
        deco_rect.center().x() - (glyph_size / 2.0),
        deco_rect.center().y() - (glyph_size / 2.0),
        glyph_size,
        glyph_size,
    )
    renderer = QSvgRenderer(icon_path)
    renderer.render(painter, glyph_rect)

    painter.restore()
