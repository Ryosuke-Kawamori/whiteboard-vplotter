#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
コマンドラインで受け取った文字列を Meiryo で描画する。

使い方:
  python3 examples/meiryo_text.py "こんにちは" --dry --svg preview.svg
  python3 examples/meiryo_text.py "会議 10:00" --size 90
  python3 examples/meiryo_text.py "明朝" --font /path/to/meiryo.ttc --dry

Meiryo は同梱していない。システムへインストールするか --font で meiryo.ttc
または meiryo.ttf を指定すること。
"""

import argparse
import math
import subprocess
import sys
from pathlib import Path

import freetype

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / 'firmware'))

from vplotter import (
    AREA_X_MAX,
    AREA_X_MIN,
    AREA_Y_MAX,
    AREA_Y_MIN,
    DummyIO,
    HOME_X,
    HOME_Y,
    LgpioIO,
    Plotter,
    write_svg,
)


MEIRYO_PATHS = (
    Path('/usr/share/fonts/truetype/msttcorefonts/meiryo.ttc'),
    Path('/usr/local/share/fonts/meiryo.ttc'),
    Path.home() / '.local/share/fonts/meiryo.ttc',
    Path('/mnt/c/Windows/Fonts/meiryo.ttc'),
    Path('/mnt/c/Windows/Fonts/meiryob.ttc'),
)


def find_meiryo(font_path=None):
    """Meiryo の実ファイルを返す。fontconfig の別フォントへの代替は拒否する。"""
    if font_path:
        path = Path(font_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f'フォントが見つかりません: {path}')
        return path

    for path in MEIRYO_PATHS:
        if path.is_file():
            return path

    try:
        result = subprocess.run(
            ['fc-match', '-f', '%{family}\n%{file}\n', 'Meiryo'],
            check=True,
            capture_output=True,
            text=True,
        )
        family, filename, *_ = result.stdout.splitlines()
        path = Path(filename)
        if 'meiryo' in family.lower() and path.is_file():
            return path
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        pass

    raise FileNotFoundError(
        'Meiryo が見つかりません。Meiryo をインストールするか '
        '--font /path/to/meiryo.ttc を指定してください。'
    )


class OutlineCollector:
    """FreeTypeのベジェ輪郭を直線点列へ変換する。"""

    def __init__(self, offset_x, baseline_y, curve_step):
        self.offset_x = offset_x
        self.baseline_y = baseline_y
        self.curve_step = curve_step
        self.strokes = []
        self.current = None

    def _point(self, point):
        return (self.offset_x + point.x / 64.0,
                self.baseline_y - point.y / 64.0)

    def move_to(self, point, _context):
        self.current = self._point(point)
        self.strokes.append([self.current])

    def line_to(self, point, _context):
        self.current = self._point(point)
        self.strokes[-1].append(self.current)

    def conic_to(self, control, end, _context):
        start = self.current
        control = self._point(control)
        end = self._point(end)
        length = math.dist(start, control) + math.dist(control, end)
        steps = max(2, math.ceil(length / self.curve_step))
        for index in range(1, steps + 1):
            ratio = index / steps
            inverse = 1.0 - ratio
            self.strokes[-1].append((
                inverse * inverse * start[0] + 2 * inverse * ratio * control[0]
                + ratio * ratio * end[0],
                inverse * inverse * start[1] + 2 * inverse * ratio * control[1]
                + ratio * ratio * end[1],
            ))
        self.current = end

    def cubic_to(self, control1, control2, end, _context):
        start = self.current
        control1 = self._point(control1)
        control2 = self._point(control2)
        end = self._point(end)
        length = (math.dist(start, control1) + math.dist(control1, control2)
                  + math.dist(control2, end))
        steps = max(2, math.ceil(length / self.curve_step))
        for index in range(1, steps + 1):
            ratio = index / steps
            inverse = 1.0 - ratio
            self.strokes[-1].append((
                inverse ** 3 * start[0]
                + 3 * inverse * inverse * ratio * control1[0]
                + 3 * inverse * ratio * ratio * control2[0]
                + ratio ** 3 * end[0],
                inverse ** 3 * start[1]
                + 3 * inverse * inverse * ratio * control1[1]
                + 3 * inverse * ratio * ratio * control2[1]
                + ratio ** 3 * end[1],
            ))
        self.current = end


def text_to_strokes(text, font_path, size, x, y, curve_step=4.0,
                    font_pixels=180, face_index=0):
    """フォントの輪郭を抽出し、機械座標の連続ストロークへ変換する。"""
    if not text:
        raise ValueError('描画する文字列が空です')
    if size <= 0:
        raise ValueError('--size は 0 より大きくしてください')
    if curve_step <= 0:
        raise ValueError('--curve-step は 0 より大きくしてください')

    face = freetype.Face(str(font_path), index=face_index)
    face.set_char_size(font_pixels * 64)
    strokes = []
    pen_x = 0.0
    baseline_y = 0.0
    previous_glyph = 0
    load_flags = freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_NO_HINTING
    for character in text:
        if character == '\n':
            pen_x = 0.0
            baseline_y += font_pixels * 1.25
            previous_glyph = 0
            continue

        glyph_index = face.get_char_index(character)
        if previous_glyph and glyph_index and face.has_kerning:
            pen_x += face.get_kerning(previous_glyph, glyph_index).x / 64.0
        face.load_glyph(glyph_index, load_flags)
        if face.glyph.outline.points:
            collector = OutlineCollector(pen_x, baseline_y, curve_step)
            face.glyph.outline.decompose(
                move_to=collector.move_to,
                line_to=collector.line_to,
                conic_to=collector.conic_to,
                cubic_to=collector.cubic_to,
            )
            strokes.extend(stroke for stroke in collector.strokes
                           if len(stroke) > 1)
        pen_x += face.glyph.advance.x / 64.0
        previous_glyph = glyph_index

    if not strokes:
        raise ValueError('文字から輪郭線を生成できませんでした')
    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    scale = size / max(max(ys) - min(ys), 1.0)
    return [[(x + (px - min(xs)) * scale, y + (py - min(ys)) * scale)
             for px, py in stroke] for stroke in strokes]


def check_fit(strokes):
    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    if not strokes:
        raise ValueError('文字から描画可能な線を生成できませんでした')
    if (min(xs) < AREA_X_MIN or max(xs) > AREA_X_MAX or
            min(ys) < AREA_Y_MIN or max(ys) > AREA_Y_MAX):
        raise ValueError(
            '描画範囲からはみ出します。--size を小さくするか '
            '--x/--y を調整してください。'
        )


def center_strokes(strokes, x=None, y=None):
    """未指定の軸を描画可能エリアの中央へ配置する。"""
    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    offset_x = (x - min(xs) if x is not None else
                (AREA_X_MIN + AREA_X_MAX - min(xs) - max(xs)) / 2)
    offset_y = (y - min(ys) if y is not None else
                (AREA_Y_MIN + AREA_Y_MAX - min(ys) - max(ys)) / 2)
    return [[(px + offset_x, py + offset_y) for px, py in stroke]
            for stroke in strokes]


def terminal_preview(strokes, max_width=80, max_height=30):
    """生成したストロークをターミナル向けのASCII画像にする。"""
    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    columns = max(1, min(max_width, math.ceil(width / max(height, 1) * max_height * 2)))
    rows = max(1, min(max_height, math.ceil(height / max(width, 1) * columns / 2)))
    canvas = [[' ' for _ in range(columns)] for _ in range(rows)]

    def cell(point):
        px, py = point
        column = round((px - min(xs)) / max(width, 1) * (columns - 1))
        row = round((py - min(ys)) / max(height, 1) * (rows - 1))
        return column, row

    for stroke in strokes:
        for start, end in zip(stroke, stroke[1:]):
            x0, y0 = cell(start)
            x1, y1 = cell(end)
            steps = max(abs(x1 - x0), abs(y1 - y0), 1)
            for index in range(steps + 1):
                ratio = index / steps
                column = round(x0 + (x1 - x0) * ratio)
                row = round(y0 + (y1 - y0) * ratio)
                canvas[row][column] = '#'

    return '\n'.join(''.join(row).rstrip() for row in canvas)


def draw(strokes, dry=False, debug_pen=False):
    io = DummyIO() if dry else LgpioIO()
    plotter = Plotter(io)
    try:
        for index, stroke in enumerate(strokes, start=1):
            if debug_pen:
                print(f'[{index:04d}] PenUp   -> '
                      f'X={stroke[0][0]:.1f}, Y={stroke[0][1]:.1f}')
            plotter.jump_to(*stroke[0])
            if debug_pen:
                print(f'[{index:04d}] PenDown')
            for point in stroke[1:]:
                if debug_pen:
                    print(f'[{index:04d}] Draw    -> '
                          f'X={point[0]:.1f}, Y={point[1]:.1f}')
                plotter.line_to(*point)
        plotter.finish()
    except KeyboardInterrupt:
        print('\n中断しました', file=sys.stderr)
        plotter.pen_up()
        io.cleanup()


def main():
    parser = argparse.ArgumentParser(description='文字列を Meiryo でホワイトボードに描く')
    parser.add_argument('text', help='描画する文字列')
    parser.add_argument('--font', help='Meiryoフォントファイル (.ttf/.ttc)')
    parser.add_argument('--size', type=float, default=90.0, help='文字列全体の高さ[mm]')
    parser.add_argument('--x', type=float, help='左端X[mm]（省略時は左右中央）')
    parser.add_argument('--y', type=float, help='上端Y[mm]（省略時は上下中央）')
    parser.add_argument('--curve-step', type=float, default=4.0,
                        help='曲線分割幅[font px]（小さいほど滑らか）')
    parser.add_argument('--face-index', type=int, default=0,
                        help='TTC内のフォント番号（Noto Sans CJK JPは0）')
    parser.add_argument('--dry', action='store_true', help='GPIOを使わず動作確認')
    parser.add_argument('--svg', help='プレビューSVGの出力先')
    parser.add_argument('--terminal-preview', action='store_true',
                        help='生成画像をターミナルにASCII表示')
    parser.add_argument('--debug-pen', action='store_true',
                        help='PenUp/PenDownと移動座標を表示')
    args = parser.parse_args()

    try:
        font_path = find_meiryo(args.font)
        strokes = text_to_strokes(
            args.text, font_path, args.size, 0, 0,
            curve_step=args.curve_step, face_index=args.face_index
        )
        strokes = center_strokes(strokes, args.x, args.y)
        check_fit(strokes)
    except (FileNotFoundError, OSError, ValueError) as error:
        parser.error(str(error))

    if args.svg:
        write_svg(args.svg, strokes)
        print(f'プレビューを書き出しました: {args.svg}')
    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    print(f'描画範囲: X={min(xs):.1f}..{max(xs):.1f} mm / '
          f'Y={min(ys):.1f}..{max(ys):.1f} mm')
    if args.terminal_preview:
        print('\n--- generated image ---')
        print(terminal_preview(strokes))
        print('--- end preview ---\n')
    if not args.dry:
        print(f'開始前にペン先を HOME ({HOME_X:.1f}, {HOME_Y:.1f}) mm '
              'へ手で合わせてください。')
    draw(strokes, dry=args.dry, debug_pen=args.debug_pen)
    draw_length = sum(math.dist(a, b) for stroke in strokes
                      for a, b in zip(stroke, stroke[1:]))
    print(f'{len(strokes)} ストローク / 描画長 {draw_length / 1000:.2f} m')


if __name__ == '__main__':
    main()