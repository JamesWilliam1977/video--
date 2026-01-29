"""
 @file
 @brief Auto-assign tab order based on on-screen widget geometry.
"""

from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtWidgets import QWidget, QLayout


def _is_focusable(widget, root, include_hidden):
    if widget is root:
        return False
    if widget.focusPolicy() == Qt.NoFocus:
        return False
    if not include_hidden and not widget.isVisibleTo(root):
        return False
    if not widget.isEnabled():
        return False
    return True


def _position_key(widget, root, fallback_index, row_tolerance):
    try:
        pos = widget.mapTo(root, QPoint(0, 0))
        x, y = pos.x(), pos.y()
    except Exception:
        x = y = 0

    if widget.size().isEmpty():
        parent = widget.parentWidget()
        if parent is not None:
            try:
                parent_pos = parent.mapTo(root, QPoint(0, 0))
                x, y = parent_pos.x(), parent_pos.y()
            except Exception:
                x = y = 0

    if row_tolerance and row_tolerance > 0:
        row = int((y + (row_tolerance / 2)) // row_tolerance)
    else:
        row = y

    return (row, x, y, fallback_index)


def apply_auto_tab_order(root, include_hidden=False, row_tolerance=8):
    """Apply top-to-bottom, left-to-right tab order on a widget tree."""
    if root is None:
        return

    widgets = []
    for index, widget in enumerate(root.findChildren(QWidget)):
        if _is_focusable(widget, root, include_hidden):
            widgets.append((widget, index))

    widgets.sort(key=lambda item: _position_key(item[0], root, item[1], row_tolerance))

    ordered_widgets = [item[0] for item in widgets]
    for first, second in zip(ordered_widgets, ordered_widgets[1:]):
        QWidget.setTabOrder(first, second)


def apply_auto_tab_order_later(root, include_hidden=False, row_tolerance=8):
    """Defer tab order assignment until after the event loop runs."""
    QTimer.singleShot(
        0,
        lambda: apply_auto_tab_order(
            root, include_hidden=include_hidden, row_tolerance=row_tolerance
        ),
    )


def _collect_focusable_from_layout(layout, root, include_hidden):
    if layout is None:
        return []
    widgets = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        child_layout = item.layout()
        if child_layout is not None:
            widgets.extend(_collect_focusable_from_layout(child_layout, root, include_hidden))
            continue
        widget = item.widget()
        if widget is not None and _is_focusable(widget, root, include_hidden):
            widgets.append(widget)
    return widgets


def apply_explicit_tab_order(widgets, root=None, include_hidden=False):
    """Apply tab order using an explicit widget list."""
    ordered = []
    seen = set()
    for widget in widgets:
        if widget is None or widget in seen:
            continue
        target_root = root or widget.window()
        if _is_focusable(widget, target_root, include_hidden):
            ordered.append(widget)
            seen.add(widget)
    for first, second in zip(ordered, ordered[1:]):
        QWidget.setTabOrder(first, second)


def apply_explicit_tab_order_later(widgets, root=None, include_hidden=False):
    """Defer explicit tab order assignment until after the event loop runs."""
    QTimer.singleShot(
        0,
        lambda: apply_explicit_tab_order(
            widgets, root=root, include_hidden=include_hidden
        ),
    )


def collect_focusable_from_layout(layout, root, include_hidden=False):
    """Collect focusable widgets from a layout in layout order."""
    if not isinstance(layout, QLayout):
        return []
    return _collect_focusable_from_layout(layout, root, include_hidden)
