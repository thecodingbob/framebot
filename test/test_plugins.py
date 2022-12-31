import datetime
import shutil
import unittest
import os
import slugify
from datetime import timedelta, datetime
from pathlib import Path
from unittest.mock import Mock, patch, DEFAULT

from facebook import GraphAPIError

import utils
from model import FacebookFrame, FacebookReactionsTotal, FacebookStoryId
from plugins import FrameBotPlugin, BestOfReposter
from social import FacebookHelper
from test import RESOURCES_DIR
from utils_for_tests import FileWritingTestCase


class TestFrameBotPlugin(FileWritingTestCase):

    def test_init(self):
        os.chdir(self.test_dir)
        plugins_directory = Path(self.test_dir).joinpath("plugins")
        plugin_directory = plugins_directory.joinpath(FrameBotPlugin.__name__)
        self.assertFalse(plugin_directory.exists())
        FrameBotPlugin()
        self.assertTrue(plugin_directory.exists())

        plugin_directory = plugins_directory.joinpath("my_custom_name")
        self.assertFalse(plugin_directory.exists())
        FrameBotPlugin(local_directory=plugin_directory)
        self.assertTrue(plugin_directory.exists())


class TestBestOfReposter(FileWritingTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.facebook_helper = Mock(spec=FacebookHelper)
        self.video_title = "test"
        self.test_bofc_path = RESOURCES_DIR.joinpath("plugins").joinpath("best_of_reposter").joinpath("bofc.json")
        self.test_frames = utils.load_obj_from_json_file(self.test_bofc_path)
        self.testee = BestOfReposter(facebook_helper=self.facebook_helper, album_id="album_id",
                                     video_title=self.video_title)
        self.test_frame = FacebookFrame(number=1, local_file="dummy.jpg")
        self.test_frame._post_time = datetime.now()
        self.test_frame._url = "https://example.com"
        self.test_frame.text = "Test Frame"

    def test_defaults(self):
        default_reactions_threshold = 50
        default_time_threshold = timedelta(days=1)
        default_yet_to_check_file = "bofc.json"
        default_store_best_ofs = True

        plugin_dir = Path(self.test_dir).joinpath("plugins").joinpath(self.testee.__class__.__name__) \
            .joinpath(slugify.slugify(f"Best Of {self.video_title}"))
        album_dir = plugin_dir.joinpath("album")
        frames_dir = plugin_dir.joinpath("frames_to_check")

        self.assertTrue(album_dir.exists())
        self.assertTrue(frames_dir.exists())

        self.assertEqual(default_reactions_threshold, self.testee.reactions_threshold)
        self.assertEqual(default_time_threshold, self.testee.time_threshold)
        self.assertEqual(plugin_dir.joinpath(default_yet_to_check_file), self.testee.yet_to_check_file.absolute())
        self.assertEqual(default_store_best_ofs, self.testee.store_best_ofs)

    def test_check_for_existing_status(self):
        # asserting no exceptions are raised
        self.testee._check_for_existing_status()

        # asserting correct loading
        shutil.copy(self.test_bofc_path, self.testee.yet_to_check_file)
        self.testee._check_for_existing_status()
        self.assertEqual(self.test_frames, self.testee.yet_to_check)
        self.assertTrue(all(self.testee.yet_to_check[i].post_time < self.testee.yet_to_check[i + 1].post_time
                            for i in range(len(self.testee.yet_to_check) - 1)))

    @patch("shutil.copyfile")
    @patch("os.remove")
    def test_check_and_post(self, mock_remove: Mock, mock_copyfile: Mock):
        # too early
        self.testee.time_threshold = timedelta(days=1)
        self.assertFalse(self.testee._check_and_post(self.test_frame))

        exists_method = "os.path.exists"
        # not enough reactions
        with patch(exists_method, return_value=True) as mock_exists:
            self.test_frame._reactions_total = FacebookReactionsTotal(
                story_id=Mock(spec=FacebookStoryId), facebook_helper=Mock(spec=FacebookHelper))
            self.test_frame._reactions_total._value = 99
            self.test_frame._post_time = datetime.now() - timedelta(days=2)
            self.testee.reactions_threshold = 100

            self.assertTrue(self.testee._check_and_post(self.test_frame))
            mock_remove.assert_called_once_with(self.test_frame.local_file)
            self.assertFalse(self.facebook_helper.upload_photo.called)
            self.assertFalse(mock_copyfile.called)
            mock_exists.assert_called_once_with(self.test_frame.local_file)

            # best of eligible
            self.testee.reactions_threshold = 98
            mock_remove.reset_mock()
            mock_exists.reset_mock()

            self.assertTrue(self.testee._check_and_post(self.test_frame))
            mock_remove.assert_called_once_with(self.test_frame.local_file)
            self.assertTrue(self.facebook_helper.upload_photo.called)
            mock_copyfile.assert_called_once_with(self.test_frame.local_file,
                                                  os.path.join(self.testee.album_path,
                                                               f"Frame {self.test_frame.number} "
                                                               f"id {self.test_frame.story_id} "
                                                               f"reactions {self.test_frame.reactions_total}"))
            mock_exists.assert_called_once_with(self.test_frame.local_file)

        # missing file
        with patch(exists_method, return_value=False) as mock_exists:
            self.assertTrue(self.testee._check_and_post(self.test_frame))
            mock_exists.assert_called_once_with(self.test_frame.local_file)

    @patch("utils.safe_json_dump")
    def test_advance_bests(self, mock_json_dump: Mock):
        self.testee.yet_to_check = self.test_frames
        mock_check_and_post = Mock()
        self.testee._check_and_post = mock_check_and_post
        mock_check_and_post.side_effect = [True, True, False]

        self.testee._advance_bests()
        self.assertEqual(1, len(self.testee.yet_to_check))
        self.assertEqual(2, mock_json_dump.call_count)
        self.assertEqual(3, mock_check_and_post.call_count)

        mock_check_and_post.reset_mock()
        mock_json_dump.reset_mock()

        # GraphAPIError raised
        mock_check_and_post.side_effect = GraphAPIError("fake error")
        expected_len = len(self.testee.yet_to_check)

        self.testee._advance_bests()
        mock_json_dump.assert_not_called()
        mock_check_and_post.assert_called_once()
        self.assertEqual(expected_len, len(self.testee.yet_to_check))

        mock_check_and_post.reset_mock()
        mock_json_dump.reset_mock()

        # last element checked
        mock_check_and_post.return_value = True
        mock_check_and_post.side_effect = [DEFAULT]
        self.testee._advance_bests()
        self.assertEqual(0, len(self.testee.yet_to_check))
        self.assertEqual(1, mock_json_dump.call_count)
        self.assertEqual(1, mock_check_and_post.call_count)

        mock_check_and_post.reset_mock()
        mock_json_dump.reset_mock()

        # nothing to check
        self.testee.yet_to_check = []
        self.testee._advance_bests()
        mock_check_and_post.assert_not_called()
        mock_json_dump.assert_not_called()

    @patch("utils.safe_json_dump")
    @patch("shutil.copyfile")
    def test_queue_for_frame_check(self, mock_copyfile: Mock, mock_json_dump: Mock):
        self.testee._queue_frame_for_check(self.test_frame)
        self.assertTrue(1, len(self.testee.yet_to_check))
        queued_frame = self.testee.yet_to_check[0]
        self.assertNotEqual(self.test_frame, queued_frame)
        new_frame_path = self.testee.frames_dir.joinpath(self.test_frame.local_file.name)
        self.assertEqual(new_frame_path, queued_frame.local_file)
        mock_copyfile.assert_called_once_with(self.test_frame.local_file, new_frame_path)
        mock_json_dump.assert_called_once_with(self.testee.yet_to_check_file, self.testee.yet_to_check)

    @patch("time.sleep")
    def test_handle_quicker(self, mock_sleep: Mock):
        def mock_advance_bests_behavior():
            # first call
            if len(self.testee.yet_to_check) == 3:
                self.testee.yet_to_check.pop(0)
                self.testee.yet_to_check.pop(1)
            # second call
            else:
                self.testee.yet_to_check.pop(0)
        og_threshold = self.testee.time_threshold
        self.testee.yet_to_check = self.test_frames
        mock_advance_bests = Mock(side_effect=mock_advance_bests_behavior)
        self.testee._advance_bests = mock_advance_bests

        self.testee._handle_quicker()

        self.assertEqual(og_threshold // 2, self.testee.time_threshold)
        self.assertEqual(0, len(self.testee.yet_to_check))
        self.assertEqual(2, mock_advance_bests.call_count)
        self.assertEqual(1, mock_sleep.call_count)


if __name__ == '__main__':
    unittest.main()
