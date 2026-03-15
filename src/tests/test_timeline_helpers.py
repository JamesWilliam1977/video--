"""
 @file
 @brief This file contains unit tests for timeline helper logic
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

import importlib
import os
import sys
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication
from classes.updates import UpdateAction

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
            "legacy-based-timeline": False,
        }

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()

    def get_settings(self):
        return self.settings

    def _tr(self, text):
        return text


class TimelineHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or DummyApp()
        cls.timeline_module = importlib.import_module("windows.views.timeline")

    def make_helper(self):
        timeline_module = self.timeline_module

        class Helper:
            def _transition_mask_reader(self, transition_data, fallback_data=None):
                return timeline_module.TimelineView._transition_mask_reader(
                    self,
                    transition_data,
                    fallback_data,
                )

            def _payload_contains_waveform(self, value):
                return timeline_module.TimelineView._payload_contains_waveform(self, value)

            def _collect_clip_ids_from_value(self, value, clip_ids):
                return timeline_module.TimelineView._collect_clip_ids_from_value(self, value, clip_ids)

        return Helper()

    def test_transition_reader_changed_detects_path_change(self):
        helper = self.make_helper()
        changed = self.timeline_module.TimelineView._transition_reader_changed(
            helper,
            {"reader": {"path": "/new.svg", "id": "R1", "has_single_image": True}},
            {"reader": {"path": "/old.svg", "id": "R1", "has_single_image": True}},
        )
        unchanged = self.timeline_module.TimelineView._transition_reader_changed(
            helper,
            {"reader": {"path": "/same.svg", "id": "R1", "has_single_image": True}},
            {"reader": {"path": "/same.svg", "id": "R1", "has_single_image": True}},
        )

        self.assertTrue(changed)
        self.assertFalse(unchanged)

    def test_transition_uses_static_mask_prefers_has_single_image_flag(self):
        helper = self.make_helper()

        self.assertTrue(
            self.timeline_module.TimelineView._transition_uses_static_mask(
                helper,
                {"reader": {"has_single_image": True}},
            )
        )
        self.assertFalse(
            self.timeline_module.TimelineView._transition_uses_static_mask(
                helper,
                {"reader": {"has_single_image": False}},
            )
        )

    def test_find_missing_transition_details_returns_overlap(self):
        clip_data = {"id": "B", "layer": 1, "position": 4.0, "start": 0.0, "end": 6.0}
        existing_clip = types.SimpleNamespace(data={"id": "A", "position": 0.0, "start": 0.0, "end": 5.0})

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.timeline_module.Clip, "filter", return_value=[existing_clip])
            )
            stack.enter_context(
                patch.object(self.timeline_module.Transition, "filter", return_value=[])
            )
            details = self.timeline_module.TimelineView._find_missing_transition_details(
                types.SimpleNamespace(),
                clip_data,
            )

        self.assertEqual(
            details,
            {"position": 4.0, "layer": 1, "start": 0.0, "end": 1.0},
        )

    def test_find_missing_transition_details_ignores_existing_transition(self):
        clip_data = {"id": "B", "layer": 1, "position": 4.0, "start": 0.0, "end": 6.0}
        existing_clip = types.SimpleNamespace(data={"id": "A", "position": 0.0, "start": 0.0, "end": 5.0})
        existing_transition = types.SimpleNamespace(data={"position": 4.0, "start": 0.0, "end": 1.0})

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.timeline_module.Clip, "filter", return_value=[existing_clip])
            )
            stack.enter_context(
                patch.object(
                    self.timeline_module.Transition,
                    "filter",
                    return_value=[existing_transition],
                )
            )
            details = self.timeline_module.TimelineView._find_missing_transition_details(
                types.SimpleNamespace(),
                clip_data,
            )

        self.assertIsNone(details)

    def test_should_refresh_waveforms_true_for_clip_payload_with_audio_data(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["clips", {"id": "C1"}],
            values={"ui": {"audio_data": [0.1, 0.2]}},
        )

        self.assertTrue(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_should_refresh_waveforms_checks_existing_clip_audio_when_payload_has_no_samples(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["clips", {"id": "C1"}],
            values={"position": 5.0},
        )
        clip = types.SimpleNamespace(data={"ui": {"audio_data": [0.5]}})

        with patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.assertTrue(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_should_refresh_waveforms_false_for_non_clip_action(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["files", {"id": "F1"}],
            values={"path": "example.mp4"},
        )

        self.assertFalse(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_should_refresh_waveforms_false_when_clip_has_no_audio_data(self):
        helper = self.make_helper()
        action = UpdateAction(
            type="update",
            key=["clips", {"id": "C1"}],
            values={"position": 5.0},
        )
        clip = types.SimpleNamespace(data={"ui": {"audio_data": []}})

        with patch.object(self.timeline_module.Clip, "get", return_value=clip):
            self.assertFalse(self.timeline_module.TimelineView._should_refresh_waveforms(helper, action))

    def test_find_missing_transition_details_ignores_tiny_overlap(self):
        clip_data = {"id": "B", "layer": 1, "position": 4.7, "start": 0.0, "end": 6.0}
        existing_clip = types.SimpleNamespace(data={"id": "A", "position": 0.0, "start": 0.0, "end": 5.0})

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(self.timeline_module.Clip, "filter", return_value=[existing_clip])
            )
            stack.enter_context(
                patch.object(self.timeline_module.Transition, "filter", return_value=[])
            )
            details = self.timeline_module.TimelineView._find_missing_transition_details(
                types.SimpleNamespace(),
                clip_data,
            )

        self.assertIsNone(details)
