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
DEFAULT_SD_BASE_CHECKPOINT = "sd_xl_base_1.0.safetensors"
DEFAULT_UPSCALE_MODEL = "RealESRGAN_x4plus.safetensors"
DEFAULT_STABLE_AUDIO_CHECKPOINT = "stable-audio-open-1.0.safetensors"
DEFAULT_STABLE_AUDIO_CLIP = "t5-base.safetensors"
DEFAULT_SVD_CHECKPOINT = "svd_xt.safetensors"
DEFAULT_RIFE_VFI_MODEL = "rife47.pth"


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
    pipelines = [
        {"id": "txt2img-basic", "name": "Basic Text to Image"},
        {"id": "txt2video-svd", "name": "Text to Video (txt_to_image_to_video)"},
        {"id": "txt2audio-stable-open", "name": "Text to Audio (Stable Audio Open)"},
    ]
    if _supports_img2img(source_file):
        pipelines.insert(0, {"id": "img2img-basic", "name": "Basic Image Variation"})
        pipelines.insert(1, {"id": "upscale-realesrgan-x4", "name": "Upscale Image (RealESRGAN x4)"})
        pipelines.insert(2, {"id": "img2video-svd", "name": "Image to Video (img_to_video)"})
    if _supports_video_upscale(source_file):
        pipelines.append({"id": "video-segment-scenes-transnet", "name": "Segment Scenes (TransNetV2)"})
        pipelines.append({"id": "video-frame-interpolation-rife2x", "name": "Frame Interpolation (RIFE 2x FPS)"})
        pipelines.append({"id": "video-upscale-gan", "name": "Upscale Video (GAN x4, first 10s)"})
        pipelines.append({"id": "video2video-basic", "name": "Video + Text to Video (Style Transfer)"})
        pipelines.append({"id": "video-whisper-srt", "name": "Whisper Transcribe to SRT (Caption Effect)"})
    return pipelines


def pipeline_requires_checkpoint(pipeline_id):
    return str(pipeline_id or "") in (
        "txt2img-basic",
        "img2img-basic",
        "txt2audio-stable-open",
        "txt2video-svd",
        "video2video-basic",
    )


def pipeline_requires_upscale_model(pipeline_id):
    return str(pipeline_id or "") in ("upscale-realesrgan-x4", "video-upscale-gan")


def pipeline_requires_stable_audio_clip(pipeline_id):
    return str(pipeline_id or "") in ("txt2audio-stable-open",)


def pipeline_requires_svd_checkpoint(pipeline_id):
    return str(pipeline_id or "") in ("txt2video-svd", "img2video-svd")


def pipeline_requires_rife_model(pipeline_id):
    return str(pipeline_id or "") in ("video-frame-interpolation-rife2x",)


def build_workflow(
    pipeline_id,
    prompt_text,
    source_path,
    output_prefix,
    checkpoint_name=None,
    upscale_model_name=None,
    stable_audio_clip_name=None,
    svd_checkpoint_name=None,
    source_fps=None,
    rife_model_name=None,
):
    prompt_text = str(prompt_text or "cinematic shot, highly detailed").strip()
    if not prompt_text:
        prompt_text = "cinematic shot, highly detailed"
    output_prefix = str(output_prefix or "openshot_gen").strip() or "openshot_gen"
    checkpoint_name = str(checkpoint_name or "").strip() or DEFAULT_SD_CHECKPOINT
    upscale_model_name = str(upscale_model_name or "").strip() or DEFAULT_UPSCALE_MODEL
    stable_audio_clip_name = str(stable_audio_clip_name or "").strip() or DEFAULT_STABLE_AUDIO_CLIP
    svd_checkpoint_name = str(svd_checkpoint_name or "").strip() or DEFAULT_SVD_CHECKPOINT
    rife_model_name = str(rife_model_name or "").strip() or DEFAULT_RIFE_VFI_MODEL
    try:
        source_fps_value = float(source_fps)
    except (TypeError, ValueError):
        source_fps_value = 30.0
    if source_fps_value <= 0:
        source_fps_value = 30.0
    target_fps = round(source_fps_value * 2.0, 6)
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

    if pipeline_id == "video-whisper-srt":
        source_path = str(source_path or "").strip()
        if not source_path:
            raise ValueError("A source video is required for this pipeline.")
        return {
            "1": {
                "inputs": {
                    "video": source_path,
                    "force_rate": 0,
                    "custom_width": 0,
                    "custom_height": 0,
                    "frame_load_cap": 0,
                    "skip_first_frames": 0,
                    "select_every_nth": 1,
                    "format": "AnimateDiff",
                },
                "class_type": "VHS_LoadVideo",
            },
            "2": {
                "inputs": {
                    "model": "medium",
                    "language": "auto",
                    "prompt": "",
                    "audio": ["1", 2],
                },
                "class_type": "Apply Whisper",
            },
            "3": {
                "inputs": {
                    "name": "{}_segments".format(output_prefix),
                    "alignment": ["2", 1],
                },
                "class_type": "Save SRT",
            },
            "4": {
                "inputs": {
                    "preview": "",
                    "previewMode": None,
                    "source": ["3", 0],
                },
                "class_type": "PreviewAny",
            },
        }

    if pipeline_id == "video-frame-interpolation-rife2x":
        source_path = str(source_path or "").strip()
        if not source_path:
            raise ValueError("A source video is required for this pipeline.")
        return {
            "1": {"inputs": {"file": source_path}, "class_type": "LoadVideo"},
            "2": {"inputs": {"video": ["1", 0]}, "class_type": "GetVideoComponents"},
            "3": {
                "inputs": {
                    "frames": ["2", 0],
                    "ckpt_name": rife_model_name,
                    "clear_cache_after_n_frames": 10,
                    "multiplier": 2,
                    "fast_mode": True,
                    "ensemble": True,
                    "scale_factor": 1,
                },
                "class_type": "RIFE VFI",
                "_meta": {"title": "RIFE VFI (recommend rife47 and rife49)"},
            },
            "4": {"inputs": {"images": ["3", 0], "audio": ["2", 1], "fps": target_fps}, "class_type": "CreateVideo"},
            "5": {
                "inputs": {
                    "video": ["4", 0],
                    "filename_prefix": "video/{}".format(output_prefix),
                    "format": "auto",
                    "codec": "auto",
                },
                "class_type": "SaveVideo",
            },
        }

    if pipeline_id == "video-segment-scenes-transnet":
        source_path = str(source_path or "").strip()
        if not source_path:
            raise ValueError("A source video is required for this pipeline.")
        return {
            "7": {"inputs": {"file": source_path}, "class_type": "LoadVideo"},
            "2": {
                "inputs": {
                    "model": "transnetv2-pytorch-weights",
                    "device": "auto",
                },
                "class_type": "DownloadAndLoadTransNetModel",
                "_meta": {"title": "MiaoshouAI Load TransNet Model"},
            },
            "1": {
                "inputs": {
                    "threshold": 0.5,
                    "min_scene_length": 30,
                    "output_dir": "output",
                    "TransNet_model": ["2", 0],
                    "video": ["7", 0],
                },
                "class_type": "TransNetV2_Run",
                "_meta": {"title": "MiaoshouAI Segment Video"},
            },
            "8": {
                "inputs": {
                    "index": 0,
                    "segment_paths": ["1", 0],
                },
                "class_type": "SelectVideo",
                "_meta": {"title": "MiaoshouAI Select Video"},
            },
            "9": {
                "inputs": {
                    "preview": "",
                    "previewMode": None,
                    "source": ["1", 0],
                },
                "class_type": "PreviewAny",
                "_meta": {"title": "Preview Any"},
            },
        }

    if pipeline_id == "txt2audio-stable-open":
        return {
            "3": {
                "inputs": {
                    "seed": seed,
                    "steps": 50,
                    "cfg": 5.0,
                    "sampler_name": "dpmpp_3m_sde_gpu",
                    "scheduler": "exponential",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["11", 0],
                },
                "class_type": "KSampler",
            },
            "4": {"inputs": {"ckpt_name": checkpoint_name}, "class_type": "CheckpointLoaderSimple"},
            "6": {"inputs": {"text": prompt_text, "clip": ["10", 0]}, "class_type": "CLIPTextEncode"},
            "7": {"inputs": {"text": "", "clip": ["10", 0]}, "class_type": "CLIPTextEncode"},
            "10": {"inputs": {"clip_name": stable_audio_clip_name, "type": "stable_audio"}, "class_type": "CLIPLoader"},
            "11": {"inputs": {"seconds": 30.0, "batch_size": 1}, "class_type": "EmptyLatentAudio"},
            "12": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEDecodeAudio"},
            "13": {"inputs": {"filename_prefix": "audio/{}".format(output_prefix), "audio": ["12", 0]}, "class_type": "SaveAudio"},
        }

    if pipeline_id == "txt2video-svd":
        return {
            "1": {"inputs": {"ckpt_name": svd_checkpoint_name}, "class_type": "ImageOnlyCheckpointLoader"},
            "2": {"inputs": {"ckpt_name": checkpoint_name}, "class_type": "CheckpointLoaderSimple"},
            "3": {"inputs": {"text": prompt_text, "clip": ["2", 1]}, "class_type": "CLIPTextEncode"},
            "4": {"inputs": {"text": "text, watermark", "clip": ["2", 1]}, "class_type": "CLIPTextEncode"},
            "5": {"inputs": {"width": 512, "height": 288, "batch_size": 1}, "class_type": "EmptyLatentImage"},
            "6": {
                "inputs": {
                    "seed": seed,
                    "steps": 15,
                    "cfg": 8.0,
                    "sampler_name": "uni_pc_bh2",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["2", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "7": {"inputs": {"samples": ["6", 0], "vae": ["2", 2]}, "class_type": "VAEDecode"},
            "8": {
                "inputs": {
                    "clip_vision": ["1", 1],
                    "init_image": ["7", 0],
                    "vae": ["1", 2],
                    "width": 512,
                    "height": 288,
                    "video_frames": 24,
                    "motion_bucket_id": 127,
                    "fps": 24,
                    "augmentation_level": 0.0,
                },
                "class_type": "SVD_img2vid_Conditioning",
            },
            "9": {"inputs": {"model": ["1", 0], "min_cfg": 1.0}, "class_type": "VideoLinearCFGGuidance"},
            "10": {
                "inputs": {
                    "seed": seed + 1,
                    "steps": 20,
                    "cfg": 2.5,
                    "sampler_name": "euler",
                    "scheduler": "karras",
                    "denoise": 1.0,
                    "model": ["9", 0],
                    "positive": ["8", 0],
                    "negative": ["8", 1],
                    "latent_image": ["8", 2],
                },
                "class_type": "KSampler",
            },
            "11": {"inputs": {"samples": ["10", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
            "12": {"inputs": {"images": ["11", 0], "fps": 24}, "class_type": "CreateVideo"},
            "13": {"inputs": {"video": ["12", 0], "filename_prefix": "video/{}".format(output_prefix), "format": "auto", "codec": "auto"}, "class_type": "SaveVideo"},
        }

    if pipeline_id == "img2video-svd":
        if not is_supported_img2img_path(source_path):
            raise ValueError(
                "The selected file is not a supported raster image for this pipeline. "
                "Use PNG/JPG/WebP/BMP/TIFF or switch to Text to Video."
            )
        return {
            "1": {"inputs": {"ckpt_name": svd_checkpoint_name}, "class_type": "ImageOnlyCheckpointLoader"},
            "2": {"inputs": {"image": str(source_path or ""), "upload": "image"}, "class_type": "LoadImage"},
            "3": {
                "inputs": {
                    "clip_vision": ["1", 1],
                    "init_image": ["2", 0],
                    "vae": ["1", 2],
                    "width": 512,
                    "height": 288,
                    "video_frames": 24,
                    "motion_bucket_id": 127,
                    "fps": 24,
                    "augmentation_level": 0.0,
                },
                "class_type": "SVD_img2vid_Conditioning",
            },
            "4": {"inputs": {"model": ["1", 0], "min_cfg": 1.0}, "class_type": "VideoLinearCFGGuidance"},
            "5": {
                "inputs": {
                    "seed": seed + 1,
                    "steps": 20,
                    "cfg": 2.5,
                    "sampler_name": "euler",
                    "scheduler": "karras",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["3", 0],
                    "negative": ["3", 1],
                    "latent_image": ["3", 2],
                },
                "class_type": "KSampler",
            },
            "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
            "7": {"inputs": {"images": ["6", 0], "fps": 24}, "class_type": "CreateVideo"},
            "8": {"inputs": {"video": ["7", 0], "filename_prefix": "video/{}".format(output_prefix), "format": "auto", "codec": "auto"}, "class_type": "SaveVideo"},
        }

    if pipeline_id == "video2video-basic":
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
            "4": {"inputs": {"ckpt_name": checkpoint_name}, "class_type": "CheckpointLoaderSimple"},
            "5": {"inputs": {"text": prompt_text, "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
            "6": {"inputs": {"text": "low quality, blurry", "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
            "7": {"inputs": {"pixels": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEEncode"},
            "8": {
                "inputs": {
                    "seed": seed, "steps": 16, "cfg": 6.0, "sampler_name": "euler", "scheduler": "normal",
                    "denoise": 0.55, "model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0],
                },
                "class_type": "KSampler",
            },
            "9": {"inputs": {"samples": ["8", 0], "vae": ["4", 2]}, "class_type": "VAEDecode"},
            "10": {"inputs": {"images": ["9", 0], "audio": ["3", 1], "fps": ["3", 2]}, "class_type": "CreateVideo"},
            "11": {"inputs": {"video": ["10", 0], "filename_prefix": "video/{}".format(output_prefix), "format": "auto", "codec": "auto"}, "class_type": "SaveVideo"},
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
