import os
import shutil
import tempfile
import unittest


class FileWritingTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

    def tearDown(self) -> None:
        if os.getcwd() == self.test_dir:
            os.chdir("/")
        shutil.rmtree(self.test_dir)


