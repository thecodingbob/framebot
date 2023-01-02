import re
import shutil
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from framebots import SimpleFrameBot, _remove_last_frame_uploaded_file, LAST_FRAME_UPLOADED_FILE, _get_filename
from model import FacebookFrame
from plugins import FrameBotPlugin
from social import FacebookHelper
from utils_for_tests import FileWritingTestCase

from test import RESOURCES_DIR


class TestStaticMethods(unittest.TestCase):

    @patch("os.path.exists")
    @patch("os.remove")
    def test_remove_last_frame_uploaded_file(self, mock_remove: Mock, mock_exists: Mock):
        # file is there
        mock_exists.return_value = True

        _remove_last_frame_uploaded_file()

        mock_remove.assert_called_once_with(LAST_FRAME_UPLOADED_FILE)
        mock_exists.assert_called_once_with(LAST_FRAME_UPLOADED_FILE)

        mock_exists.reset_mock()
        mock_remove.reset_mock()

        # file is not there
        mock_exists.return_value = False

        _remove_last_frame_uploaded_file()

        mock_remove.assert_not_called()
        mock_exists.assert_called_once_with(LAST_FRAME_UPLOADED_FILE)

    def test_get_filename(self):
        filename = "dummy"
        extension = ".jpg"
        full_filename = f"{filename}{extension}"
        self.assertEqual(filename, _get_filename(filename))
        self.assertEqual(full_filename, _get_filename(full_filename))
        self.assertEqual(filename, _get_filename(
            Path("root").joinpath("exampledir").joinpath(filename)))


class TestSimpleFrameBot(FileWritingTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.mock_helper = Mock(spec=FacebookHelper)
        self.video_title = "Test video title"
        self.testee = SimpleFrameBot(
            facebook_helper=self.mock_helper,
            video_title=self.video_title
        )
        self.mock_plugin = Mock(spec=FrameBotPlugin)

    def _copy_frames_directory(self):
        shutil.copytree(RESOURCES_DIR.joinpath("framebots").joinpath("simple_framebot").joinpath("frames"),
                        self.test_dir.joinpath("frames"))

    def test_init(self):
        self.assertEqual([], self.testee.plugins)

    def test_frames_naming(self):
        with self.assertRaises(ValueError):
            self.testee.frames_naming = "nonsense"

        self.testee.frames_ext = "jpg"
        self.testee.frames_naming = "$N$"
        self.assertEqual(re.compile("^(\\d+)\\.jpg$"), self.testee.frames_naming)

        self.testee.frames_naming = "My cool movie frame $N$ of 123543"
        self.assertEqual(re.compile("^My cool movie frame (\\d+) of 123543\\.jpg$"), self.testee.frames_naming)
        self.assertIsNotNone(self.testee.frames_naming.match("My cool movie frame 000010 of 123543.jpg"))

    def test_init_frames(self):
        # empty frame list
        self.testee._init_frames()
        self.assertEqual(0, len(self.testee.frames))

        # frame list with some frames
        self._copy_frames_directory()
        self.testee._init_frames()

        expected_frames_paths = list(self.test_dir.joinpath("frames").glob("*.jpg"))
        self.assertEqual(len(expected_frames_paths), len(self.testee.frames))
        for i, frame in enumerate(self.testee.frames):
            self.assertEqual(i + 1, frame.number)
            self.assertEqual(expected_frames_paths[i], frame.local_file.absolute())

        # start from later frame
        self.testee.last_frame_uploaded = 5
        self.testee._init_frames()

        self.assertEqual(len(expected_frames_paths) - self.testee.last_frame_uploaded, len(self.testee.frames))
        for i, frame in enumerate(self.testee.frames):
            self.assertEqual(i + self.testee.last_frame_uploaded + 1, frame.number)
            self.assertEqual(expected_frames_paths[i + self.testee.last_frame_uploaded], frame.local_file.absolute())

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="13")
    def test_init_status(self, mock_file: Mock, mock_exists: Mock):
        # no last frame uploaded file
        mock_exists.return_value = False
        self.testee._init_status()
        self.assertEqual(-1, self.testee.last_frame_uploaded)
        mock_file.assert_not_called()
        mock_exists.assert_called_once_with(LAST_FRAME_UPLOADED_FILE)

        # file found
        mock_exists.reset_mock()
        mock_exists.return_value = True
        self.testee._init_status()
        self.assertEqual(13, self.testee.last_frame_uploaded)
        mock_file.assert_called_once_with(LAST_FRAME_UPLOADED_FILE)
        mock_exists.assert_called_once_with(LAST_FRAME_UPLOADED_FILE)

    def test_get_frame_index_number(self):
        self.assertEqual(1, self.testee._get_frame_index_number("1.jpg"))
        self.assertEqual(1, self.testee._get_frame_index_number("001.jpg"))
        self.assertEqual(123, self.testee._get_frame_index_number(Path("example").joinpath("123.jpg")))
        self.assertEqual(123, self.testee._get_frame_index_number(Path("example").joinpath("123.jpg").absolute()))

        complicated_name_string = "I like complicated frame names $N$. Frame number was right before this sentence!"
        self.testee.frames_naming = complicated_name_string

        self.assertEqual(2, self.testee._get_frame_index_number(
            Path("example").joinpath(complicated_name_string.replace("$N$", "0002") + ".jpg")))

    def test_get_default_message(self):
        total_frames_number = 20
        frame_number = 12

        self.testee.total_frames_number = total_frames_number
        message = self.testee._get_default_message(frame_number)
        self.assertEqual(f"{self.video_title}\nFrame {frame_number} of {total_frames_number}", message)

    def test_update_last_frame_uploaded(self):
        test_last_frame_uploaded = 10
        self.testee._update_last_frame_uploaded(test_last_frame_uploaded)

        self.assertEqual(test_last_frame_uploaded, self.testee.last_frame_uploaded)
        test_last_frame_uploaded_path = self.test_dir.joinpath(LAST_FRAME_UPLOADED_FILE)
        self.assertTrue(test_last_frame_uploaded_path.exists())
        with open(test_last_frame_uploaded_path) as f:
            self.assertEqual(str(test_last_frame_uploaded), f.read())

    @patch("framebots._remove_last_frame_uploaded_file")
    def test_start(self, mock_remove: Mock):
        self.testee.plugins.append(self.mock_plugin)
        self.testee._upload_loop = Mock()
        self.testee._remove_last_frame_uploaded_file = Mock()

        self.testee.start()

        self.testee._upload_loop.assert_called_once()
        mock_remove.assert_called_once()
        self.mock_plugin.before_upload_loop.assert_called_once()
        self.mock_plugin.after_upload_loop.assert_called_once()

    @patch("os.remove")
    def test_upload_loop(self, mock_remove: Mock):
        self.testee.plugins.append(self.mock_plugin)
        self.testee._upload_frame = Mock()
        self.testee.upload_interval = timedelta(microseconds=0)
        self._copy_frames_directory()
        self.testee._init_frames()
        frames_number = self.testee.total_frames_number
        self.assertGreater(frames_number, 0)

        self.testee._upload_loop()
        self.assertEqual(frames_number, self.testee._upload_frame.call_count)
        self.assertEqual(frames_number, self.mock_plugin.before_frame_upload.call_count)
        self.assertEqual(frames_number, self.mock_plugin.after_frame_upload.call_count)
        mock_remove.assert_not_called()

        self.testee.delete_files = True
        self.testee.last_frame_uploaded = -1
        self.testee._init_frames()
        self.testee._upload_loop()
        self.assertEqual(frames_number, mock_remove.call_count)

    def test_upload_frame(self):
        test_frame = FacebookFrame(number=1, local_file="dummy.jpg")
        self.testee._upload_frame(test_frame)

        self.assertEqual(self.testee._get_default_message(test_frame.number), test_frame.text)
        self.assertIsNotNone(test_frame.post_id)
        self.assertIsNotNone(test_frame.url)
        self.assertEqual(test_frame.number, self.testee.last_frame_uploaded)
        self.mock_helper.upload_photo.assert_called_once_with(test_frame.local_file, test_frame.text)


if __name__ == '__main__':
    unittest.main()
