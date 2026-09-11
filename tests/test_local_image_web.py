import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class LocalImageWebTest(unittest.TestCase):
    def test_local_upload_page_has_simple_form(self):
        from examples.local_image_upload_server import build_page, save_uploaded_file

        page = build_page()
        self.assertIn('type="file"', page)
        self.assertIn('accept="image/', page)
        self.assertIn('upload', page.lower())
        self.assertIn('id="stopBtn"', page)
        self.assertIn('id="inputPreview"', page)
        self.assertIn('id="svgPreview"', page)
        self.assertTrue(callable(save_uploaded_file))


if __name__ == '__main__':
    unittest.main()
