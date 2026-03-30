import os
import sys
import types
import unittest
from unittest.mock import patch

from PyQt5.QtCore import QRect, QSize
from PyQt5.QtWidgets import QApplication


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_test_app import ensure_app_state, get_or_create_app


class DummySettings:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key, False)

    def set(self, key, value):
        self.values[key] = value


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()


app, _owns_app = get_or_create_app(DummyApp)
ensure_app_state(app, DummySettings, extra_attrs={"window": types.SimpleNamespace()})

from windows.cutting import Cutting
from windows.region import SelectRegion


class DummySignal:
    def __init__(self):
        self.calls = 0

    def emit(self, *args):
        self.calls += 1


class DummyVideoPreview:
    def __init__(self, viewport):
        self._viewport = viewport

    def centeredViewport(self, width, height):
        _ = (width, height)
        return self._viewport

    def width(self):
        return self._viewport.width()

    def height(self):
        return self._viewport.height()


class DialogPreviewResizeTests(unittest.TestCase):
    def test_cutting_select_reader_data_uses_proxy_when_target_fits(self):
        proxy = {"path": "/proxy.mp4", "width": 1280, "height": 720}
        source = {"path": "/source.mp4", "width": 3840, "height": 2160}
        fake = types.SimpleNamespace(
            proxy_reader_data=proxy,
            source_reader_data=source,
            _reader_capacity=lambda data: Cutting._reader_capacity(None, data),
        )

        reader_data = Cutting._select_reader_data_for_size(fake, QSize(960, 540))

        self.assertEqual(reader_data, proxy)

    def test_cutting_select_reader_data_promotes_to_source_when_proxy_too_small(self):
        proxy = {"path": "/proxy.mp4", "width": 1280, "height": 720}
        source = {"path": "/source.mp4", "width": 3840, "height": 2160}
        fake = types.SimpleNamespace(
            proxy_reader_data=proxy,
            source_reader_data=source,
            _reader_capacity=lambda data: Cutting._reader_capacity(None, data),
        )

        reader_data = Cutting._select_reader_data_for_size(fake, QSize(1920, 1080))

        self.assertEqual(reader_data, proxy)

    def test_cutting_target_preview_max_size_caps_to_reader_resolution(self):
        fake = types.SimpleNamespace(
            videoPreview=DummyVideoPreview(QRect(0, 0, 2400, 1350)),
            devicePixelRatioF=lambda: 1.0,
            width=1280,
            height=720,
        )

        size = Cutting._target_preview_max_size(fake)

        self.assertEqual(size, QSize(1280, 720))

    def test_region_target_preview_max_size_scales_with_viewport(self):
        fake = types.SimpleNamespace(
            videoPreview=DummyVideoPreview(QRect(0, 0, 900, 500)),
            devicePixelRatioF=lambda: 1.0,
            width=1920,
            height=1080,
        )

        size = SelectRegion._target_preview_max_size(fake)

        self.assertEqual(size, QSize(900, 500))

    def test_cutting_apply_dynamic_preview_max_size_refreshes_when_size_changes(self):
        calls = []
        timeline = types.SimpleNamespace(
            preview_width=320,
            preview_height=180,
            SetMaxSize=lambda w, h: calls.append(("set", w, h)),
            ClearAllCache=lambda deep: calls.append(("clear", deep)),
        )
        fake = types.SimpleNamespace(
            initialized=True,
            r=timeline,
            _target_preview_max_size=lambda: QSize(640, 360),
            _select_reader_data_for_size=lambda size: {"path": "/source.mp4"},
            reader_data={"path": "/source.mp4"},
            PauseSignal=DummySignal(),
            refreshFrameSignal=DummySignal(),
        )

        Cutting._apply_dynamic_preview_max_size(fake)

        self.assertEqual(fake.PauseSignal.calls, 1)
        self.assertEqual(fake.refreshFrameSignal.calls, 1)
        self.assertEqual(calls, [("set", 640, 360), ("clear", True)])

    def test_cutting_build_preview_timeline_uses_source_dimensions(self):
        timeline_args = []
        timeline_setmax = []

        class FakeTimeline:
            def __init__(self, width, height, fps, sample_rate, channels, channel_layout):
                timeline_args.append((width, height, fps, sample_rate, channels, channel_layout))
                self.info = types.SimpleNamespace()

            def SetMaxSize(self, width, height):
                timeline_setmax.append((width, height))

            def AddClip(self, clip):
                self.clip = clip

            def Open(self):
                pass

        class FakeClipReaderInfo:
            has_video = True
            has_audio = False

        class FakeClipReader:
            info = FakeClipReaderInfo()

        class FakeClip:
            def __init__(self, path):
                self.path = path
                self.reader = FakeClipReader()
                self.display = None

            def SetJson(self, payload):
                self.payload = payload

            def Start(self, value):
                self.start = value

            def End(self, value):
                self.end = value

            def Reader(self):
                return self.reader

        fake = types.SimpleNamespace(
            width=3840,
            height=2160,
            fps_num=30,
            fps_den=1,
            sample_rate=48000,
            channels=2,
            channel_layout=3,
            file=types.SimpleNamespace(absolute_path=lambda: "/source.mp4", data={"start": 0.0, "duration": 5.0}),
            video_length=150,
            source_reader_data={"path": "/source.mp4"},
            proxy_reader_data={"path": ""},
        )

        with patch("windows.cutting.openshot.Timeline", FakeTimeline), \
             patch("windows.cutting.openshot.Clip", FakeClip), \
             patch("windows.cutting.openshot.Fraction", side_effect=lambda num, den: (num, den)), \
             patch("windows.cutting.openshot.FRAME_DISPLAY_CLIP", 7):
            Cutting._build_preview_timeline(fake, {"path": "/source.mp4"}, QSize(640, 360))

        self.assertEqual(timeline_args[0][0:2], (3840, 2160))
        self.assertEqual(timeline_setmax, [(640, 360)])


if __name__ == "__main__":
    unittest.main()
