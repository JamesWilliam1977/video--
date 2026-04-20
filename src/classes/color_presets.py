"""
 @file
 @brief Reusable Color Grade preset payload helpers
"""

import copy


COLOR_GRADE_CLASS_NAME = "ColorGrade"

COLOR_PRESET_RESET = "reset"
COLOR_PRESET_AUTO_CONTRAST = "auto_contrast"
COLOR_PRESET_LIFT_SHADOWS = "lift_shadows"
COLOR_PRESET_WARM_UP = "warm_up"
COLOR_PRESET_BOOST_COLOR = "boost_color"


def default_curve_data():
    return {"enabled": True, "points": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]}


def default_wheels_data():
    return {
        "enabled": True,
        "global": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
        "shadows": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
        "midtones": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
        "highlights": {"color": "#ffffff", "amount": 0.0, "luma": 0.0},
    }


def is_color_grade_effect(effect_json):
    if not isinstance(effect_json, dict):
        return False
    return effect_json.get("class_name") == COLOR_GRADE_CLASS_NAME


def _constant_property(value):
    return {
        "Points": [
            {
                "co": {"X": 1.0, "Y": float(value)},
                "handle_left": {"X": 0.5, "Y": 1.0},
                "handle_right": {"X": 0.5, "Y": 0.0},
                "handle_type": 0,
                "interpolation": 0,
            }
        ]
    }


def _set_scalar(effect_json, key, value):
    effect_json[key] = _constant_property(value)


def _set_curve(effect_json, key, points, enabled=True):
    effect_json[key] = {
        "enabled": bool(enabled),
        "points": [{"x": float(point["x"]), "y": float(point["y"])} for point in points],
    }


def apply_color_grade_preset(effect_json, preset_name):
    payload = copy.deepcopy(effect_json or {})

    for key, value in (
        ("temperature", 0.0),
        ("tint", 0.0),
        ("exposure", 0.0),
        ("contrast", 0.0),
        ("highlights", 0.0),
        ("shadows", 0.0),
        ("saturation", 1.0),
        ("vibrance", 0.0),
        ("mix", 1.0),
        ("lut_intensity", 1.0),
    ):
        _set_scalar(payload, key, value)

    payload["lut_path"] = ""
    payload["wheels"] = default_wheels_data()
    payload["curve_master"] = default_curve_data()
    payload["curve_red"] = default_curve_data()
    payload["curve_green"] = default_curve_data()
    payload["curve_blue"] = default_curve_data()

    if preset_name == COLOR_PRESET_AUTO_CONTRAST:
        _set_scalar(payload, "contrast", 0.18)
        _set_scalar(payload, "highlights", -0.08)
        _set_scalar(payload, "shadows", 0.08)
        _set_scalar(payload, "vibrance", 0.06)
        _set_curve(payload, "curve_master", [
            {"x": 0.0, "y": 0.0},
            {"x": 0.25, "y": 0.22},
            {"x": 0.75, "y": 0.80},
            {"x": 1.0, "y": 1.0},
        ])
    elif preset_name == COLOR_PRESET_LIFT_SHADOWS:
        _set_scalar(payload, "exposure", 0.08)
        _set_scalar(payload, "contrast", -0.03)
        _set_scalar(payload, "highlights", -0.05)
        _set_scalar(payload, "shadows", 0.22)
        _set_curve(payload, "curve_master", [
            {"x": 0.0, "y": 0.06},
            {"x": 0.35, "y": 0.40},
            {"x": 1.0, "y": 1.0},
        ])
    elif preset_name == COLOR_PRESET_WARM_UP:
        _set_scalar(payload, "temperature", 0.18)
        _set_scalar(payload, "tint", 0.03)
        _set_scalar(payload, "saturation", 1.05)
        _set_scalar(payload, "vibrance", 0.08)
    elif preset_name == COLOR_PRESET_BOOST_COLOR:
        _set_scalar(payload, "contrast", 0.08)
        _set_scalar(payload, "saturation", 1.18)
        _set_scalar(payload, "vibrance", 0.22)
        _set_curve(payload, "curve_master", [
            {"x": 0.0, "y": 0.0},
            {"x": 0.20, "y": 0.16},
            {"x": 0.80, "y": 0.86},
            {"x": 1.0, "y": 1.0},
        ])
    else:
        raise ValueError("Unknown color preset: {}".format(preset_name))

    return payload
