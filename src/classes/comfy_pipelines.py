"""
 @file
 @brief Basic built-in ComfyUI pipeline definitions.
"""

import random
import os


RASTER_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif",
}


def is_supported_img2img_path(path):
    ext = os.path.splitext(str(path or ""))[1].lower()
    return ext in RASTER_IMAGE_EXTENSIONS


def _supports_img2img(source_file=None):
    if not source_file:
        return False
    if source_file.data.get("media_type") != "image":
        return False
    path = source_file.data.get("path", "")
    return is_supported_img2img_path(path)


def available_pipelines(source_file=None):
    pipelines = [{"id": "txt2img-basic", "name": "Basic Text to Image"}]
    if _supports_img2img(source_file):
        pipelines.insert(0, {"id": "img2img-basic", "name": "Basic Image Variation"})
    return pipelines


def build_workflow(pipeline_id, prompt_text, source_path, output_prefix, checkpoint_name=None):
    prompt_text = str(prompt_text or "cinematic shot, highly detailed").strip()
    if not prompt_text:
        prompt_text = "cinematic shot, highly detailed"
    output_prefix = str(output_prefix or "openshot_gen").strip() or "openshot_gen"
    checkpoint_name = str(checkpoint_name or "").strip() or "v1-5-pruned-emaonly.safetensors"
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
