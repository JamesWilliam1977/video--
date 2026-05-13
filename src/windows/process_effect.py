"""
 @file
 @brief This file loads the Initialize Effects / Pre-process effects dialog
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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
import time
import json
import functools
import webbrowser
import hashlib
import subprocess
import sys
import zipfile

from qt_api import Qt, pyqtSignal, QCoreApplication, QTimer
from qt_api import QPainter
from qt_api import (
    QPushButton, QDialog, QLabel, QDoubleSpinBox, QSpinBox, QLineEdit,
    QCheckBox, QComboBox, QDialogButtonBox, QSizePolicy, QMessageBox,
    QFileDialog, QProgressDialog, QWidget, QHBoxLayout,
)
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes import http_client
from classes import ui_util
from classes.app import get_app
from classes.logger import log
from classes.metrics import *

YOLO5_DOWNLOAD_URL = "https://cdn.openshot.org/static/files/yolov5/yolov5s-openshot.zip"
YOLO5_DOWNLOAD_SHA256 = "cd401831d6a700cb827b4470ec0a505fb8802a85075fcd55c279cb4b73e02c69"
YOLO5_DIR = os.path.join(info.YOLO_PATH, "Yolo5")
YOLO5_MODEL_PATH = os.path.join(YOLO5_DIR, "yolov5s.onnx")
YOLO5_CLASSES_PATH = os.path.join(YOLO5_DIR, "obj.names")
YOLO5_MODEL_SHA256 = "ffcac948408e3731ba6b0059e125f3d759672830771b72d5081fb6244ff47e5d"
YOLO5_CLASSES_SHA256 = "bd17f1ee35d5f3c862a4894605855abbb9dda4b0621fdb0ac4c2c8c7bb7e730a"
YOLO5_MODEL_NAME = "YOLOv5"


class DownloadCancelled(Exception):
    """Raised when a user cancels an in-progress download."""


class RegionButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.qimage = None

    def setImage(self, qimage):
        self.qimage = qimage
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.qimage:
            painter = QPainter(self)
            resized_qimage = self.qimage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.drawImage(0, 0, resized_qimage)
        else:
            super().paintEvent(event)  # Draw the normal button


class ProcessEffect(QDialog):
    """ Choose Profile Dialog """
    progress = pyqtSignal(int)

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'process-effect.ui')

    def __init__(self, clip_id, effect_class, effect_params):

        if not openshot.Clip().COMPILED_WITH_CV:
            raise ModuleNotFoundError("Openshot not compiled with OpenCV")

        # Create dialog class
        super().__init__()
        # Track effect details
        self.clip_id = clip_id
        self.effect_name = ""
        self.effect_class = effect_class
        self.context = {}
        self.file_fields = {}
        self.onnx_validation_cache = {}
        self.file_validation_timer = QTimer(self)
        self.file_validation_timer.setInterval(300)
        self.file_validation_timer.setSingleShot(True)
        self.file_validation_timer.timeout.connect(self.update_file_validation)

        # Get all effect JSON data, and find effect's display name (based on the class name)
        raw_effects_list = json.loads(openshot.EffectInfo.Json())
        for raw_effect in raw_effects_list:
            if raw_effect.get("class_name") == self.effect_class:
                self.effect_name = raw_effect.get("name")
                break

        # Access C++ timeline and find the Clip instance which this effect should be applied to
        timeline_instance = get_app().window.timeline_sync.timeline
        for clip_instance in timeline_instance.Clips():
            if clip_instance.Id() == self.clip_id:
                self.clip_instance = clip_instance
                break

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # get translations
        _ = get_app()._tr

        # Update window title
        self.setWindowTitle(self.windowTitle() % _(self.effect_name))

        # Pause playback
        get_app().window.PauseSignal.emit()

        # Track metrics
        track_metric_screen("process-effect-screen")

        # Loop through options and create widgets
        form_layout = self.scrollAreaWidgetContents.layout()
        for param in effect_params:
            # Create Label
            widget = None
            label = QLabel()
            label.setText(_(param["title"]))
            label.setToolTip(_(param["title"]))

            if param["type"] == "link":
                # create a clickable link
                label.setText('<a href="%s">%s</a>' % (param["value"], _(param["title"])))
                label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                label.linkActivated.connect(functools.partial(self.link_activated, widget, param))

            if param["type"] == "download-yolo5":
                widget = QPushButton(_("Download"))
                widget.setToolTip(self.model_message(_("Download %(model)s model files.")))
                widget.clicked.connect(functools.partial(self.download_yolo5_clicked, widget, param))

            if param["type"] == "spinner":
                # create QDoubleSpinBox
                widget = QDoubleSpinBox()
                widget.setMinimum(float(param["min"]))
                widget.setMaximum(float(param["max"]))
                widget.setValue(float(param["value"]))
                widget.setSingleStep(1.0)
                widget.setToolTip(_(param["title"]))
                widget.valueChanged.connect(functools.partial(self.spinner_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = float(param["value"])

            if param["type"] == "rect":
                # create QPushButton which opens up a display of the clip, with ability to select Rectangle
                widget = RegionButton(_("Click to Select"))
                widget.setMinimumHeight(80)
                widget.setToolTip(_(param["title"]))
                widget.clicked.connect(functools.partial(self.rect_select_clicked, widget, param))

                # Set initial context
                self.context[param["setting"]] = {"button-clicked": False, "x": 0, "y": 0, "width": 0, "height": 0}

            if param["type"] == "spinner-int":
                # create QDoubleSpinBox
                widget = QSpinBox()
                widget.setMinimum(int(param["min"]))
                widget.setMaximum(int(param["max"]))
                widget.setValue(int(param["value"]))
                widget.setSingleStep(1)
                widget.setToolTip(_(param["title"]))
                widget.valueChanged.connect(functools.partial(self.spinner_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = int(param["value"])

            elif param["type"] == "text":
                # create QLineEdit
                widget = QLineEdit()
                widget.setText(_(param["value"]))
                widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = param["value"]

            elif param["type"] == "file":
                widget = QWidget()
                widget_layout = QHBoxLayout(widget)
                widget_layout.setContentsMargins(0, 0, 0, 0)
                widget_layout.setSpacing(6)

                path_widget = QLineEdit()
                path_widget.setText(param["value"])
                path_widget.setToolTip(_(param["title"]))
                path_widget.textChanged.connect(functools.partial(self.file_value_changed, path_widget, param))

                status_widget = QLabel()
                status_widget.setMinimumWidth(20)
                status_widget.setToolTip(_("File has not been validated yet."))

                browse_button = QPushButton(_("Browse"))
                browse_button.setToolTip(_("Choose a file from disk."))
                browse_button.clicked.connect(functools.partial(self.file_browse_clicked, path_widget, param))

                path_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                status_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
                browse_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

                widget_layout.addWidget(path_widget, 1, Qt.AlignVCenter)
                widget_layout.addWidget(status_widget, 0, Qt.AlignVCenter)
                widget_layout.addWidget(browse_button, 0, Qt.AlignVCenter)

                self.context[param["setting"]] = param["value"]
                self.file_fields[param["setting"]] = {
                    "param": param,
                    "path": path_widget,
                    "status": status_widget,
                }

            elif param["type"] == "bool":
                # create spinner
                widget = QCheckBox()
                if param["value"] == True:
                    widget.setCheckState(Qt.Checked)
                    self.context[param["setting"]] = True
                else:
                    widget.setCheckState(Qt.Unchecked)
                    self.context[param["setting"]] = False
                widget.stateChanged.connect(functools.partial(self.bool_value_changed, widget, param))

            elif param["type"] == "dropdown":

                # create spinner
                widget = QComboBox()

                # Get values
                value_list = param["values"]

                # Add normal values
                box_index = 0
                for value_item in value_list:
                    k = value_item["name"]
                    v = value_item["value"]
                    i = value_item.get("icon", None)

                    # add dropdown item
                    widget.addItem(_(k), v)

                    # select dropdown (if default)
                    if v == param["value"]:
                        widget.setCurrentIndex(box_index)

                        # Set initial context
                        self.context[param["setting"]] = param["value"]
                    box_index = box_index + 1

                widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))

            # Add Label and Widget to the form
            if widget and label:
                # Add minimum size
                label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

                form_layout.addRow(label, widget)

            elif not widget and label:
                label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                form_layout.addRow(label)

        # Add buttons
        self.cancel_button = QPushButton(_('Cancel'))
        self.process_button = QPushButton(_('Process Effect'))
        self.buttonBox.addButton(self.process_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.RejectRole)
        self.update_file_validation()

        # flag to close the clip processing thread
        self.cancel_clip_processing = False
        self.effect = None

    def link_activated(self, widget, param, value):
        """Link activated"""
        webbrowser.open(value, new=1)

    def model_message(self, message):
        """Format a translated message with the object detection model name."""
        return message % {"model": YOLO5_MODEL_NAME}

    def spinner_value_changed(self, widget, param, value):
        """Spinner value change callback"""
        self.context[param["setting"]] = value
        log.info(self.context)

    def bool_value_changed(self, widget, param, state):
        """Boolean value change callback"""
        if state == Qt.Checked:
            self.context[param["setting"]] = True
        else:
            self.context[param["setting"]] = False
        log.info(self.context)

    def dropdown_index_changed(self, widget, param, index):
        """Dropdown value change callback"""
        value = widget.itemData(index)
        self.context[param["setting"]] = value
        log.info(self.context)

    def text_value_changed(self, widget, param, value=None):
        """Textbox value change callback"""
        try:
            # Attempt to load value from QTextEdit (i.e. multi-line)
            if not value:
                value = widget.toPlainText()
        except:
            log.debug('Failed to get plain text from widget')

        self.context[param["setting"]] = value
        log.info(self.context)

    def file_value_changed(self, widget, param, value=None):
        """File path textbox change callback"""
        if value is None:
            value = widget.text()
        self.context[param["setting"]] = value
        self.file_validation_timer.start()
        log.info(self.context)

    def file_browse_clicked(self, widget, param):
        """Browse for a file path."""
        _ = get_app()._tr
        current_path = widget.text()
        start_dir = os.path.dirname(current_path) if current_path else info.USER_PATH
        selected_path = QFileDialog.getOpenFileName(
            self,
            _("Choose %s") % _(param["title"]),
            start_dir,
            _(param.get("file-filter", "All files (*)")),
        )[0]
        if selected_path:
            widget.setText(selected_path)

    def validate_onnx_model_load(self, path):
        """Return whether OpenCV can load this ONNX model."""
        _ = get_app()._tr
        try:
            stat = os.stat(path)
        except OSError:
            return False, _("File not found")

        cache_key = (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
        cached = self.onnx_validation_cache.get(cache_key)
        if cached:
            return cached

        validator_code = """
import sys

try:
    import cv2
except ImportError:
    sys.exit(2)

try:
    cv2.dnn.readNetFromONNX(sys.argv[1])
except Exception as ex:
    sys.stderr.write(str(ex))
    sys.exit(1)
"""
        try:
            validation = subprocess.run(
                [sys.executable, "-c", validator_code, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            result = (False, _("Unable to load model file."))
            self.onnx_validation_cache[cache_key] = result
            log.error("ONNX model validation timed out: %s", path)
            return result

        if validation.returncode == 2:
            result = (True, _("Ready"))
        elif validation.returncode != 0:
            error_text = (validation.stderr or "").strip()
            if validation.returncode < 0:
                log.error("ONNX model validation crashed with signal %s", -validation.returncode)
            elif error_text:
                log.error("ONNX model validation failed: %s", error_text)
            else:
                log.error("ONNX model validation failed with code %s", validation.returncode)

            if "Unsupported data type: FLOAT16" in error_text:
                result = (
                    False,
                    self.model_message(_("%(model)s requires an FP32 model file for this OpenCV build.")),
                )
            else:
                result = (False, _("Unable to load model file."))
        else:
            result = (True, _("Ready"))

        self.onnx_validation_cache[cache_key] = result
        return result

    def validate_file_param(self, param, path):
        """Validate a pre-processing file field."""
        _ = get_app()._tr
        if param.get("required") and not path:
            return False, _("Required file")
        if not path:
            return True, ""
        if not os.path.isfile(path):
            return False, _("File not found")

        validator = param.get("validator")
        if validator == "onnx":
            if not path.lower().endswith(".onnx"):
                return False, _("Expected a model file.")
            if os.path.getsize(path) <= 0:
                return False, _("Model file is empty.")
            return self.validate_onnx_model_load(path)
        elif validator == "classes":
            try:
                with open(path, "r", encoding="utf-8") as classes_file:
                    class_names = [line.strip() for line in classes_file if line.strip()]
            except OSError:
                return False, _("Unable to read class names")
            if not class_names:
                return False, _("Class names file is empty")
        return True, _("Ready")

    def update_file_validation(self):
        """Update validation indicators and Process button state."""
        if self.file_validation_timer.isActive():
            self.file_validation_timer.stop()

        all_valid = True
        for setting, field in self.file_fields.items():
            path = field["path"].text()
            valid, message = self.validate_file_param(field["param"], path)
            status = field["status"]
            status.setText("✓" if valid else "✕")
            status.setStyleSheet("color: #4caf50; font-weight: bold;" if valid else "color: #e53935; font-weight: bold;")
            status.setToolTip(message)
            all_valid = all_valid and valid

        if hasattr(self, "process_button"):
            self.process_button.setEnabled(all_valid)

    def file_sha256(self, path):
        """Return the SHA256 checksum of a file."""
        digest = hashlib.sha256()
        with open(path, "rb") as input_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def yolo5_default_files_match(self):
        """Return whether the default YOLOv5 files already match expected checksums."""
        try:
            return (
                os.path.isfile(YOLO5_MODEL_PATH)
                and os.path.isfile(YOLO5_CLASSES_PATH)
                and self.file_sha256(YOLO5_MODEL_PATH) == YOLO5_MODEL_SHA256
                and self.file_sha256(YOLO5_CLASSES_PATH) == YOLO5_CLASSES_SHA256
            )
        except OSError:
            return False

    def set_yolo5_default_file_fields(self, param):
        """Point the YOLOv5 file inputs at the default downloaded files."""
        for setting, path in (
            (param.get("model-setting"), YOLO5_MODEL_PATH),
            (param.get("classes-setting"), YOLO5_CLASSES_PATH),
        ):
            field = self.file_fields.get(setting)
            if field:
                field["path"].setText(path)

    def download_yolo5_clicked(self, widget, param):
        """Download the default YOLOv5 model files."""
        _ = get_app()._tr
        os.makedirs(YOLO5_DIR, exist_ok=True)

        if self.yolo5_default_files_match():
            self.set_yolo5_default_file_fields(param)
            self.update_file_validation()
            QMessageBox.information(
                self,
                self.model_message(_("Download %(model)s Files")),
                self.model_message(_("The %(model)s files are already downloaded.")),
            )
            return

        progress = QProgressDialog(
            self.model_message(_("Downloading %(model)s files...")),
            _("Cancel"),
            0,
            100,
            self,
        )
        progress.setWindowTitle(self.model_message(_("Download %(model)s Files")))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        zip_download_path = os.path.join(YOLO5_DIR, "yolov5s-openshot.zip.download")
        model_download_path = "{}.download".format(YOLO5_MODEL_PATH)
        classes_download_path = "{}.download".format(YOLO5_CLASSES_PATH)

        def remove_partial_downloads():
            for path in (zip_download_path, model_download_path, classes_download_path):
                if os.path.exists(path):
                    os.remove(path)

        def report_progress(downloaded_size, total_size):
            if total_size > 0:
                progress.setValue(min(100, int(downloaded_size * 100 / total_size)))
            else:
                progress.setValue(0)
            QCoreApplication.processEvents()
            if progress.wasCanceled():
                raise DownloadCancelled()

        try:
            http_client.download_file(
                http_client.urls_with_http_fallback(YOLO5_DOWNLOAD_URL),
                zip_download_path,
                self.model_message(_("%(model)s files")),
                report_progress,
                cancel_exceptions=(DownloadCancelled,),
            )
            if self.file_sha256(zip_download_path) != YOLO5_DOWNLOAD_SHA256:
                raise ValueError(self.model_message(_("Downloaded %(model)s files are invalid.")))

            with zipfile.ZipFile(zip_download_path) as yolo5_zip:
                for member_name, destination_path in (
                    ("yolov5s.onnx", model_download_path),
                    ("obj.names", classes_download_path),
                ):
                    with yolo5_zip.open(member_name) as source_file, open(destination_path, "wb") as output_file:
                        output_file.write(source_file.read())

            if self.file_sha256(model_download_path) != YOLO5_MODEL_SHA256:
                raise ValueError(self.model_message(_("Downloaded %(model)s files are invalid.")))
            if self.file_sha256(classes_download_path) != YOLO5_CLASSES_SHA256:
                raise ValueError(self.model_message(_("Downloaded %(model)s files are invalid.")))

            os.replace(model_download_path, YOLO5_MODEL_PATH)
            os.replace(classes_download_path, YOLO5_CLASSES_PATH)
        except DownloadCancelled:
            remove_partial_downloads()
            log.info("YOLOv5 file download cancelled")
            self.update_file_validation()
            return
        except Exception as ex:
            remove_partial_downloads()
            QMessageBox.warning(self, _("Download Failed"), str(ex))
            log.error("Failed to download YOLOv5 files: %s", ex)
            self.update_file_validation()
            return
        finally:
            if os.path.exists(zip_download_path):
                os.remove(zip_download_path)
            progress.close()

        self.set_yolo5_default_file_fields(param)
        self.update_file_validation()

    def rect_select_clicked(self, widget, param):
        """Rect select button clicked"""
        _ = get_app()._tr
        self.context[param["setting"]].update({"button-clicked": True})

        # show dialog
        from windows.region import SelectRegion
        from classes.query import File, Clip

        c = Clip.get(id=self.clip_id)
        reader_path = c.data.get('reader', {}).get('path','')
        f = File.get(path=reader_path)
        if f:
            win = SelectRegion(f, self.clip_instance, parent=self)
            # Run the dialog event loop - blocking interaction on this window during that time
            result = win.exec_()
            if result == QDialog.Accepted:
                # self.first_frame = win.current_frame
                # Region selected (get coordinates if any)
                selected_rect = win.selected_rect_normalized() if hasattr(win, "selected_rect_normalized") else None
                if selected_rect:
                    x1 = float(selected_rect.get("normalized_x", 0.0))
                    y1 = float(selected_rect.get("normalized_y", 0.0))
                    xw = float(selected_rect.get("normalized_width", 0.0))
                    yh = float(selected_rect.get("normalized_height", 0.0))
                else:
                    topLeft = win.videoPreview.regionTopLeftHandle
                    bottomRight = win.videoPreview.regionBottomRightHandle
                    curr_frame_size = win.videoPreview.curr_frame_size
                    if not topLeft or not bottomRight or not curr_frame_size:
                        QMessageBox.warning(
                            self,
                            _("Invalid Region"),
                            _("Please draw a rectangle region before clicking Select Region."),
                        )
                        return
                    x1 = topLeft.x() / curr_frame_size.width()
                    y1 = topLeft.y() / curr_frame_size.height()
                    x2 = bottomRight.x() / curr_frame_size.width()
                    y2 = bottomRight.y() / curr_frame_size.height()
                    xw = x2 - x1
                    yh = y2 - y1

                # Get QImage of region
                region_qimage = win.selected_region_qimage() if hasattr(win, "selected_region_qimage") else None
                if region_qimage is None and win.videoPreview.region_qimage:
                    region_qimage = win.videoPreview.region_qimage
                if region_qimage:

                    # Resize QImage to match button size
                    resized_qimage = region_qimage.scaled(widget.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

                    # Remove button text (so region QImage is more visible)
                    widget.setImage(resized_qimage)
                    widget.setText("")

                # If data found, add to context
                self.context[param["setting"]].update({"normalized_x": x1, "normalized_y": y1,
                                                       "normalized_width": xw,
                                                       "normalized_height": yh,
                                                       "first-frame": win.current_frame,
                                                       })
                log.info(self.context)

        else:
            log.error('No file found with path: %s' % reader_path)

    def accept(self):
        """ Start processing effect """
        _ = get_app()._tr
        self.update_file_validation()
        if self.file_fields and not self.process_button.isEnabled():
            return

        # Enable ProgressBar
        self.progressBar.setEnabled(True)
        self.process_button.setEnabled(False)

        # Print effect settings
        log.info(self.context)

        # Create effect Id and protobuf data path
        ID = get_app().project.generate_id()

        # Create protobuf data path
        protobufPath = os.path.join(info.PROTOBUF_DATA_PATH, ID + '.data')
        if os.name == 'nt' : protobufPath = protobufPath.replace("\\", "/")

        self.context["protobuf_data_path"] = protobufPath

        # Load into JSON string info about protobuf data path
        jsonString = json.dumps(self.context)

        def show_processing_error(message=None):
            """Show a processing failure and leave the dialog open for correction."""
            if not message:
                message = _("Unable to process this effect. Check the model files and settings.")
            self.progressBar.setEnabled(False)
            self.process_button.setEnabled(True)
            QMessageBox.warning(self, _("Processing Failed"), message)

        def cancel_processing(max_wait_seconds=1.0):
            """Request cancellation without allowing libopenshot to freeze this dialog."""
            processing.CancelProcessing()
            wait_start = time.time()
            while not processing.IsDone() and (time.time() - wait_start) < max_wait_seconds:
                QCoreApplication.processEvents()
                time.sleep(0.01)

        # Generate processed data
        try:
            processing = openshot.ClipProcessingJobs(self.effect_class, jsonString)
            processing.processClip(self.clip_instance, jsonString)
        except Exception as ex:
            log.error("Failed to start effect processing: %s", ex)
            show_processing_error(str(ex))
            return

        # get processing status
        blank_error_start = None
        while(not processing.IsDone() ):
            if processing.GetError():
                message = (processing.GetErrorMessage() or "").strip()
                if message:
                    log.error("Effect processing failed: %s", message)
                    cancel_processing()
                    show_processing_error(message)
                    return
                if blank_error_start is None:
                    blank_error_start = time.time()
                elif time.time() - blank_error_start > 3.0:
                    log.error("Effect processing failed without an error message")
                    cancel_processing()
                    show_processing_error()
                    return
            else:
                blank_error_start = None

            # update progressbar
            progressionStatus = processing.GetProgress()
            self.progressBar.setValue(int(progressionStatus))
            time.sleep(0.01)

            # Process any queued events
            QCoreApplication.processEvents()

            # if the cancel button was pressed, close the processing thread
            if(self.cancel_clip_processing):
                cancel_processing()

        if not self.cancel_clip_processing and processing.GetError():
            message = (processing.GetErrorMessage() or "").strip()
            log.error(
                "Effect processing failed%s",
                ": %s" % message if message else "",
            )
            show_processing_error(message)
            return

        if(not self.cancel_clip_processing):
            # Load processed data into effect
            self.effect = openshot.EffectInfo().CreateEffect(self.effect_class)
            self.effect.SetJson( '{"protobuf_data_path": "%s"}' % protobufPath )
            self.effect.Id(ID)

            # Accept dialog
            super(ProcessEffect, self).accept()

    def reject(self):
        # Cancel dialog
        self.exporting = False
        self.cancel_clip_processing = True
        super(ProcessEffect, self).reject()
