"""
 @file
 @brief This file contains some Effect metadata related to pre-processing of Effects
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Frank Dana <ferdnyc AT gmail com>

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
from classes.info import YOLO_PATH
import os

YOLO_DEFAULT_PATH = os.path.join(YOLO_PATH, "yolo26n-seg")
EDGESAM_DEFAULT_PATH = os.path.expanduser("~/Downloads/edgesam-opencv")
XMEM_DEFAULT_PATH = os.path.expanduser("~/Downloads/xmem-opencv")
# Not all Effects support pre-processing, so for now, this is a hard-coded
# solution to providing the pre-processing params needed for these special effects.

effect_options = {
    # TODO: Remove Example example options
    "Example": [
        {
            "title": "Region",
            "setting": "region",
            "x": 0.05,
            "y": 0.05,
            "width": 0.25,
            "height": 0.25,
            "type": "rect"
        },
        {
            "max": 100,
            "title": "Volume",
            "min": 0,
            "setting": "volume",
            "value": 75,
            "type": "spinner"
        },
        {
            "value": "blender",
            "title": "Blender Command (path)",
            "type": "text",
            "setting": "blender_command"
        },
        {
            "max": 192000,
            "title": "Default Audio Sample Rate",
            "min": 22050,
            "setting": "default-samplerate",
            "value": 48000,
            "values": [
                {
                    "value": 22050,
                    "name": "22050"
                },
                {
                    "value": 44100,
                    "name": "44100"
                },
                {
                    "value": 48000,
                    "name": "48000"
                },
                {
                    "value": 96000,
                    "name": "96000"
                },
                {
                    "value": 192000,
                    "name": "192000"
                }
            ],
            "type": "dropdown",
        }
    ],

    "Tracker": [
        {
            "title": "Region",
            "setting": "region",
            "x": 0.05,
            "y": 0.05,
            "width": 0.25,
            "height": 0.25,
            "first-frame": 1,
            "type": "rect"
        },

        {
            "title": "Tracker type",
            "setting": "tracker-type",
            "value": "KCF",
            "values": [
                {
                    "value": "KCF",
                    "name": "KCF"
                },
                {
                    "value": "MIL",
                    "name": "MIL"
                },
                {
                    "value": "BOOSTING",
                    "name": "BOOSTING"
                },
                {
                    "value": "TLD",
                    "name": "TLD"
                },
                {
                    "value": "MEDIANFLOW",
                    "name": "MEDIANFLOW"
                },
                {
                    "value": "MOSSE",
                    "name": "MOSSE"
                },
                {
                    "value": "CSRT",
                    "name": "CSRT"
                }
            ],
            "type": "dropdown",
        }
    ],

    "Stabilizer": [
        {
            "max": 100,
            "title": "Smoothing window",
            "min": 1,
            "setting": "smoothing-window",
            "value": 30,
            "type": "spinner"
        }
    ],

    "ObjectDetection": [
        {
            "title": "Model Files",
            "type": "download-yolo",
            "setting": "download-yolo",
            "model-setting": "model",
            "classes-setting": "classes_file"
        },
        {
            "value": os.path.join(YOLO_DEFAULT_PATH, "model.onnx"),
            "title": "Model File",
            "type": "file",
            "setting": "model",
            "file-filter": "Model files (*.onnx)",
            "validator": "onnx",
            "required": True
        },
        {
            "value": os.path.join(YOLO_DEFAULT_PATH, "classes.names"),
            "title": "Class Names",
            "type": "file",
            "setting": "classes_file",
            "file-filter": "Class names (*.names *.txt)",
            "validator": "classes",
            "required": True
        },
        {
            "title": "Processing Device",
            "setting": "processing-device",
            "value": "CPU",
            "values": [
                {
                    "value": "GPU",
                    "name": "GPU"
                },
                {
                    "value": "CPU",
                    "name": "CPU"
                }
            ],
            "type": "dropdown",
        }
    ],

    "ObjectMask": [
        {
            "value": os.path.join(EDGESAM_DEFAULT_PATH, "edge_sam_encoder.onnx"),
            "title": "Encoder Model File",
            "type": "file",
            "setting": "encoder_model",
            "file-filter": "Model files (*.onnx)",
            "validator": "onnx",
            "required": True
        },
        {
            "value": os.path.join(EDGESAM_DEFAULT_PATH, "edge_sam_decoder_np10.onnx"),
            "title": "Decoder Model File",
            "type": "file",
            "setting": "decoder_model",
            "file-filter": "Model files (*.onnx)",
            "validator": "onnx",
            "required": True
        },
        {
            "value": os.path.join(XMEM_DEFAULT_PATH, "XMem-encode_key.onnx"),
            "title": "XMem Key Encoder Model File",
            "type": "file",
            "setting": "xmem_encode_key_model",
            "file-filter": "Model files (*.onnx)",
            "validator": "onnx",
            "required": True
        },
        {
            "value": os.path.join(XMEM_DEFAULT_PATH, "XMem-encode_value-m1.onnx"),
            "title": "XMem Value Encoder Model File",
            "type": "file",
            "setting": "xmem_encode_value_model",
            "file-filter": "Model files (*.onnx)",
            "validator": "onnx",
            "required": True
        },
        {
            "value": os.path.join(XMEM_DEFAULT_PATH, "XMem-decode-m1.onnx"),
            "title": "XMem Decoder Model File",
            "type": "file",
            "setting": "xmem_decode_model",
            "file-filter": "Model files (*.onnx)",
            "validator": "onnx",
            "required": True
        },
        {
            "title": "Point / Region",
            "type": "object-mask-selection",
            "setting": "object_mask_selection"
        },
        {
            "title": "Processing Device",
            "setting": "processing-device",
            "value": "CPU",
            "values": [
                {
                    "value": "GPU",
                    "name": "GPU"
                },
                {
                    "value": "CPU",
                    "name": "CPU"
                }
            ],
            "type": "dropdown",
        }
    ]
}
