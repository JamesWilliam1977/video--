"""Test package bootstrap for headless Qt environments."""

import os

from PyQt5.QtCore import QCoreApplication, Qt


# Package builders run without an X server, so force Qt to use a headless backend.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

# QtWebEngine requires this attribute before any Qt application is created.
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
