import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples.image_to_svg import raster_to_strokes, write_svg_from_image


class ImageToSvgExampleTest(unittest.TestCase):
    def test_raster_to_strokes_and_svg_output(self):
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / 'sample.png'
            img = Image.new('L', (40, 30), 255)
            for x in range(10, 25):
                for y in range(8, 22):
                    img.putpixel((x, y), 0)
            img.save(image_path)

            strokes = raster_to_strokes(image_path, target_width=40, threshold=200)
            self.assertTrue(strokes)
            dense_strokes = raster_to_strokes(image_path, target_width=40, threshold=200, line_step=1)
            self.assertLess(len(strokes), len(dense_strokes))

            svg_path = Path(td) / 'sample.svg'
            write_svg_from_image(image_path, svg_path, target_width=40, threshold=200)
            self.assertTrue(svg_path.exists())
            text = svg_path.read_text(encoding='utf-8')
            self.assertIn('<svg', text)
            self.assertIn('stroke', text)
            self.assertIn('M 10.0000,8.0000', text)


if __name__ == '__main__':
    unittest.main()
