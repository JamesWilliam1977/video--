"""
 @file
 @brief This file contains Comfy generation orchestration logic.
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
import re
import tempfile
from time import time

import openshot
from PyQt5.QtWidgets import QMessageBox, QDialog

from classes import info
from classes.app import get_app
from classes.comfy_client import ComfyClient
from classes.comfy_pipelines import (
    available_pipelines,
    build_workflow,
    is_supported_img2img_path,
    pipeline_requires_checkpoint,
    pipeline_requires_upscale_model,
    DEFAULT_SD_CHECKPOINT,
    DEFAULT_UPSCALE_MODEL,
)
from classes.logger import log
from classes.query import File
from windows.generate import GenerateMediaDialog


class GenerationService:
    """Encapsulates generation-specific UI + workflow behavior."""

    def __init__(self, win):
        self.win = win
        self._generation_temp_files = []
        self._comfy_status_cache = {"checked_at": 0.0, "available": False}

    def cleanup_temp_files(self):
        for tmp_path in list(self._generation_temp_files):
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
        self._generation_temp_files = []

    def comfy_ui_url(self):
        url = get_app().get_settings().get("comfy-ui-url") or "http://127.0.0.1:8188"
        return str(url).strip().rstrip("/")

    def is_comfy_available(self, force=False):
        now = time()
        if not force and (now - self._comfy_status_cache["checked_at"]) < 2.0:
            return self._comfy_status_cache["available"]

        url = self.comfy_ui_url()
        available = False
        try:
            available = ComfyClient(url).ping(timeout=0.5)
        except Exception:
            available = False

        self._comfy_status_cache["checked_at"] = now
        self._comfy_status_cache["available"] = available
        return available

    def can_open_generate_dialog(self):
        return len(self.win.selected_file_ids()) <= 1

    def _prepare_generation_source_path(self, source_file, template_id):
        if not source_file:
            return ""

        source_path = source_file.data.get("path", "")
        media_type = source_file.data.get("media_type")
        if template_id not in ("img2img-basic", "upscale-realesrgan-x4") or media_type != "image":
            return source_path

        if is_supported_img2img_path(source_path):
            return source_path

        tmp_fd, tmp_png = tempfile.mkstemp(prefix="openshot-comfy-", suffix=".png")
        os.close(tmp_fd)
        try:
            clip = openshot.Clip(source_path)
            frame = clip.Reader().GetFrame(1)
            frame.Save(tmp_png, 1.0)
            self._generation_temp_files.append(tmp_png)
            return tmp_png
        except Exception:
            try:
                os.remove(tmp_png)
            except OSError:
                pass
            raise

    def _prepare_generation_video_input(self, source_file, client):
        if not source_file:
            raise ValueError("A source video is required.")
        source_path = source_file.data.get("path", "")
        if not source_path:
            raise ValueError("Source video path is invalid.")
        return client.upload_input_file(source_path)

    def _prepare_generation_image_input(self, local_image_path, client):
        local_image_path = str(local_image_path or "").strip()
        if not local_image_path:
            raise ValueError("A source image is required.")
        return client.upload_input_file(local_image_path)

    def action_generate_trigger(self, checked=True):
        selected_files = self.win.selected_files()
        if len(selected_files) > 1:
            return

        if not self.is_comfy_available(force=True):
            msg = QMessageBox(self.win)
            msg.setWindowTitle("ComfyUI Unavailable")
            msg.setText(
                "OpenShot could not connect to ComfyUI at:\n{}\n\n"
                "Start ComfyUI or update the URL in Preferences > Experimental.".format(self.comfy_ui_url())
            )
            msg.exec_()
            return

        source_file = selected_files[0] if selected_files else None
        templates = available_pipelines(source_file=source_file)
        win = GenerateMediaDialog(source_file=source_file, templates=templates, parent=self.win)
        if win.exec_() != QDialog.Accepted:
            return

        payload = win.get_payload()
        payload_name = self._next_generation_name(payload.get("name"))
        source_file_id = source_file.id if source_file else None
        try:
            source_path = self._prepare_generation_source_path(source_file, payload.get("template_id"))
        except Exception as ex:
            QMessageBox.warning(
                self.win,
                "Source Conversion Failed",
                "OpenShot could not convert this image into PNG for ComfyUI.\n\n{}".format(ex),
            )
            return
        pipeline_id = payload.get("template_id")
        checkpoint_name = None
        upscale_model_name = None
        client = ComfyClient(self.comfy_ui_url())
        workflow_source = source_path

        if pipeline_id == "video-upscale-gan":
            if not source_file or source_file.data.get("media_type") != "video":
                QMessageBox.information(self.win, "Invalid Input", "This pipeline requires a source video file.")
                return
            try:
                workflow_source = self._prepare_generation_video_input(source_file, client)
            except Exception as ex:
                QMessageBox.warning(
                    self.win,
                    "Video Upload Failed",
                    "OpenShot could not upload the source video into ComfyUI input.\n\n{}".format(ex),
                )
                return
        elif pipeline_id in ("img2img-basic", "upscale-realesrgan-x4"):
            try:
                workflow_source = self._prepare_generation_image_input(source_path, client)
            except Exception as ex:
                QMessageBox.warning(
                    self.win,
                    "Image Upload Failed",
                    "OpenShot could not upload the source image into ComfyUI input.\n\n{}".format(ex),
                )
                return

        try:
            if pipeline_requires_checkpoint(pipeline_id):
                checkpoint_names = client.list_checkpoints()
                if checkpoint_names:
                    checkpoint_name = (
                        DEFAULT_SD_CHECKPOINT if DEFAULT_SD_CHECKPOINT in checkpoint_names else checkpoint_names[0]
                    )
        except Exception as ex:
            log.warning("Failed to query ComfyUI checkpoints: %s", ex)

        if pipeline_requires_checkpoint(pipeline_id) and not checkpoint_name:
            QMessageBox.information(
                self.win,
                "No Checkpoints Found",
                "ComfyUI has no checkpoints available for CheckpointLoaderSimple.\n"
                "Add a model to ComfyUI/models/checkpoints and try again.",
            )
            return

        try:
            if pipeline_requires_upscale_model(pipeline_id):
                upscale_models = client.list_upscale_models()
                if upscale_models:
                    upscale_model_name = (
                        DEFAULT_UPSCALE_MODEL if DEFAULT_UPSCALE_MODEL in upscale_models else upscale_models[0]
                    )
        except Exception as ex:
            log.warning("Failed to query ComfyUI upscale models: %s", ex)

        if pipeline_requires_upscale_model(pipeline_id) and not upscale_model_name:
            QMessageBox.information(
                self.win,
                "No Upscale Models Found",
                "ComfyUI has no upscaler models available for UpscaleModelLoader.\n"
                "Add a model such as RealESRGAN_x4plus.safetensors to ComfyUI/models/upscale_models and try again.",
            )
            return

        try:
            workflow = build_workflow(
                pipeline_id,
                payload.get("prompt"),
                workflow_source,
                payload_name,
                checkpoint_name=checkpoint_name,
                upscale_model_name=upscale_model_name,
            )
        except Exception as ex:
            QMessageBox.information(self.win, "Invalid Input", str(ex))
            return
        request = {
            "comfy_url": self.comfy_ui_url(),
            "workflow": workflow,
            "client_id": "openshot-qt",
            "timeout_s": 21600,
            "save_node_ids": [
                str(node_id)
                for node_id, node in workflow.items()
                if node.get("class_type") in ("SaveImage", "SaveVideo")
            ],
        }
        job_id = self.win.generation_queue.enqueue(
            payload_name,
            payload.get("template_id"),
            payload.get("prompt"),
            source_file_id=source_file_id,
            request=request,
        )
        if not job_id:
            QMessageBox.information(
                self.win,
                "Generation Already Active",
                "Only one active generation is allowed per source file.",
            )
            return

        self.win.statusBar.showMessage("Queued generation job", 3000)

    def on_generation_job_finished(self, job_id, status):
        job = self.win.generation_queue.get_job(job_id) if getattr(self.win, "generation_queue", None) else None
        if not job:
            return

        if status == "completed":
            imported = self._import_generation_outputs(job)
            if imported > 0:
                self.win.statusBar.showMessage("Generation completed and imported {} file(s)".format(imported), 5000)
            else:
                self.win.statusBar.showMessage("Generation completed (no output files found)", 5000)
            return

        if status == "canceled":
            self.win.statusBar.showMessage("Generation canceled", 3000)
            return

        if status == "failed":
            error_text = str(job.get("error") or "ComfyUI generation failed.")
            self.win.statusBar.showMessage("Generation failed", 5000)
            QMessageBox.warning(self.win, "Generation Failed", error_text)

    def _import_generation_outputs(self, job):
        outputs = list(job.get("outputs", []) or [])
        if not outputs:
            return 0

        request = job.get("request", {}) or {}
        comfy_url = str(request.get("comfy_url") or self.comfy_ui_url())
        client = ComfyClient(comfy_url)
        output_dir = os.path.join(info.USER_PATH, "comfy_outputs")
        os.makedirs(output_dir, exist_ok=True)

        name_raw = str(job.get("name") or "generation")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name_raw).strip("._")
        if not safe_name:
            safe_name = "generation"

        saved_paths = []
        for index, image_ref in enumerate(outputs, start=1):
            original_name = str(image_ref.get("filename", "output.png"))
            ext = os.path.splitext(original_name)[1] or ".png"
            local_name = "{}_{}{}".format(safe_name, str(index).zfill(3), ext)
            local_path = self._next_available_path(os.path.join(output_dir, local_name))
            try:
                client.download_image(image_ref, local_path)
                saved_paths.append(local_path)
            except Exception as ex:
                log.warning("Failed to download Comfy output %s: %s", image_ref, ex)

        if not saved_paths:
            return 0

        self.win.files_model.add_files(
            saved_paths,
            quiet=True,
            prevent_image_seq=True,
            prevent_recent_folder=True,
        )
        return len(saved_paths)

    def _next_generation_name(self, requested_name):
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", str(requested_name or "").strip()).strip("._")
        if not base:
            base = "generation"

        existing_names = set()
        for file_obj in File.filter():
            if not file_obj:
                continue
            display_name = str(file_obj.data.get("name") or os.path.basename(file_obj.data.get("path", "")) or "")
            if display_name:
                stem = os.path.splitext(display_name)[0]
                existing_names.add(stem.lower())

        if base.lower() not in existing_names:
            return base

        name_root = base
        m = re.match(r"^(.*?)(?:_gen(\d+))?$", base, re.IGNORECASE)
        if m:
            name_root = (m.group(1) or base).rstrip("_") or "generation"
        n = 1
        while True:
            candidate = "{}_gen{}".format(name_root, n)
            if candidate.lower() not in existing_names:
                return candidate
            n += 1

    def _next_available_path(self, path):
        if not os.path.exists(path):
            return path
        folder = os.path.dirname(path)
        stem, ext = os.path.splitext(os.path.basename(path))
        n = 2
        while True:
            candidate = os.path.join(folder, "{}_{}{}".format(stem, n, ext))
            if not os.path.exists(candidate):
                return candidate
            n += 1
