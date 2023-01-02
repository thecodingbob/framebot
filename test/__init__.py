from pathlib import Path

from model import FacebookFrame

RESOURCES_DIR: Path = Path("resources").absolute()


def generate_test_frame() -> FacebookFrame:
    test_frame = FacebookFrame(number=1, local_file=RESOURCES_DIR.joinpath("dummy.jpg"))
    test_frame.text = "This is a test frame. \nIt has no purpose outside of the tests."
    return test_frame
