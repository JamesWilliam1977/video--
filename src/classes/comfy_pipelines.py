"""
 @file
 @brief This file contains built-in ComfyUI pipeline definitions.
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

import random
import os


RASTER_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif",
}

DEFAULT_SD_CHECKPOINT = "sd_xl_turbo_1.0_fp16.safetensors"
DEFAULT_UPSCALE_MODEL = "RealESRGAN_x4plus.safetensors"


def is_supported_img2img_path(path):
    path_text = str(path or "").strip()
    # Comfy annotated paths can look like: "image.jpg [input]"
    if path_text.endswith("]") and " [" in path_text:
        path_text = path_text.rsplit(" [", 1)[0].strip()
    ext = os.path.splitext(path_text)[1].lower()
    return ext in RASTER_IMAGE_EXTENSIONS


def _supports_img2img(source_file=None):
    if not source_file:
        return False
    if source_file.data.get("media_type") != "image":
        return False
    path = source_file.data.get("path", "")
    return is_supported_img2img_path(path)


def _supports_video_upscale(source_file=None):
    if not source_file:
        return False
    return source_file.data.get("media_type") == "video"


def available_pipelines(source_file=None):
    pipelines = [{"id": "txt2img-basic", "name": "Basic Text to Image"}]
    if _supports_img2img(source_file):
        pipelines.insert(0, {"id": "img2img-basic", "name": "Basic Image Variation"})
        pipelines.insert(1, {"id": "upscale-realesrgan-x4", "name": "Upscale Image (RealESRGAN x4)"})
    if _supports_video_upscale(source_file):
        pipelines.append({"id": "video-upscale-gan", "name": "Upscale Video (GAN x4, first 10s)"})
    return pipelines


def pipeline_requires_checkpoint(pipeline_id):
    return str(pipeline_id or "") in ("txt2img-basic", "img2img-basic")


def pipeline_requires_upscale_model(pipeline_id):
    return str(pipeline_id or "") in ("upscale-realesrgan-x4", "video-upscale-gan")


def build_workflow(
    pipeline_id,
    prompt_text,
    source_path,
    output_prefix,
    checkpoint_name=None,
    upscale_model_name=None,
):
    prompt_text = str(prompt_text or "cinematic shot, highly detailed").strip()
    if not prompt_text:
        prompt_text = "cinematic shot, highly detailed"
    output_prefix = str(output_prefix or "openshot_gen").strip() or "openshot_gen"
    checkpoint_name = str(checkpoint_name or "").strip() or DEFAULT_SD_CHECKPOINT
    upscale_model_name = str(upscale_model_name or "").strip() or DEFAULT_UPSCALE_MODEL
    seed = random.randint(1, 2**31 - 1)

    if pipeline_id == "img2img-basic":
        if not is_supported_img2img_path(source_path):
            raise ValueError(
                "The selected file is not a supported raster image for this pipeline. "
                "Use PNG/JPG/WebP/BMP/TIFF or switch to Text to Image."
            )
        return {
            "1": {"inputs": {"ckpt_name": checkpoint_name}, "class_type": "CheckpointLoaderSimple"},
            "2": {"inputs": {"text": prompt_text, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
            "3": {"inputs": {"text": "low quality, blurry", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
            "4": {"inputs": {"image": str(source_path or ""), "upload": "image"}, "class_type": "LoadImage"},
            "5": {"inputs": {"pixels": ["4", 0], "vae": ["1", 2]}, "class_type": "VAEEncode"},
            "6": {
                "inputs": {
                    "seed": seed, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal",
                    "denoise": 0.65, "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "7": {"inputs": {"samples": ["6", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
            "8": {"inputs": {"filename_prefix": output_prefix, "images": ["7", 0]}, "class_type": "SaveImage"},
        }

    if pipeline_id == "upscale-realesrgan-x4":
        if not is_supported_img2img_path(source_path):
            raise ValueError(
                "The selected file is not a supported raster image for this pipeline. "
                "Use PNG/JPG/WebP/BMP/TIFF or switch to Text to Image."
            )
        return {
            "1": {"inputs": {"image": str(source_path or ""), "upload": "image"}, "class_type": "LoadImage"},
            "2": {"inputs": {"model_name": upscale_model_name}, "class_type": "UpscaleModelLoader"},
            "3": {"inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}, "class_type": "ImageUpscaleWithModel"},
            "4": {"inputs": {"filename_prefix": output_prefix, "images": ["3", 0]}, "class_type": "SaveImage"},
        }

    if pipeline_id == "video-upscale-gan":
        source_path = str(source_path or "").strip()
        if not source_path:
            raise ValueError("A source video is required for this pipeline.")
        return {
            "1": {"inputs": {"file": source_path}, "class_type": "LoadVideo"},
            "2": {
                "inputs": {"video": ["1", 0], "start_time": 0.0, "duration": 10.0, "strict_duration": False},
                "class_type": "Video Slice",
            },
            "3": {"inputs": {"video": ["2", 0]}, "class_type": "GetVideoComponents"},
            "4": {"inputs": {"model_name": upscale_model_name}, "class_type": "UpscaleModelLoader"},
            "5": {"inputs": {"upscale_model": ["4", 0], "image": ["3", 0]}, "class_type": "ImageUpscaleWithModel"},
            "6": {"inputs": {"images": ["5", 0], "audio": ["3", 1], "fps": ["3", 2]}, "class_type": "CreateVideo"},
            "7": {"inputs": {"video": ["6", 0], "filename_prefix": "video/{}".format(output_prefix), "format": "auto", "codec": "auto"}, "class_type": "SaveVideo"},
        }

    return {
        "1": {"inputs": {"ckpt_name": checkpoint_name}, "class_type": "CheckpointLoaderSimple"},
        "2": {"inputs": {"text": prompt_text, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "3": {"inputs": {"text": "low quality, blurry", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "4": {"inputs": {"width": 1024, "height": 576, "batch_size": 1}, "class_type": "EmptyLatentImage"},
        "5": {
            "inputs": {
                "seed": seed, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal",
                "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
            },
            "class_type": "KSampler",
        },
        "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
        "7": {"inputs": {"filename_prefix": output_prefix, "images": ["6", 0]}, "class_type": "SaveImage"},
    }
