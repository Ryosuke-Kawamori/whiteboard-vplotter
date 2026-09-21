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
    BOARD_X_MAX,
    BOARD_X_MIN,
    BOARD_Y_MAX,
    BOARD_Y_MIN,
    DummyIO,
    FEED_DRAW,
    FEED_MOVE,
    HOME_X,
    HOME_Y,
    LgpioIO,
    Plotter,
    SERVO_DOWN_US,
    SERVO_FAST_DELAY,
    SERVO_FAST_STEP_US,
    SERVO_SLOW_DELAY,
    SERVO_SLOW_STEP_US,
    SERVO_SLOW_ZONE,
    SERVO_UP_US,
    SERVO_WAIT,
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
    simplify=1.5,
    min_contour_pixels=8,
):
    """二値画像の境界を追跡し、閉じた輪郭ストロークへ変換する。"""
    img = _normalize_image(image_path, target_width=target_width, threshold=threshold, invert=invert)
    width, height = img.size
    pixels = img.load()
    if simplify < 0:
        raise ValueError('simplify は 0 以上にしてください')
    if min_contour_pixels < 1:
        raise ValueError('min_contour_pixels は 1 以上にしてください')

    black = [[pixels[x, y] <= threshold for x in range(width)]
             for y in range(height)]
    edges = set()
    for y in range(height):
        for x in range(width):
            if not black[y][x]:
                continue
            if y == 0 or not black[y - 1][x]:
                edges.add(((x, y), (x + 1, y)))
            if x == width - 1 or not black[y][x + 1]:
                edges.add(((x + 1, y), (x + 1, y + 1)))
            if y == height - 1 or not black[y + 1][x]:
                edges.add(((x + 1, y + 1), (x, y + 1)))
            if x == 0 or not black[y][x - 1]:
                edges.add(((x, y + 1), (x, y)))

    outgoing = {}
    for start, end in edges:
        outgoing.setdefault(start, []).append(end)

    contours = []
    unused = set(edges)
    while unused:
        start, current = min(unused)
        contour = [start, current]
        unused.remove((start, current))
        while current != start:
            candidates = [end for end in outgoing.get(current, [])
                          if (current, end) in unused]
            if not candidates:
                break
            previous = contour[-2]
            incoming = (current[0] - previous[0], current[1] - previous[1])
            direction_order = {
                (1, 0): ((0, 1), (1, 0), (0, -1), (-1, 0)),
                (0, 1): ((-1, 0), (0, 1), (1, 0), (0, -1)),
                (-1, 0): ((0, -1), (-1, 0), (0, 1), (1, 0)),
                (0, -1): ((1, 0), (0, -1), (-1, 0), (0, 1)),
            }[incoming]
            candidates.sort(key=lambda end: direction_order.index(
                (end[0] - current[0], end[1] - current[1])))
            following = candidates[0]
            unused.remove((current, following))
            contour.append(following)
            current = following
        if contour[-1] == start and len(contour) - 1 >= min_contour_pixels:
            contours.append(_simplify_closed_contour(contour, simplify))

    return [[(x / width, y / height) for x, y in contour]
            for contour in contours]


def _point_line_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    if dx == 0 and dy == 0:
        return math.dist(point, start)
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)
    projection = (start[0] + ratio * dx, start[1] + ratio * dy)
    return math.dist(point, projection)


def _simplify_path(points, tolerance):
    if len(points) <= 2:
        return points
    distances = [_point_line_distance(point, points[0], points[-1])
                 for point in points[1:-1]]
    if not distances or max(distances) <= tolerance:
        return [points[0], points[-1]]
    split = distances.index(max(distances)) + 1
    return (_simplify_path(points[:split + 1], tolerance)[:-1]
            + _simplify_path(points[split:], tolerance))


def _simplify_closed_contour(contour, tolerance):
    points = contour[:-1]
    if tolerance == 0 or len(points) <= 3:
        return contour
    anchor = points[0]
    split = max(range(1, len(points)), key=lambda index: math.dist(anchor, points[index]))
    first = _simplify_path(points[:split + 1], tolerance)
    second = _simplify_path(points[split:] + [anchor], tolerance)
    return first[:-1] + second


def _svg_path_for_strokes(strokes, scale_x=1.0, scale_y=1.0):
    parts = []
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        d = 'M ' + ' L '.join(
            f'{x * scale_x:.4f},{y * scale_y:.4f}' for x, y in stroke
        )
        parts.append(f'<path d="{d}" fill="none" stroke="#111" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>')
    return '\n'.join(parts)


def write_svg_from_image(
    image_path,
    output_svg,
    target_width=220,
    threshold=200,
    invert=False,
    simplify=1.5,
    min_contour_pixels=8,
    size=180.0,
    x=None,
    y=None,
):
    """盤面・描画可能領域・実配置を重ねたSVGプレビューを保存する。"""
    machine = image_to_machine_strokes(
        image_path,
        target_width=target_width,
        threshold=threshold,
        invert=invert,
        simplify=simplify,
        min_contour_pixels=min_contour_pixels,
        size=size,
        x=x,
        y=y,
    )
    write_board_preview(output_svg, machine)
    return machine


def write_board_preview(output_svg, strokes):
    """盤面と描画可能領域に、機械座標のストロークを重ねて保存する。"""
    board_width = BOARD_X_MAX - BOARD_X_MIN
    board_height = BOARD_Y_MAX - BOARD_Y_MIN
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{BOARD_X_MIN} {BOARD_Y_MIN} {board_width} {board_height}">',
        f'<rect x="{BOARD_X_MIN}" y="{BOARD_Y_MIN}" width="{board_width}" height="{board_height}" fill="#fff" stroke="#64748b" stroke-width="5"/>',
        f'<rect x="{AREA_X_MIN}" y="{AREA_Y_MIN}" width="{AREA_X_MAX - AREA_X_MIN}" height="{AREA_Y_MAX - AREA_Y_MIN}" fill="#dbeafe" fill-opacity="0.35" stroke="#2563eb" stroke-width="4" stroke-dasharray="16 10"/>',
        f'<text x="{BOARD_X_MIN + 25}" y="{BOARD_Y_MIN + 45}" font-size="28" fill="#475569">Whiteboard {board_width:.0f} x {board_height:.0f} mm</text>',
        f'<text x="{AREA_X_MIN + 20}" y="{AREA_Y_MIN + 40}" font-size="26" fill="#2563eb">Drawable X {AREA_X_MIN:.0f}..{AREA_X_MAX:.0f} / Y {AREA_Y_MIN:.0f}..{AREA_Y_MAX:.0f} mm</text>',
        _svg_path_for_strokes(strokes),
        '</svg>',
    ]
    Path(output_svg).write_text('\n'.join(svg), encoding='utf-8')


def to_machine(strokes, size, cx, y_bottom, image_aspect=1.0):
    """元画像の縦横比を保って、正規化座標を機械座標に変換する。"""
    if not strokes:
        return []
    if size <= 0:
        raise ValueError('size は 0 より大きくしてください')
    if image_aspect <= 0:
        raise ValueError('image_aspect は 0 より大きくしてください')

    width_mm = size
    height_mm = size / image_aspect
    out = []
    for stroke in strokes:
        seq = []
        for x, y in stroke:
            px = cx + (x - 0.5) * width_mm
            py = y_bottom - height_mm + y * height_mm
            seq.append((px, py))
        out.append(seq)
    return out


def image_to_machine_strokes(
    image_path,
    size=180.0,
    x=None,
    y=None,
    target_width=220,
    threshold=200,
    invert=False,
    simplify=1.5,
    min_contour_pixels=8,
):
    x0 = x if x is not None else (AREA_X_MIN + AREA_X_MAX) / 2.0
    y0 = y if y is not None else AREA_Y_MAX - 25.0
    strokes = raster_to_strokes(
        image_path,
        target_width=target_width,
        threshold=threshold,
        invert=invert,
        simplify=simplify,
        min_contour_pixels=min_contour_pixels,
    )
    with Image.open(image_path) as image:
        image_aspect = image.width / image.height
    machine = to_machine(
        strokes, size=size, cx=x0, y_bottom=y0, image_aspect=image_aspect
    )
    if not machine:
        raise ValueError('画像から描画可能な輪郭を生成できませんでした')
    xs = [px for stroke in machine for px, _ in stroke]
    ys = [py for stroke in machine for _, py in stroke]
    if (min(xs) < AREA_X_MIN or max(xs) > AREA_X_MAX or
            min(ys) < AREA_Y_MIN or max(ys) > AREA_Y_MAX):
        raise ValueError(
            '描画範囲がホワイトボードの領域からはみ出します。'
            '--size を小さくするか、--x/--y を調整してください。'
        )
    return machine


def _servo_transition_seconds(start_us, target_us):
    current = int(start_us)
    target = int(target_us)
    distance = abs(target - current)
    if distance == 0:
        return 0.0
    direction = 1 if target > current else -1
    slow_distance = distance * SERVO_SLOW_ZONE
    elapsed = 0.0
    while current != target:
        travelled = abs(current - start_us)
        remaining = abs(target - current)
        progress = travelled / distance
        ease = 0.25 + 0.75 * (4.0 * progress * (1.0 - progress))
        if remaining <= slow_distance:
            step = SERVO_SLOW_STEP_US
            elapsed += SERVO_SLOW_DELAY
        else:
            step = SERVO_FAST_STEP_US
            elapsed += SERVO_FAST_DELAY
        current += direction * min(max(1, round(step * ease)), remaining)
    return elapsed + SERVO_WAIT


def estimate_plot_time(strokes):
    """描画・空移動・サーボ動作を含む概算秒数を返す。"""
    draw_length = sum(
        math.dist(start, end)
        for stroke in strokes
        for start, end in zip(stroke, stroke[1:])
    )
    move_length = 0.0
    previous = (HOME_X, HOME_Y)
    for stroke in strokes:
        move_length += math.dist(previous, stroke[0])
        previous = stroke[-1]
    move_length += math.dist(previous, (HOME_X, HOME_Y))
    servo_per_stroke = (
        _servo_transition_seconds(SERVO_UP_US, SERVO_DOWN_US)
        + _servo_transition_seconds(SERVO_DOWN_US, SERVO_UP_US)
    )
    seconds = (draw_length / FEED_DRAW + move_length / FEED_MOVE
               + len(strokes) * servo_per_stroke + SERVO_WAIT)
    return draw_length, move_length, seconds


def format_plot_estimate(strokes):
    draw_length, move_length, seconds = estimate_plot_time(strokes)
    return (f'{len(strokes)} ストローク / 描画 {draw_length / 1000:.2f} m / '
            f'空移動 {move_length / 1000:.2f} m / 約 {seconds / 60:.1f} 分')


def draw_image_to_board(
    image_path,
    size=180.0,
    x=None,
    y=None,
    dry=False,
    svg_path=None,
    threshold=200,
    invert=False,
    simplify=1.5,
    min_contour_pixels=8,
    should_stop=None,
):
    """ローカルの画像を白板に描画する。"""
    machine = image_to_machine_strokes(
        image_path,
        size=size,
        x=x,
        y=y,
        threshold=threshold,
        invert=invert,
        simplify=simplify,
        min_contour_pixels=min_contour_pixels,
    )

    if svg_path:
        write_svg_from_image(
            image_path, svg_path, threshold=threshold, invert=invert,
            simplify=simplify, min_contour_pixels=min_contour_pixels,
            size=size, x=x, y=y,
        )

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
    ap.add_argument('--size', type=float, default=180.0, help='描画幅[mm]')
    ap.add_argument('--x', type=float, default=None, help='画像の中心X[mm]')
    ap.add_argument('--y', type=float, default=None, help='画像の下端Y[mm]')
    ap.add_argument('--threshold', type=int, default=200, help='黒判定しきい値(0-255)')
    ap.add_argument('--simplify', type=float, default=1.5,
                    help='輪郭の単純化量[px]（小さいほど形状が細かい）')
    ap.add_argument('--min-contour-pixels', type=int, default=8,
                    help='描画する最小輪郭長[px]')
    ap.add_argument('--invert', action='store_true', help='白黒を反転して描く')
    ap.add_argument('--dry', action='store_true', help='GPIO を使わず軌跡だけ確認')
    a = ap.parse_args()

    if not Path(a.image).is_file():
        raise SystemExit(f'画像が見つかりません: {a.image}')

    if a.svg:
        machine = write_svg_from_image(
            a.image,
            a.svg,
            target_width=220,
            threshold=a.threshold,
            invert=a.invert,
            simplify=a.simplify,
            min_contour_pixels=a.min_contour_pixels,
            size=a.size,
            x=a.x,
            y=a.y,
        )
        print(f'SVGを出力しました: {a.svg}')
    else:
        machine = image_to_machine_strokes(
            a.image, size=a.size, x=a.x, y=a.y,
            threshold=a.threshold, invert=a.invert,
            simplify=a.simplify,
            min_contour_pixels=a.min_contour_pixels,
        )

    print(f'想定時間: {format_plot_estimate(machine)}')

    draw_image_to_board(
        a.image,
        size=a.size,
        x=a.x,
        y=a.y,
        dry=a.dry,
        svg_path=None,
        threshold=a.threshold,
        invert=a.invert,
        simplify=a.simplify,
        min_contour_pixels=a.min_contour_pixels,
    )
    if a.dry:
        print(f'画像から {len(machine)} ストロークを生成しました。')


if __name__ == '__main__':
    main()
