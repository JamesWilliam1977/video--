"""
@file
@brief Unit tests for thumbnail generation fallback behavior.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import classes.thumbnail as thumbnail


class _Frame:
    def __init__(self):
        self.calls = []

    def Thumbnail(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class _Reader:
    def __init__(self, *, open_error=None, metadata=None):
        self.open_error = open_error
        self.open_calls = 0
        self.close_calls = 0
        self.decode_sizes = []
        self.max_frames = []
        self.metadata = metadata or {}

        class _Metadata(dict):
            def count(self, key):
                return 1 if key in self else 0

        self.info = SimpleNamespace(metadata=_Metadata(self.metadata))
        self._frame = _Frame()

    def SetMaxDecodeSize(self, width, height):
        self.decode_sizes.append((width, height))

    def Open(self):
        self.open_calls += 1
        if self.open_error:
            raise self.open_error

    def GetFrame(self, _):
        self.max_frames.append(_)
        return self._frame

    def Close(self):
        self.close_calls += 1


class ThumbnailGenerationTests(unittest.TestCase):
    def test_generate_thumbnail_retries_when_first_reader_fails_to_open(self):
        first_reader = _Reader(open_error=RuntimeError("QtImageReader could not open image file."))
        second_reader = _Reader()
        created = []
        reader_iter = iter([first_reader, second_reader])

        def create_reader(path, inspect_reader):
            created.append((path, inspect_reader))
            return next(reader_iter)

        with patch.object(thumbnail.openshot.Clip, "CreateReader", side_effect=create_reader), \
             patch.object(thumbnail.os.path, "exists", side_effect=lambda path: True), \
             patch.object(thumbnail.shutil, "copyfile") as copyfile_patch:
            thumbnail.GenerateThumbnail("image.webp", "/tmp/thumb.png", 1, 20, 20, None, None)

        self.assertEqual(created, [("image.webp", False), ("image.webp", True)])
        self.assertEqual(first_reader.open_calls, 1)
        self.assertEqual(second_reader.open_calls, 1)
        self.assertEqual(second_reader.decode_sizes, [(60, 60)])
        self.assertEqual(second_reader.max_frames, [1])
        self.assertEqual(first_reader.close_calls, 1)
        self.assertEqual(second_reader.close_calls, 1)
        copyfile_patch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
