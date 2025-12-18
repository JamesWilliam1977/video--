"""
Centralized Qt binding loader for OpenShot.

Selects an available binding (PyQt6/PySide6/PyQt5/PySide2) using the
`OPENSHOT_QT_API` env var (`auto` default, otherwise one of
`pyqt6|pyside6|pyqt5|pyside2`). Logs the selection attempts, failures,
and final choice to help diagnose environment issues.
"""

import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# Public exports filled in after binding selection
QtCore = QtGui = QtWidgets = QtSvg = QtWebEngineWidgets = QtWebChannel = QtWebKitWidgets = None
Signal = Slot = Property = None
QRegularExpression = None
QT_API: Optional[str] = None
QT_VERSION_STR: Optional[str] = None
BINDING_VERSION_STR: Optional[str] = None


def _binding_order(env_value: str) -> List[str]:
    """Compute binding preference order based on env."""
    value = (env_value or "auto").strip().lower()
    if value in ("pyqt6", "pyside6", "pyqt5", "pyside2"):
        return [value]
    return ["pyqt6", "pyside6", "pyqt5", "pyside2"]


def _import_binding(name: str) -> Tuple:
    """Import a specific binding and return modules and helpers."""
    if name == "pyqt6":
        import PyQt6.QtCore as QtCoreMod
        import PyQt6.QtGui as QtGuiMod
        import PyQt6.QtWidgets as QtWidgetsMod

        QtSvgMod = None
        QtWebEngineWidgetsMod = None
        QtWebChannelMod = None
        QtWebKitWidgetsMod = None
        try:
            import PyQt6.QtSvg as QtSvgMod  # type: ignore
        except Exception:
            pass
        try:
            import PyQt6.QtWebEngineWidgets as QtWebEngineWidgetsMod  # type: ignore
            import PyQt6.QtWebChannel as QtWebChannelMod  # type: ignore
        except Exception:
            pass
        return (
            "pyqt6",
            QtCoreMod,
            QtGuiMod,
            QtWidgetsMod,
            QtSvgMod,
            QtWebEngineWidgetsMod,
            QtWebChannelMod,
            QtWebKitWidgetsMod,
            QtCoreMod.pyqtSignal,
            QtCoreMod.pyqtSlot,
            QtCoreMod.pyqtProperty,
            QtCoreMod.QRegularExpression,
            QtCoreMod.QT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
        )

    if name == "pyside6":
        import PySide6.QtCore as QtCoreMod
        import PySide6.QtGui as QtGuiMod
        import PySide6.QtWidgets as QtWidgetsMod

        QtSvgMod = None
        QtWebEngineWidgetsMod = None
        QtWebChannelMod = None
        QtWebKitWidgetsMod = None
        try:
            import PySide6.QtSvg as QtSvgMod  # type: ignore
        except Exception:
            pass
        try:
            import PySide6.QtWebEngineWidgets as QtWebEngineWidgetsMod  # type: ignore
            import PySide6.QtWebChannel as QtWebChannelMod  # type: ignore
        except Exception:
            pass
        return (
            "pyside6",
            QtCoreMod,
            QtGuiMod,
            QtWidgetsMod,
            QtSvgMod,
            QtWebEngineWidgetsMod,
            QtWebChannelMod,
            QtWebKitWidgetsMod,
            QtCoreMod.Signal,
            QtCoreMod.Slot,
            QtCoreMod.Property,
            QtCoreMod.QRegularExpression,
            QtCoreMod.__version__,  # PySide binds Qt version here
            QtCoreMod.__version__,
        )

    if name == "pyqt5":
        import PyQt5.QtCore as QtCoreMod
        import PyQt5.QtGui as QtGuiMod
        import PyQt5.QtWidgets as QtWidgetsMod

        QtSvgMod = None
        QtWebEngineWidgetsMod = None
        QtWebChannelMod = None
        QtWebKitWidgetsMod = None
        try:
            import PyQt5.QtSvg as QtSvgMod  # type: ignore
        except Exception:
            pass
        try:
            import PyQt5.QtWebEngineWidgets as QtWebEngineWidgetsMod  # type: ignore
            import PyQt5.QtWebChannel as QtWebChannelMod  # type: ignore
        except Exception:
            pass
        try:
            import PyQt5.QtWebKitWidgets as QtWebKitWidgetsMod  # type: ignore
        except Exception:
            pass
        return (
            "pyqt5",
            QtCoreMod,
            QtGuiMod,
            QtWidgetsMod,
            QtSvgMod,
            QtWebEngineWidgetsMod,
            QtWebChannelMod,
            QtWebKitWidgetsMod,
            QtCoreMod.pyqtSignal,
            QtCoreMod.pyqtSlot,
            QtCoreMod.pyqtProperty,
            QtCoreMod.QRegularExpression,
            QtCoreMod.QT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
        )

    if name == "pyside2":
        import PySide2.QtCore as QtCoreMod
        import PySide2.QtGui as QtGuiMod
        import PySide2.QtWidgets as QtWidgetsMod

        QtSvgMod = None
        QtWebEngineWidgetsMod = None
        QtWebChannelMod = None
        QtWebKitWidgetsMod = None
        try:
            import PySide2.QtSvg as QtSvgMod  # type: ignore
        except Exception:
            pass
        try:
            import PySide2.QtWebEngineWidgets as QtWebEngineWidgetsMod  # type: ignore
            import PySide2.QtWebChannel as QtWebChannelMod  # type: ignore
        except Exception:
            pass
        try:
            import PySide2.QtWebKitWidgets as QtWebKitWidgetsMod  # type: ignore
        except Exception:
            pass
        return (
            "pyside2",
            QtCoreMod,
            QtGuiMod,
            QtWidgetsMod,
            QtSvgMod,
            QtWebEngineWidgetsMod,
            QtWebChannelMod,
            QtWebKitWidgetsMod,
            QtCoreMod.Signal,
            QtCoreMod.Slot,
            QtCoreMod.Property,
            QtCoreMod.QRegularExpression,
            QtCoreMod.__version__,
            QtCoreMod.__version__,
        )

    raise ImportError(f"Unknown binding '{name}'")


def _select_binding() -> str:
    """Select and load the first available binding."""
    global QtCore, QtGui, QtWidgets, QtSvg, QtWebEngineWidgets, QtWebChannel, QtWebKitWidgets
    global Signal, Slot, Property, QRegularExpression, QT_API, QT_VERSION_STR, BINDING_VERSION_STR

    requested = os.environ.get("OPENSHOT_QT_API", "auto")
    attempts = _binding_order(requested)
    errors = []
    logger.info("qt_api: requested=%s, attempts=%s", requested, attempts)

    for candidate in attempts:
        try:
            (
                QT_API,
                QtCore,
                QtGui,
                QtWidgets,
                QtSvg,
                QtWebEngineWidgets,
                QtWebChannel,
                QtWebKitWidgets,
                Signal,
                Slot,
                Property,
                QRegularExpression,
                QT_VERSION_STR,
                BINDING_VERSION_STR,
            ) = _import_binding(candidate)
            logger.info(
                "qt_api: selected %s (Qt %s, binding %s)",
                QT_API,
                QT_VERSION_STR,
                BINDING_VERSION_STR,
            )
            return QT_API
        except Exception as ex:  # noqa: BLE001
            logger.warning("qt_api: failed to load %s: %s", candidate, ex)
            errors.append(f"{candidate}: {ex}")

    raise ImportError(
        "No suitable Qt binding found. Tried: "
        + ", ".join(errors)
        + ". Set OPENSHOT_QT_API to force a specific binding."
    )


def load_ui(path: str, baseinstance=None):
    """Load a Qt Designer .ui file using the active binding."""
    if QT_API is None:
        _select_binding()

    if QT_API in ("pyqt6", "pyqt5"):
        from importlib import import_module

        uic = import_module(f"{'PyQt6' if QT_API == 'pyqt6' else 'PyQt5'}.uic")
        return uic.loadUi(path, baseinstance)

    # PySide
    from importlib import import_module

    QtUiTools = import_module("PySide6.QtUiTools" if QT_API == "pyside6" else "PySide2.QtUiTools")  # type: ignore
    loader = QtUiTools.QUiLoader()
    ui_file = QtCore.QFile(path)
    if not ui_file.open(QtCore.QFile.ReadOnly):
        raise IOError(f"Cannot open UI file: {path}")
    try:
        return loader.load(ui_file, baseinstance)
    finally:
        ui_file.close()


def ensure_binding():
    """Force binding selection (useful for early importers)."""
    if QT_API is None:
        _select_binding()


# Select binding immediately on import for visibility
ensure_binding()

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtSvg",
    "QtWebEngineWidgets",
    "QtWebChannel",
    "QtWebKitWidgets",
    "Signal",
    "Slot",
    "Property",
    "QRegularExpression",
    "QT_API",
    "QT_VERSION_STR",
    "BINDING_VERSION_STR",
    "ensure_binding",
    "load_ui",
]
