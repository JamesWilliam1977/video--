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
QState = QStateMachine = None
uic = None
QT_API: Optional[str] = None
QT_VERSION_STR: Optional[str] = None
BINDING_VERSION_STR: Optional[str] = None
_MODULES = []
_FAILED_IMPORT: Optional[Exception] = None
_SELECTING = False


def _patch_enums_for_qt6():
    """Backfill Qt5-style enum attributes on Qt6 scoped enums."""
    if QT_API not in ("pyqt6", "pyside6"):
        return
    QDir = getattr(QtCore, "QDir", None)
    if QDir:
        # Filters
        filt = getattr(QDir, "Filter", None) or getattr(QDir, "Filters", None)
        if filt:
            for name, val in vars(filt).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QDir, name):
                    try:
                        setattr(QDir, name, val)
                    except Exception:
                        pass

    QLibraryInfo = getattr(QtCore, "QLibraryInfo", None)
    if QLibraryInfo:
        # Backfill TranslationsPath constant and location() alias
        lib_path_enum = getattr(QLibraryInfo, "LibraryPath", None)
        if lib_path_enum and not hasattr(QLibraryInfo, "TranslationsPath"):
            try:
                setattr(QLibraryInfo, "TranslationsPath", lib_path_enum.TranslationsPath)
            except Exception:
                pass
        if hasattr(QLibraryInfo, "path") and not hasattr(QLibraryInfo, "location"):
            try:
                setattr(QLibraryInfo, "location", staticmethod(QLibraryInfo.path))
            except Exception:
                pass
        # Sort flags
        sort = getattr(QDir, "SortFlag", None) or getattr(QDir, "SortFlags", None)
        if sort:
            for name, val in vars(sort).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QDir, name):
                    try:
                        setattr(QDir, name, val)
                    except Exception:
                        pass


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
        try:
            import PyQt6.uic as uicMod
        except Exception:
            uicMod = None
        try:
            import PyQt6.QtStateMachine as QtStateMachineMod  # type: ignore
            q_state = getattr(QtStateMachineMod, "QState", None)
            q_state_machine = getattr(QtStateMachineMod, "QStateMachine", None)
        except Exception:
            QtStateMachineMod = None
            q_state = getattr(QtCoreMod, "QState", None)
            q_state_machine = getattr(QtCoreMod, "QStateMachine", None)

        if q_state is None or q_state_machine is None:
            raise ImportError("PyQt6 QtStateMachine module not available (QState/QStateMachine missing)")
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
            q_state,
            q_state_machine,
            uicMod,
            QtCoreMod.QT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
        )

    if name == "pyside6":
        import PySide6.QtCore as QtCoreMod
        import PySide6.QtGui as QtGuiMod
        import PySide6.QtWidgets as QtWidgetsMod
        QtUiToolsMod = None
        try:
            import PySide6.QtStateMachine as QtStateMachineMod  # type: ignore
            q_state = getattr(QtStateMachineMod, "QState", None)
            q_state_machine = getattr(QtStateMachineMod, "QStateMachine", None)
        except Exception:
            QtStateMachineMod = None
            q_state = getattr(QtCoreMod, "QState", None)
            q_state_machine = getattr(QtCoreMod, "QStateMachine", None)

        if q_state is None or q_state_machine is None:
            raise ImportError("PySide6 QtStateMachine module not available (QState/QStateMachine missing)")
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
            q_state,
            q_state_machine,
            QtUiToolsMod,
            QtCoreMod.__version__,  # PySide binds Qt version here
            QtCoreMod.__version__,
        )

    if name == "pyqt5":
        import PyQt5.QtCore as QtCoreMod
        import PyQt5.QtGui as QtGuiMod
        import PyQt5.QtWidgets as QtWidgetsMod
        import PyQt5.uic as uicMod
        q_state = getattr(QtCoreMod, "QState", None)
        q_state_machine = getattr(QtCoreMod, "QStateMachine", None)
        if q_state is None or q_state_machine is None:
            raise ImportError("PyQt5 missing QState/QStateMachine in QtCore")

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
            q_state,
            q_state_machine,
            uicMod,
            QtCoreMod.QT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
        )

    if name == "pyside2":
        import PySide2.QtCore as QtCoreMod
        import PySide2.QtGui as QtGuiMod
        import PySide2.QtWidgets as QtWidgetsMod
        QtUiToolsMod = None
        try:
            import PySide2.QtStateMachine as QtStateMachineMod  # type: ignore
            q_state = getattr(QtStateMachineMod, "QState", None)
            q_state_machine = getattr(QtStateMachineMod, "QStateMachine", None)
        except Exception:
            QtStateMachineMod = None
            q_state = getattr(QtCoreMod, "QState", None)
            q_state_machine = getattr(QtCoreMod, "QStateMachine", None)
        if q_state is None or q_state_machine is None:
            raise ImportError("PySide2 QtStateMachine module not available (QState/QStateMachine missing)")

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
            q_state,
            q_state_machine,
            QtUiToolsMod,
            QtCoreMod.__version__,
            QtCoreMod.__version__,
        )

    raise ImportError(f"Unknown binding '{name}'")


def _select_binding() -> str:
    """Select and load the first available binding."""
    global QtCore, QtGui, QtWidgets, QtSvg, QtWebEngineWidgets, QtWebChannel, QtWebKitWidgets
    global Signal, Slot, Property, QRegularExpression, QState, QStateMachine, uic, QT_API, QT_VERSION_STR, BINDING_VERSION_STR, _MODULES
    global _FAILED_IMPORT, _SELECTING

    if _FAILED_IMPORT:
        raise _FAILED_IMPORT
    if _SELECTING:
        # Prevent recursion if an import path triggers __getattr__ again
        raise ImportError("qt_api: binding selection already in progress")
    _SELECTING = True

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
                QState,
                QStateMachine,
                uic,
                QT_VERSION_STR,
                BINDING_VERSION_STR,
            ) = _import_binding(candidate)
            logger.info(
                "qt_api: selected %s (Qt %s, binding %s)",
                QT_API,
                QT_VERSION_STR,
                BINDING_VERSION_STR,
            )
            _MODULES = [
                m
                for m in (
                    QtCore,
                    QtGui,
                    QtWidgets,
                    QtSvg,
                    QtWebEngineWidgets,
                    QtWebChannel,
                    QtWebKitWidgets,
                )
                if m is not None
            ]
            _patch_enums_for_qt6()
            _FAILED_IMPORT = None
            _SELECTING = False
            return QT_API
        except Exception as ex:  # noqa: BLE001
            logger.warning("qt_api: failed to load %s: %s", candidate, ex)
            errors.append(f"{candidate}: {ex}")

    _SELECTING = False
    _FAILED_IMPORT = ImportError(
        "No suitable Qt binding found. Tried: "
        + ", ".join(errors)
        + ". Set OPENSHOT_QT_API to force a specific binding."
    )
    raise _FAILED_IMPORT


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
    return QT_API


def __getattr__(name):
    """Lazy attribute forwarding so `from qt_api import QIcon` works."""
    if QT_API is None:
        _select_binding()
    # Expose common QtCore symbols directly
    if name in ("pyqtSignal", "Signal"):
        return Signal
    if name in ("pyqtSlot", "Slot"):
        return Slot
    if name in ("pyqtProperty", "Property"):
        return Property
    if name in ("QByteArray", "QLibraryInfo", "QDir"):
        return getattr(QtCore, name)
    if name in ("QState", "QStateMachine"):
        global QState, QStateMachine
        if QState is None or QStateMachine is None:
            try:
                if QT_API == "pyqt6":
                    import PyQt6.QtStateMachine as QtStateMachine  # type: ignore
                elif QT_API == "pyside6":
                    import PySide6.QtStateMachine as QtStateMachine  # type: ignore
                elif QT_API == "pyqt5":
                    QtStateMachine = QtCore
                else:
                    import PySide2.QtStateMachine as QtStateMachine  # type: ignore
                QState = getattr(QtStateMachine, "QState", None)
                QStateMachine = getattr(QtStateMachine, "QStateMachine", None)
            except Exception:
                pass
        return QState if name == "QState" else QStateMachine
    for module in _MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(name)


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
    "QState",
    "QStateMachine",
    # Commonly used Qt types
    "QSignalTransition",
    "QState",
    "QStateMachine",
    "QByteArray",
    "QDir",
    "QLibraryInfo",
    "QT_API",
    "QT_VERSION_STR",
    "BINDING_VERSION_STR",
    "ensure_binding",
    "load_ui",
]
