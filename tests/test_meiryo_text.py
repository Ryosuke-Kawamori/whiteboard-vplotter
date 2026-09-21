import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from examples.meiryo_text import (
    AREA_X_MAX,
    AREA_X_MIN,
    AREA_Y_MAX,
    AREA_Y_MIN,
    center_strokes,
    draw,
    terminal_preview,
    text_to_strokes,
)


class MeiryoTextPlacementTest(unittest.TestCase):
    def test_default_position_is_centered(self):
        strokes = [[(10.0, 20.0), (110.0, 70.0)]]

        centered = center_strokes(strokes)

        xs = [x for stroke in centered for x, _ in stroke]
        ys = [y for stroke in centered for _, y in stroke]
        self.assertAlmostEqual((AREA_X_MIN + AREA_X_MAX) / 2,
                               (min(xs) + max(xs)) / 2)
        self.assertAlmostEqual((AREA_Y_MIN + AREA_Y_MAX) / 2,
                               (min(ys) + max(ys)) / 2)

    def test_explicit_position_sets_visible_top_left(self):
        strokes = [[(10.0, 20.0), (110.0, 70.0)]]

        positioned = center_strokes(strokes, x=400.0, y=500.0)

        self.assertEqual((400.0, 500.0), positioned[0][0])

    def test_terminal_preview_renders_strokes(self):
        preview = terminal_preview([[(0.0, 0.0), (10.0, 0.0)]],
                                   max_width=10, max_height=5)

        self.assertIn('##########', preview)

    def test_debug_pen_prints_transitions(self):
        output = StringIO()

        with redirect_stdout(output):
            draw([[(500.0, 500.0), (510.0, 500.0)]],
                 dry=True, debug_pen=True)

        self.assertIn('PenUp', output.getvalue())
        self.assertIn('PenDown', output.getvalue())
        self.assertIn('Draw', output.getvalue())

    def test_text_uses_closed_outline_strokes(self):
        font_path = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
        if not font_path.exists():
            self.skipTest('Noto Sans CJK JP is not installed')

        strokes = text_to_strokes('お', font_path, 90.0, 0.0, 0.0)

        self.assertLess(len(strokes), 10)
        self.assertTrue(all(
            abs(stroke[0][0] - stroke[-1][0]) < 0.01
            and abs(stroke[0][1] - stroke[-1][1]) < 0.01
            for stroke in strokes
        ))


if __name__ == '__main__':
    unittest.main()