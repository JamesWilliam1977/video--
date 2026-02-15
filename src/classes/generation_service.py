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
from urllib.parse import unquote
from fractions import Fraction

import openshot
from PyQt5.QtWidgets import QMessageBox, QDialog

from classes import info
from classes import time_parts
from classes.app import get_app
from classes.comfy_client import ComfyClient
from classes.comfy_pipelines import (
    available_pipelines,
    build_workflow,
    is_supported_img2img_path,
    pipeline_requires_checkpoint,
    pipeline_requires_svd_checkpoint,
    pipeline_requires_stable_audio_clip,
    pipeline_requires_rife_model,
    pipeline_requires_upscale_model,
    DEFAULT_RIFE_VFI_MODEL,
    DEFAULT_SD_CHECKPOINT,
    DEFAULT_SD_BASE_CHECKPOINT,
    DEFAULT_STABLE_AUDIO_CHECKPOINT,
    DEFAULT_STABLE_AUDIO_CLIP,
    DEFAULT_SVD_CHECKPOINT,
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
        if template_id not in ("img2img-basic", "upscale-realesrgan-x4", "img2video-svd") or media_type != "image":
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

    def _get_source_fps(self, source_file):
        if not source_file:
            return None
        fps_data = source_file.data.get("fps")
        if isinstance(fps_data, dict):
            try:
                num = float(fps_data.get("num", 0))
                den = float(fps_data.get("den", 0))
            except (TypeError, ValueError):
                num = den = 0.0
            if num > 0 and den > 0:
                return num / den
        return None

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
        stable_audio_clip_name = None
        svd_checkpoint_name = None
        rife_model_name = None
        client = ComfyClient(self.comfy_ui_url())
        workflow_source = source_path

        if pipeline_id in (
            "video-upscale-gan",
            "video2video-basic",
            "video-whisper-srt",
            "video-frame-interpolation-rife2x",
            "video-segment-scenes-transnet",
        ):
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
        elif pipeline_id in ("img2img-basic", "upscale-realesrgan-x4", "img2video-svd"):
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
            checkpoint_names = []
            if pipeline_requires_checkpoint(pipeline_id) or pipeline_requires_svd_checkpoint(pipeline_id):
                checkpoint_names = client.list_checkpoints()
                if checkpoint_names:
                    preferred_checkpoint = DEFAULT_SD_CHECKPOINT
                    if pipeline_id == "txt2audio-stable-open":
                        preferred_checkpoint = DEFAULT_STABLE_AUDIO_CHECKPOINT
                    elif pipeline_id in ("txt2video-svd", "video2video-basic"):
                        preferred_checkpoint = DEFAULT_SD_BASE_CHECKPOINT
                    checkpoint_name = (
                        preferred_checkpoint if preferred_checkpoint in checkpoint_names else checkpoint_names[0]
                    )
                if pipeline_requires_svd_checkpoint(pipeline_id):
                    if DEFAULT_SVD_CHECKPOINT in checkpoint_names:
                        svd_checkpoint_name = DEFAULT_SVD_CHECKPOINT
                    else:
                        # Prefer any checkpoint that appears to be an SVD model.
                        svd_candidates = [name for name in checkpoint_names if "svd" in str(name).lower()]
                        if svd_candidates:
                            svd_checkpoint_name = svd_candidates[0]
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

        if pipeline_requires_svd_checkpoint(pipeline_id) and not svd_checkpoint_name:
            QMessageBox.information(
                self.win,
                "No SVD Checkpoint Found",
                "ComfyUI could not find the SVD checkpoint required for the selected video generation template.\n"
                "Add an SVD checkpoint (for example {}) to ComfyUI/models/checkpoints and try again.".format(DEFAULT_SVD_CHECKPOINT),
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
            if pipeline_requires_stable_audio_clip(pipeline_id):
                clip_names = client.list_clip_models()
                if clip_names:
                    for preferred in (DEFAULT_STABLE_AUDIO_CLIP, "t5_base.safetensors"):
                        if preferred in clip_names:
                            stable_audio_clip_name = preferred
                            break
                    if not stable_audio_clip_name:
                        stable_audio_clip_name = clip_names[0]
        except Exception as ex:
            log.warning("Failed to query ComfyUI CLIP models: %s", ex)

        if pipeline_requires_stable_audio_clip(pipeline_id) and not stable_audio_clip_name:
            QMessageBox.information(
                self.win,
                "No Text Encoders Found",
                "ComfyUI has no CLIP/text-encoder models available for CLIPLoader.\n"
                "Add a text encoder such as t5-base.safetensors and try again.",
            )
            return

        try:
            if pipeline_requires_rife_model(pipeline_id):
                rife_models = client.list_rife_vfi_models()
                if rife_models:
                    for preferred in (DEFAULT_RIFE_VFI_MODEL, "rife49.pth"):
                        if preferred in rife_models:
                            rife_model_name = preferred
                            break
                    if not rife_model_name:
                        rife_model_name = rife_models[0]
        except Exception as ex:
            log.warning("Failed to query ComfyUI RIFE VFI models: %s", ex)

        if pipeline_requires_rife_model(pipeline_id) and not rife_model_name:
            QMessageBox.information(
                self.win,
                "RIFE VFI Not Available",
                "ComfyUI could not find the RIFE VFI node/models required for frame interpolation.\n"
                "Install ComfyUI-Frame-Interpolation and add models such as rife47.pth.",
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
                stable_audio_clip_name=stable_audio_clip_name,
                svd_checkpoint_name=svd_checkpoint_name,
                source_fps=self._get_source_fps(source_file),
                rife_model_name=rife_model_name,
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
                if node.get("class_type") in (
                    "SaveImage",
                    "SaveVideo",
                    "SaveAudio",
                    "Save SRT",
                    "PreviewAny",
                    "TransNetV2_Run",
                )
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
            result = self._import_generation_outputs(job)
            imported = int(result.get("imported", 0))
            caption_saved = bool(result.get("caption_saved", False))
            scenes_labeled = int(result.get("scenes_labeled", 0))
            if imported > 0 and caption_saved:
                self.win.statusBar.showMessage(
                    "Generation completed, imported {} file(s), and saved file caption data".format(imported),
                    5000,
                )
            elif imported > 0 and scenes_labeled > 0:
                self.win.statusBar.showMessage(
                    "Generation completed, imported {} file(s), and labeled {} scene segment(s)".format(
                        imported, scenes_labeled
                    ),
                    5000,
                )
            elif imported > 0:
                self.win.statusBar.showMessage("Generation completed and imported {} file(s)".format(imported), 5000)
            elif caption_saved:
                self.win.statusBar.showMessage("Generation completed and saved file caption data", 5000)
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
            return {"imported": 0, "caption_saved": False}

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
        text_outputs = []
        video_path_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
        seen_video_payload_paths = set()
        for index, output_ref in enumerate(outputs, start=1):
            text_payload = str(output_ref.get("text", "")).strip()
            if text_payload:
                payload_video_paths = self._extract_video_paths_from_text(text_payload)
                if not payload_video_paths:
                    payload_ext = os.path.splitext(text_payload)[1].lower()
                    if payload_ext in video_path_exts:
                        payload_video_paths = [text_payload]
                downloaded_any_video = False
                for raw_video_path in payload_video_paths:
                    norm_video_path = str(raw_video_path).strip().replace("\\", "/")
                    if not norm_video_path or norm_video_path in seen_video_payload_paths:
                        continue
                    seen_video_payload_paths.add(norm_video_path)

                    payload_ext = os.path.splitext(norm_video_path)[1].lower() or ".mp4"
                    video_ref = self._comfy_output_ref_from_path(norm_video_path)
                    if not video_ref:
                        continue
                    local_name = "{}_{}{}".format(safe_name, str(index).zfill(3), payload_ext)
                    local_path = self._next_available_path(os.path.join(output_dir, local_name))
                    try:
                        client.download_output_file(video_ref, local_path)
                        saved_paths.append(local_path)
                        downloaded_any_video = True
                    except Exception as ex:
                        log.warning(
                            "Failed to download segmented video from Comfy path output %s: %s",
                            raw_video_path,
                            ex,
                        )
                if downloaded_any_video:
                    continue

                # Some Save SRT node variants return the output file path as text.
                # Convert that path to a downloadable Comfy output ref when possible.
                if text_payload.lower().endswith(".srt"):
                    srt_ref = self._comfy_output_ref_from_path(text_payload)
                    if srt_ref:
                        local_name = "{}_{}{}".format(safe_name, str(index).zfill(3), ".srt")
                        local_path = self._next_available_path(os.path.join(output_dir, local_name))
                        try:
                            client.download_output_file(srt_ref, local_path)
                            with open(local_path, "r", encoding="utf-8") as handle:
                                srt_text = handle.read().strip()
                            if srt_text:
                                saved_paths.append(local_path)
                                text_outputs.append(srt_text)
                                continue
                        except Exception as ex:
                            log.warning("Failed to download/read SRT from Comfy path output %s: %s", text_payload, ex)

                ext = ".srt" if str(output_ref.get("format", "")).lower() == "srt" else ".txt"
                local_name = "{}_{}{}".format(safe_name, str(index).zfill(3), ext)
                local_path = self._next_available_path(os.path.join(output_dir, local_name))
                try:
                    with open(local_path, "w", encoding="utf-8") as handle:
                        handle.write(text_payload)
                    saved_paths.append(local_path)
                    text_outputs.append(text_payload)
                except Exception as ex:
                    log.warning("Failed to write Comfy text output to %s: %s", local_path, ex)
                continue

            original_name = str(output_ref.get("filename", "output.png"))
            ext = os.path.splitext(original_name)[1] or ".png"
            local_name = "{}_{}{}".format(safe_name, str(index).zfill(3), ext)
            local_path = self._next_available_path(os.path.join(output_dir, local_name))
            try:
                client.download_output_file(output_ref, local_path)
                saved_paths.append(local_path)
            except Exception as ex:
                log.warning("Failed to download Comfy output %s: %s", output_ref, ex)

        if not saved_paths:
            return {"imported": 0, "caption_saved": False}

        self.win.files_model.add_files(
            saved_paths,
            quiet=True,
            prevent_image_seq=True,
            prevent_recent_folder=True,
        )

        caption_saved = False
        scenes_labeled = 0
        if str(job.get("template_id") or "") == "video-whisper-srt":
            caption_text = self._resolve_caption_text(saved_paths, text_outputs)
            caption_saved = self._store_caption_on_file(
                source_file_id=job.get("source_file_id"),
                caption_text=caption_text,
            )
        if str(job.get("template_id") or "") == "video-segment-scenes-transnet":
            scenes_labeled = self._apply_scene_segment_metadata(
                source_file_id=job.get("source_file_id"),
                saved_paths=saved_paths,
            )
        return {"imported": len(saved_paths), "caption_saved": caption_saved, "scenes_labeled": scenes_labeled}

    def _extract_video_paths_from_text(self, text_payload):
        """Extract absolute video file paths from log/text payloads."""
        text_payload = str(text_payload or "")
        if not text_payload:
            return []
        pattern = re.compile(
            r"([A-Za-z]:[\\/][^\r\n]+?\.(?:mp4|mov|mkv|webm|avi|m4v)|/[^\r\n]+?\.(?:mp4|mov|mkv|webm|avi|m4v))",
            re.IGNORECASE,
        )
        return [match.strip() for match in pattern.findall(text_payload) if match.strip()]

    def _resolve_caption_text(self, saved_paths, text_outputs):
        srt_path = ""
        for path in saved_paths:
            if str(path).lower().endswith(".srt"):
                srt_path = path
                break
        if srt_path:
            try:
                with open(srt_path, "r", encoding="utf-8") as handle:
                    text = handle.read().strip()
                if text:
                    return text
            except Exception as ex:
                log.warning("Failed reading SRT file for file caption metadata: %s", ex)

        for value in text_outputs:
            text = str(value or "").strip()
            if "-->" in text:
                return text

        for value in text_outputs:
            text = str(value or "").strip()
            if text:
                return text

        return ""

    def _store_caption_on_file(self, source_file_id, caption_text):
        caption_text = str(caption_text or "").strip()
        if not caption_text:
            return False

        source_file_value = source_file_id
        file_obj = File.get(id=source_file_value)
        if file_obj is None:
            file_obj = File.get(id=str(source_file_value or ""))
        if file_obj is None:
            log.info("No source file found for caption metadata update (file_id=%s)", source_file_value)
            return False

        if not isinstance(file_obj.data, dict):
            file_obj.data = {}
        file_obj.data["caption"] = caption_text
        file_obj.save()
        self.win.FileUpdated.emit(str(file_obj.id))
        return True

    def _seconds_to_compact_timecode(self, seconds_value, fps_fraction, include_hours=False, include_minutes=False):
        fps_fraction = fps_fraction if isinstance(fps_fraction, Fraction) and fps_fraction > 0 else Fraction(30, 1)
        fps_float = float(fps_fraction)
        frame_number = int(round(max(0.0, float(seconds_value or 0.0)) * fps_float)) + 1
        t = time_parts.secondsToTime((frame_number - 1) / fps_float, fps_fraction.numerator, fps_fraction.denominator)
        hours = int(t.get("hour", 0))
        minutes = int(t.get("min", 0))
        secs = int(t.get("sec", 0))
        frames = int(t.get("frame", 0))
        if include_hours:
            return "{:02d}:{:02d}:{:02d};{:02d}".format(hours, minutes, secs, frames)
        if include_minutes:
            return "{:02d}:{:02d};{:02d}".format(minutes, secs, frames)
        return "{:02d};{:02d}".format(secs, frames)

    def _append_scene_tag(self, file_obj):
        tags_raw = str(file_obj.data.get("tags", "") or "").strip()
        if not tags_raw:
            file_obj.data["tags"] = "scene"
            return
        tags = [part.strip() for part in tags_raw.split(",") if part.strip()]
        if any(part.lower() == "scene" for part in tags):
            return
        tags.append("scene")
        file_obj.data["tags"] = ", ".join(tags)

    def _apply_scene_segment_metadata(self, source_file_id, saved_paths):
        source_file = File.get(id=source_file_id) if source_file_id else None
        base_name = "scene"
        fps_fraction = Fraction(30, 1)
        if source_file:
            source_path = str(source_file.data.get("path", "") or "")
            if source_path:
                base_name = os.path.splitext(os.path.basename(source_path))[0] or base_name
            fps_data = source_file.data.get("fps", {})
            try:
                num = int(fps_data.get("num", 30))
                den = int(fps_data.get("den", 1) or 1)
                if num > 0 and den > 0:
                    fps_fraction = Fraction(num, den)
            except (TypeError, ValueError, ZeroDivisionError):
                fps_fraction = Fraction(30, 1)

        imported_files = []
        for path in saved_paths:
            file_obj = File.get(path=path)
            if file_obj and str(file_obj.data.get("media_type", "")) == "video":
                imported_files.append(file_obj)
        if not imported_files:
            return 0

        running_start = 0.0
        updated = 0
        for file_obj in imported_files:
            duration = float(file_obj.data.get("duration") or 0.0)
            if duration <= 0:
                start_trim = float(file_obj.data.get("start") or 0.0)
                end_trim = float(file_obj.data.get("end") or 0.0)
                duration = max(0.0, end_trim - start_trim)
            running_end = running_start + max(0.0, duration)

            include_hours = int(running_end // 3600) > 0
            include_minutes = include_hours or int((running_end % 3600) // 60) > 0
            start_tc = self._seconds_to_compact_timecode(
                running_start, fps_fraction, include_hours=include_hours, include_minutes=include_minutes
            )
            end_tc = self._seconds_to_compact_timecode(
                running_end, fps_fraction, include_hours=include_hours, include_minutes=include_minutes
            )
            file_obj.data["name"] = "{} ({} to {})".format(base_name, start_tc, end_tc)
            self._append_scene_tag(file_obj)
            file_obj.save()
            self.win.FileUpdated.emit(str(file_obj.id))

            running_start = running_end
            updated += 1

        return updated

    def _comfy_output_ref_from_path(self, path_text):
        """Convert a Comfy output absolute/relative path into a /view-compatible output ref."""
        path_text = unquote(str(path_text or "").strip())
        if not path_text:
            return None
        normalized = path_text.replace("\\", "/")
        filename = os.path.basename(normalized)
        if not filename:
            return None

        subfolder = ""
        marker = "/output/"
        if marker in normalized:
            rel = normalized.split(marker, 1)[1].lstrip("/")
            rel_dir = os.path.dirname(rel).strip("/")
            subfolder = rel_dir
        elif normalized.startswith("output/"):
            rel = normalized[len("output/"):]
            rel_dir = os.path.dirname(rel).strip("/")
            subfolder = rel_dir
        else:
            if os.path.isabs(normalized):
                # Unknown absolute location outside Comfy output tree; fallback to basename only.
                return {
                    "filename": filename,
                    "subfolder": "",
                    "type": "output",
                }
            rel_dir = os.path.dirname(normalized).strip("/")
            if rel_dir and rel_dir != ".":
                subfolder = rel_dir

        return {
            "filename": filename,
            "subfolder": subfolder,
            "type": "output",
        }

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
