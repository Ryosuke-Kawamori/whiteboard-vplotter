import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class LocalImageWebTest(unittest.TestCase):
    def test_text_can_be_placed_at_requested_center(self):
        from examples.local_image_upload_server import text_machine_strokes

        strokes = text_machine_strokes('今週の目標\n安全第一', size=100, x=950, y=500)
        xs = [x for stroke in strokes for x, _ in stroke]
        ys = [y for stroke in strokes for _, y in stroke]

        self.assertAlmostEqual(950, (min(xs) + max(xs)) / 2)
        self.assertAlmostEqual(500, (min(ys) + max(ys)) / 2)

    def test_multiple_text_boxes_are_combined(self):
        from examples.local_image_upload_server import text_boxes_machine_strokes

        strokes = text_boxes_machine_strokes(
            '[{"text":"左", "size":60, "x":400, "y":350},'
            '{"text":"右", "size":80, "x":1400, "y":700}]'
        )
        xs = [x for stroke in strokes for x, _ in stroke]
        ys = [y for stroke in strokes for _, y in stroke]

        self.assertLess(min(xs), 400)
        self.assertGreater(max(xs), 1400)
        self.assertLess(min(ys), 350)
        self.assertGreater(max(ys), 700)

    def test_local_upload_page_has_simple_form(self):
        from examples.local_image_upload_server import (
            build_page,
            resolve_uploaded_image,
            save_uploaded_file,
        )

        page = build_page()
        self.assertIn('type="file"', page)
        self.assertIn('accept="image/', page)
        self.assertIn('upload', page.lower())
        self.assertIn('id="stopBtn"', page)
        self.assertNotIn('id="inputPreview"', page)
        self.assertIn('id="svgPreview"', page)
        self.assertIn('id="source"', page)
        self.assertNotIn('accept="image/*" required', page)
        self.assertIn('type="range"', page)
        self.assertIn("fetch('/preview?'", page)
        self.assertIn("layer.addEventListener('pointermove'", page)
        self.assertIn('id="imageMode"', page)
        self.assertIn('id="textMode"', page)
        self.assertIn('id="text"', page)
        self.assertIn('id="boxes"', page)
        self.assertIn('id="addText"', page)
        self.assertIn('id="sizeNumber"', page)
        self.assertIn("item.className = 'text-box'", page)
        self.assertIn('name="mode"', page)
        self.assertIn('選択中の文字の高さ', page)
        self.assertIn('boxes:boxesInput.value', page)
        self.assertIn('min="250" max="1650" value="950"', page)
        self.assertIn('min="200" max="920" value="560"', page)
        from examples.local_image_upload_server import format_plot_estimate
        self.assertTrue(callable(format_plot_estimate))
        self.assertTrue(callable(save_uploaded_file))
        self.assertTrue(callable(resolve_uploaded_image))

    def test_uploaded_image_can_be_reused_without_uploading_again(self):
        from examples import local_image_upload_server as server

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(server, 'UPLOAD_DIR', Path(temp_dir)):
                saved = server.save_uploaded_file('sample.png', b'image-data')
                reused = server.resolve_uploaded_image(
                    {'source': saved.name}, 'upload.png', None
                )

        self.assertEqual(saved, reused)


if __name__ == '__main__':
    unittest.main()
