#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_to_svg.py -- ローカル画像を SVG 化して、ホワイトボードに描画する例

使い方:
  python3 examples/image_to_svg.py --image ./sample.png --dry --svg preview.svg
  python3 examples/image_to_svg.py --image ./sample.png --size 180 --x 800 --y 700

画像はローカルのファイルパスを指定するだけで扱える。アップロードしたい画像を
このスクリプトに渡して、SVG プレビューと実描画の両方を行える。
"""

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageOps

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (_ROOT, _ROOT / 'firmware'):
    if (_p / 'vplotter.py').exists():
        sys.path.insert(0, str(_p))
        break

from vplotter import (
    AREA_X_MAX,
    AREA_X_MIN,
    AREA_Y_MAX,
    AREA_Y_MIN,
    DummyIO,
    LgpioIO,
    Plotter,
    write_svg,
)


def _normalize_image(image_path, target_width=200, threshold=200, invert=False):
    img = Image.open(image_path).convert('L')
    if invert:
        img = ImageOps.invert(img)
    width, height = img.size
    if width == 0 or height == 0:
        raise ValueError(f'画像が空です: {image_path}')
    scale = target_width / float(width)
    target_height = max(1, int(round(height * scale)))
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return img


def raster_to_strokes(
    image_path,
    target_width=220,
    threshold=200,
    invert=False,
    line_step=10,
    min_segment_pixels=8,
    max_gap_pixels=6,
):
    """グレースケール画像を、横線セグメントの列として変換する。

    黒い領域を一定行ごとに走査し、連続した黒画素列ごとに 1 ストロークを作る。
    ボードに描く際はこのストローク列をそのまま機械座標に変換する。
    """
    img = _normalize_image(image_path, target_width=target_width, threshold=threshold, invert=invert)
    width, height = img.size
    pixels = img.load()
    strokes = []

    if line_step < 1:
        raise ValueError('line_step は 1 以上にしてください')
    if min_segment_pixels < 1:
        raise ValueError('min_segment_pixels は 1 以上にしてください')
    if max_gap_pixels < 0:
        raise ValueError('max_gap_pixels は 0 以上にしてください')

    for y in range(0, height, line_step):
        segments = []
        start = None

        for x in range(width):
            val = pixels[x, y]
            is_black = val <= threshold
            if is_black and start is None:
                start = x
            elif (not is_black) and start is not None:
                segments.append((start, x - 1))
                start = None
        if start is not None:
            segments.append((start, width - 1))

        merged_segments = []
        for x0, x1 in segments:
            if merged_segments and x0 - merged_segments[-1][1] - 1 <= max_gap_pixels:
                merged_segments[-1] = (merged_segments[-1][0], x1)
            else:
                merged_segments.append((x0, x1))

        for x0, x1 in merged_segments:
            if x1 - x0 + 1 < min_segment_pixels:
                continue
            # 0..1 正規化した座標系に変換する
            x0_n = x0 / width
            x1_n = (x1 + 1) / width
            y_n = y / height
            strokes.append([(x0_n, y_n), (x1_n, y_n)])

    return strokes


def _svg_path_for_strokes(strokes, width, height):
    parts = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        d = 'M ' + ' L '.join(
            f'{x * width:.4f},{y * height:.4f}' for x, y in stroke
        )
        parts.append(f'<path d="{d}" fill="none" stroke="#111" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>')
    return '\n'.join(parts)


def write_svg_from_image(
    image_path,
    output_svg,
    target_width=220,
    threshold=200,
    invert=False,
    line_step=10,
    min_segment_pixels=8,
    max_gap_pixels=6,
):
    """ローカル画像を SVG として保存する。"""
    strokes = raster_to_strokes(
        image_path,
        target_width=target_width,
        threshold=threshold,
        invert=invert,
        line_step=line_step,
        min_segment_pixels=min_segment_pixels,
        max_gap_pixels=max_gap_pixels,
    )
    img = _normalize_image(image_path, target_width=target_width, threshold=threshold, invert=invert)
    width, height = img.size
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        _svg_path_for_strokes(strokes, width, height),
        '</svg>',
    ]
    Path(output_svg).write_text('\n'.join(svg), encoding='utf-8')
    return strokes


def to_machine(strokes, size, cx, y_bottom, aspect=0.85):
    """正規化座標 0..1 を、ホワイトボードの機械座標に変換する。"""
    if not strokes:
        return []

    width_mm = size * aspect
    height_mm = size * (1.0 / max(0.2, aspect))
    out = []
    for stroke in strokes:
        seq = []
        for x, y in stroke:
            px = cx + (x - 0.5) * width_mm
            py = y_bottom - y * height_mm
            seq.append((px, py))
        out.append(seq)
    return out


def draw_image_to_board(
    image_path,
    size=180.0,
    x=None,
    y=None,
    dry=False,
    svg_path=None,
    threshold=200,
    invert=False,
    line_step=10,
    min_segment_pixels=8,
    max_gap_pixels=6,
    should_stop=None,
):
    """ローカルの画像を白板に描画する。"""
    x0 = x if x is not None else (AREA_X_MIN + AREA_X_MAX) / 2.0
    y0 = y if y is not None else AREA_Y_MAX - 25.0

    strokes = raster_to_strokes(
        image_path,
        target_width=220,
        threshold=threshold,
        invert=invert,
        line_step=line_step,
        min_segment_pixels=min_segment_pixels,
        max_gap_pixels=max_gap_pixels,
    )
    machine = to_machine(strokes, size=size, cx=x0, y_bottom=y0)

    xs = [p[0] for s in machine for p in s]
    ys = [p[1] for s in machine for p in s]
    if machine and (min(xs) < AREA_X_MIN or max(xs) > AREA_X_MAX or min(ys) < AREA_Y_MIN or max(ys) > AREA_Y_MAX):
        raise ValueError(
            '描画範囲がホワイトボードの領域からはみ出します。--size を小さくするか、--x/--y を調整してください。'
        )

    if svg_path:
        write_svg(svg_path, machine)

    io = DummyIO() if dry else LgpioIO()
    p = Plotter(io)
    try:
        stopped = False
        for s in machine:
            if should_stop is not None and should_stop():
                stopped = True
                break
            if not s:
                continue
            p.jump_to(*s[0])
            for start, end in zip(s, s[1:]):
                if should_stop is not None and should_stop():
                    stopped = True
                    break
                distance = math.dist(start, end)
                segments = max(1, math.ceil(distance / 2.0))
                for index in range(1, segments + 1):
                    if should_stop is not None and should_stop():
                        stopped = True
                        break
                    ratio = index / segments
                    p.line_to(
                        start[0] + (end[0] - start[0]) * ratio,
                        start[1] + (end[1] - start[1]) * ratio,
                    )
                if stopped:
                    break
            if stopped:
                break
        p.finish()
    except KeyboardInterrupt:
        p.pen_up()
        io.cleanup()
    return machine


def main():
    ap = argparse.ArgumentParser(description='ローカル画像を SVG に変換して白板に描く')
    ap.add_argument('--image', required=True, help='ローカルの画像ファイルパス')
    ap.add_argument('--svg', default=None, help='SVGの出力先（プレビュー用）')
    ap.add_argument('--size', type=float, default=180.0, help='描画サイズ[mm]')
    ap.add_argument('--x', type=float, default=None, help='画像の中心X[mm]')
    ap.add_argument('--y', type=float, default=None, help='画像の下端Y[mm]')
    ap.add_argument('--threshold', type=int, default=200, help='黒判定しきい値(0-255)')
    ap.add_argument('--line-step', type=int, default=10, help='何行ごとに描くか（大きいほど線が減る）')
    ap.add_argument('--min-segment-pixels', type=int, default=8, help='描画する最小線分長[px]')
    ap.add_argument('--max-gap-pixels', type=int, default=6, help='連結して描く最大の白い隙間[px]')
    ap.add_argument('--invert', action='store_true', help='白黒を反転して描く')
    ap.add_argument('--dry', action='store_true', help='GPIO を使わず軌跡だけ確認')
    a = ap.parse_args()

    if not Path(a.image).is_file():
        raise SystemExit(f'画像が見つかりません: {a.image}')

    if a.svg:
        write_svg_from_image(
            a.image,
            a.svg,
            target_width=220,
            threshold=a.threshold,
            invert=a.invert,
            line_step=a.line_step,
            min_segment_pixels=a.min_segment_pixels,
            max_gap_pixels=a.max_gap_pixels,
        )
        print(f'SVGを出力しました: {a.svg}')

    machine = draw_image_to_board(
        a.image,
        size=a.size,
        x=a.x,
        y=a.y,
        dry=a.dry,
        svg_path=None,
        threshold=a.threshold,
        invert=a.invert,
        line_step=a.line_step,
        min_segment_pixels=a.min_segment_pixels,
        max_gap_pixels=a.max_gap_pixels,
    )
    if a.dry:
        print(f'画像から {len(machine)} ストロークを生成しました。')


if __name__ == '__main__':
    main()
