import datetime
import shutil
import unittest
import os
import slugify
from datetime import timedelta, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import utils
from model import FacebookFrame, FacebookReactionsTotal
from plugins import FrameBotPlugin, BestOfReposter
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
        self.facebook_helper = Mock()
        self.video_title = "test"
        self.test_bofc_path = RESOURCES_DIR.joinpath("plugins").joinpath("best_of_reposter").joinpath("bofc.json")
        self.test_frames = utils.load_obj_from_json_file(self.test_bofc_path)
        self.testee = BestOfReposter(facebook_helper=self.facebook_helper, album_id="album_id",
                                     video_title=self.video_title)

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
        test_frame = FacebookFrame(number=1, local_file="dummy.jpg")
        test_frame._post_time = datetime.now()
        test_frame._url = "https://example.com"
        test_frame.text = "Test Frame"
        self.testee.time_threshold = timedelta(days=1)
        self.assertFalse(self.testee._check_and_post(test_frame))

        # not enough reactions
        test_frame._reactions_total = FacebookReactionsTotal(story_id=Mock(), facebook_helper=Mock())
        test_frame._reactions_total._value = 99
        test_frame._post_time = datetime.now() - timedelta(days=2)
        self.testee.reactions_threshold = 100

        self.assertTrue(self.testee._check_and_post(test_frame))
        mock_remove.assert_called_once_with(test_frame.local_file)
        self.assertFalse(self.facebook_helper.upload_photo.called)
        self.assertFalse(mock_copyfile.called)

        # best of eligible
        self.testee.reactions_threshold = 98
        mock_remove.reset_mock()

        self.assertTrue(self.testee._check_and_post(test_frame))
        mock_remove.assert_called_once_with(test_frame.local_file)
        self.assertTrue(self.facebook_helper.upload_photo.called)
        self.assertTrue(mock_copyfile.called)


if __name__ == '__main__':
    unittest.main()
