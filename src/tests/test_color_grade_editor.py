"""
 @file
 @brief Unit tests for ColorGrade editor helpers
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
import sys
import unittest

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from windows.color_grade_editor import (  # noqa: E402
    default_curve_data,
    default_wheels_data,
    is_achromatic_color,
    normalize_curve_data,
    normalize_wheels_data,
    puck_display_color,
)
from qt_api import QColor  # noqa: E402


class ColorGradeEditorTests(unittest.TestCase):
    def test_normalize_curve_data_injects_endpoints_and_sorts_points(self):
        curve = normalize_curve_data({
            "points": [
                {"x": 0.8, "y": 1.2},
                {"x": 0.2, "y": -1.0},
            ]
        })
        self.assertEqual(curve["points"][0]["x"], 0.0)
        self.assertEqual(curve["points"][-1]["x"], 1.0)
        self.assertGreaterEqual(curve["points"][1]["x"], curve["points"][0]["x"])

    def test_normalize_curve_data_falls_back_to_default(self):
        self.assertEqual(normalize_curve_data({}), default_curve_data())

    def test_normalize_curve_data_preserves_enabled_flag(self):
        curve = normalize_curve_data({"enabled": False, "points": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]})
        self.assertFalse(curve["enabled"])

    def test_normalize_wheels_data_clamps_values(self):
        wheels = normalize_wheels_data({
            "global": {"color": "#zzzzzz", "amount": 5, "luma": -5},
        })
        self.assertEqual(wheels["global"]["color"], "#ffffff")
        self.assertEqual(wheels["global"]["amount"], 1.0)
        self.assertEqual(wheels["global"]["luma"], -1.0)

    def test_normalize_wheels_data_supplies_missing_entries(self):
        wheels = normalize_wheels_data({})
        self.assertEqual(wheels, default_wheels_data())

    def test_normalize_wheels_data_preserves_enabled_flag(self):
        wheels = normalize_wheels_data({"enabled": False})
        self.assertFalse(wheels["enabled"])

    def test_achromatic_color_detection_treats_white_as_neutral(self):
        self.assertTrue(is_achromatic_color(QColor("#ffffff")))
        self.assertTrue(is_achromatic_color(QColor("#808080")))
        self.assertFalse(is_achromatic_color(QColor("#00ff24")))

    def test_puck_display_color_blends_from_neutral_to_hue(self):
        neutral = puck_display_color({"color": "#ff0000", "amount": 0.0})
        full = puck_display_color({"color": "#ff0000", "amount": 1.0})
        self.assertNotEqual(neutral.name(), full.name())
        self.assertEqual(full.name(), "#ff0000")


if __name__ == "__main__":
    unittest.main()
