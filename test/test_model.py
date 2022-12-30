import datetime
import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from model import RemoteValue, FacebookStoryId, FacebookReactionsTotal, FacebookFrame


class TestRemoteValue(unittest.TestCase):

    def setUp(self) -> None:
        self.refresher = Mock()
        self.value = 1
        self.refresher.return_value = self.value
        self.testee: RemoteValue[int] = RemoteValue[int](self.refresher)

    def test_value(self):
        self.assertEqual(self.value, self.testee.value)
        self.assertEqual(self.value, self.testee.value)
        self.refresher.assert_called_once()

    def test_refresh(self):
        self.testee.refresh()
        self.assertTrue((datetime.datetime.now() - self.testee.last_updated) < datetime.timedelta(seconds=1))
        self.refresher.assert_called_once()
        self.testee.refresh()
        self.assertTrue(2, self.refresher.call_count)

    def test_last_updated(self):
        self.assertIsNone(self.testee.last_updated)
        self.testee.refresh()
        self.assertIsNotNone(self.testee.last_updated)


class TestFacebookStoryId(unittest.TestCase):

    def test_value(self):
        mock_helper = MagicMock()
        fake_post_id = "id"
        fake_story_id = "story_id"
        mock_helper.get_story_id = MagicMock(return_value=fake_story_id)
        testee = FacebookStoryId(post_id=fake_post_id, facebook_helper=mock_helper)
        self.assertEqual(fake_story_id, testee.value)
        mock_helper.get_story_id.assert_called_once_with(fake_post_id)


class TestFacebookReactionsTotal(unittest.TestCase):

    def test_value(self):
        mock_helper = MagicMock()
        mock_story_id = MagicMock()
        mock_story_id.value = "story_id"
        fake_reactions_total = 1000
        mock_helper.get_reactions_total_count = MagicMock(return_value=fake_reactions_total)
        testee = FacebookReactionsTotal(story_id=mock_story_id, facebook_helper=mock_helper)
        self.assertEqual(fake_reactions_total, testee.value)
        mock_helper.get_reactions_total_count.assert_called_once_with(mock_story_id.value)


class TestFacebookFrame(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_helper = MagicMock()
        self.testee = FacebookFrame(local_file="dummy.jpg", number=1)

    def test_story_id(self):
        self.assertIsNone(self.testee.story_id)

    def test_reactions_total(self):
        self.assertIsNone(self.testee.reactions_total)

    @patch("model.FacebookStoryId.value", new_callable=PropertyMock)
    @patch("model.FacebookReactionsTotal.value", new_callable=PropertyMock)
    def test_mark_as_posted(self, mock_reactions_total, mock_story_id):
        mock_reactions_total.return_value = 12
        mock_story_id.return_value = "story_id"
        post_id = "id"

        self.testee.mark_as_posted(post_id, facebook_helper=self.mock_helper)

        self.assertEqual(post_id, self.testee.post_id)
        self.assertEqual(mock_story_id.return_value, self.testee.story_id)
        self.assertEqual(f"https://facebook.com/{post_id}", self.testee.url)
        self.assertTrue((datetime.datetime.now() - self.testee.post_time) < datetime.timedelta(seconds=1))
        self.assertEqual(mock_reactions_total.return_value, self.testee.reactions_total)

        self.assertRaises(ValueError, self.testee.mark_as_posted, None)


if __name__ == '__main__':
    unittest.main()
