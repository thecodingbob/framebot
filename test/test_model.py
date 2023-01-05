import datetime
import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from framebot.model import RemoteValue, FacebookReactionsTotal, FacebookFrame
from framebot.social import FacebookPostPhotoResponse


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


class TestFacebookReactionsTotal(unittest.TestCase):

    def test_value(self):
        mock_helper = MagicMock()
        post_id = "post_id"
        fake_reactions_total = 1000
        mock_helper.get_reactions_total_count = MagicMock(return_value=fake_reactions_total)
        testee = FacebookReactionsTotal(post_id=post_id, facebook_helper=mock_helper)
        self.assertEqual(fake_reactions_total, testee.value)
        mock_helper.get_reactions_total_count.assert_called_once_with(post_id)


class TestFacebookFrame(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_helper = MagicMock()
        self.testee = FacebookFrame(local_file="dummy.jpg", number=1)

    def test_story_id(self):
        self.assertIsNone(self.testee.post_id)

    def test_reactions_total(self):
        self.assertIsNone(self.testee.reactions_total)

    @patch("framebot.model.FacebookReactionsTotal.value", new_callable=PropertyMock)
    def test_mark_as_posted(self, mock_reactions_total):
        mock_reactions_total.return_value = 12
        fake_api_response = FacebookPostPhotoResponse("id", "post_id")

        self.testee.mark_as_posted(fake_api_response, facebook_helper=self.mock_helper)

        self.assertEqual(fake_api_response.photo_id, self.testee.photo_id)
        self.assertEqual(fake_api_response.post_id, self.testee.post_id)
        self.assertEqual(f"https://facebook.com/{fake_api_response.photo_id}", self.testee.url)
        self.assertTrue((datetime.datetime.now() - self.testee.post_time) < datetime.timedelta(seconds=1))
        self.assertEqual(mock_reactions_total.return_value, self.testee.reactions_total)

        self.assertRaises(ValueError, self.testee.mark_as_posted, None, None)


if __name__ == '__main__':
    unittest.main()
