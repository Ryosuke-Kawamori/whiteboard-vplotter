import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples.image_to_svg import (
    estimate_plot_time,
    format_plot_estimate,
    raster_to_strokes,
    to_machine,
    write_svg_from_image,
)
from examples.plot_area_limits import limit_strokes


class ImageToSvgExampleTest(unittest.TestCase):
    def test_plot_estimate_includes_draw_move_and_servo_time(self):
        strokes = [[(950.0, 650.0), (968.0, 650.0)]]

        draw_length, move_length, seconds = estimate_plot_time(strokes)

        self.assertEqual(18.0, draw_length)
        self.assertEqual(18.0, move_length)
        self.assertGreater(seconds, draw_length / 18.0 + move_length / 35.0)
        self.assertIn('約 ', format_plot_estimate(strokes))

    def test_limit_stroke_matches_configured_drawable_area(self):
        stroke = limit_strokes()[0]

        self.assertEqual((250.0, 200.0), stroke[0])
        self.assertEqual((1650.0, 920.0), stroke[2])
        self.assertEqual(stroke[0], stroke[-1])

    def test_to_machine_preserves_image_aspect_ratio(self):
        strokes = [[(0.0, 0.0), (1.0, 1.0)]]

        machine = to_machine(
            strokes, size=200.0, cx=500.0, y_bottom=600.0,
            image_aspect=2.0,
        )

        self.assertEqual((400.0, 500.0), machine[0][0])
        self.assertEqual((600.0, 600.0), machine[0][1])

    def test_raster_to_strokes_and_svg_output(self):
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / 'sample.png'
            img = Image.new('L', (40, 30), 255)
            for x in range(10, 25):
                for y in range(8, 22):
                    img.putpixel((x, y), 0)
            img.save(image_path)

            strokes = raster_to_strokes(image_path, target_width=40, threshold=200)
            self.assertEqual(1, len(strokes))
            self.assertEqual(strokes[0][0], strokes[0][-1])
            self.assertEqual(5, len(strokes[0]))
            detailed = raster_to_strokes(
                image_path, target_width=40, threshold=200, simplify=0
            )
            self.assertGreater(len(detailed[0]), len(strokes[0]))

            svg_path = Path(td) / 'sample.svg'
            write_svg_from_image(image_path, svg_path, target_width=40, threshold=200)
            self.assertTrue(svg_path.exists())
            text = svg_path.read_text(encoding='utf-8')
            self.assertIn('<svg', text)
            self.assertIn('stroke', text)
            self.assertIn('Whiteboard 1800 x 900 mm', text)
            self.assertIn('Drawable X 250..1650 / Y 200..920 mm', text)
            self.assertIn('M 905.0000,796.0000', text)
            self.assertIn('L 905.0000,796.0000', text)


if __name__ == '__main__':
    unittest.main()
