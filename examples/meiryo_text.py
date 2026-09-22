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
from collections import defaultdict
from pathlib import Path

import freetype
import numpy as np
from PIL import Image

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

SINGLELINE_RENDER_PX = 600
SINGLELINE_THRESHOLD = 128
SINGLELINE_PRUNE_PX = 3
SINGLELINE_SIMPLIFY_PX = 1.5
SINGLELINE_MERGE_GAP_PX = 2.0


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


def _zhang_suen_thin(binary):
    """Zhang-Suen thinning を 8-neighbor 画像へ適用する。"""
    image = np.array(binary, dtype=np.uint8, copy=True)
    if image.size == 0:
        return image
    height, width = image.shape
    if height < 3 or width < 3:
        return image

    changed = True
    while changed:
        changed = False
        to_remove = []
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                if image[y, x] == 0:
                    continue
                p2, p3, p4, p5, p6, p7, p8, p9 = (
                    image[y - 1, x], image[y - 1, x + 1], image[y, x + 1],
                    image[y + 1, x + 1], image[y + 1, x], image[y + 1, x - 1],
                    image[y, x - 1], image[y - 1, x - 1],
                )
                neighbors = sum((p2, p3, p4, p5, p6, p7, p8, p9))
                if neighbors < 2 or neighbors > 6:
                    continue
                transitions = 0
                for first, second in zip((p2, p3, p4, p5, p6, p7, p8, p9),
                                         (p3, p4, p5, p6, p7, p8, p9, p2)):
                    if first == 0 and second == 1:
                        transitions += 1
                if transitions != 1:
                    continue
                if p2 * p4 * p6 == 0 and p4 * p6 * p8 == 0:
                    to_remove.append((y, x))
        for y, x in to_remove:
            if image[y, x]:
                image[y, x] = 0
                changed = True

        to_remove = []
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                if image[y, x] == 0:
                    continue
                p2, p3, p4, p5, p6, p7, p8, p9 = (
                    image[y - 1, x], image[y - 1, x + 1], image[y, x + 1],
                    image[y + 1, x + 1], image[y + 1, x], image[y + 1, x - 1],
                    image[y, x - 1], image[y - 1, x - 1],
                )
                neighbors = sum((p2, p3, p4, p5, p6, p7, p8, p9))
                if neighbors < 2 or neighbors > 6:
                    continue
                transitions = 0
                for first, second in zip((p2, p3, p4, p5, p6, p7, p8, p9),
                                         (p3, p4, p5, p6, p7, p8, p9, p2)):
                    if first == 0 and second == 1:
                        transitions += 1
                if transitions != 1:
                    continue
                if p2 * p4 * p8 == 0 and p2 * p6 * p8 == 0:
                    to_remove.append((y, x))
        for y, x in to_remove:
            if image[y, x]:
                image[y, x] = 0
                changed = True
    return image > 0


def _connected_components(mask):
    """Binary mask を connected component ごとに返す。"""
    visited = set()
    height, width = mask.shape
    components = []
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or (y, x) in visited:
                continue
            stack = [(y, x)]
            visited.add((y, x))
            component = []
            while stack:
                cy, cx = stack.pop()
                component.append((cy, cx))
                for ny in range(max(0, cy - 1), min(height, cy + 2)):
                    for nx in range(max(0, cx - 1), min(width, cx + 2)):
                        if (ny, nx) == (cy, cx) or not mask[ny, nx]:
                            continue
                        if (ny, nx) not in visited:
                            visited.add((ny, nx))
                            stack.append((ny, nx))
            components.append(component)
    return components


def _polyline_length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _simplify_polyline(points, tolerance):
    if len(points) <= 2:
        return points
    simplified = [points[0]]
    for index in range(1, len(points) - 1):
        prev = points[index - 1]
        current = points[index]
        next_point = points[index + 1]
        cross = abs((next_point[0] - prev[0]) * (current[1] - prev[1])
                    - (next_point[1] - prev[1]) * (current[0] - prev[0]))
        denom = math.dist(prev, next_point)
        if denom <= 1e-6:
            simplified.append(current)
            continue
        distance = cross / denom
        if distance > tolerance:
            simplified.append(current)
    simplified.append(points[-1])
    return simplified


def _skeleton_to_polylines(mask, prune_px=3, simplify_px=1.5, merge_gap_px=2.0):
    """1ピクセル幅の骨格線を長い polyline にまとめる。"""
    components = _connected_components(mask)
    polylines = []
    for component in components:
        if len(component) < 2:
            continue
        adjacency = defaultdict(set)
        for y, x in component:
            for ny in range(max(0, y - 1), min(mask.shape[0], y + 2)):
                for nx in range(max(0, x - 1), min(mask.shape[1], x + 2)):
                    if (ny, nx) == (y, x) or not mask[ny, nx]:
                        continue
                    adjacency[(y, x)].add((ny, nx))
        for start in list(adjacency):
            if len(adjacency[start]) == 0:
                continue
            if any(len(adjacency[p]) == 1 for p in adjacency if p == start):
                pass
        used = set()
        for start in sorted(component, key=lambda p: (len(adjacency[p]), -p[0], -p[1])):
            if start in used:
                continue
            path = [start]
            current = start
            previous = None
            while True:
                neighbors = [n for n in adjacency[current]
                             if n not in used and n != previous]
                if not neighbors:
                    break
                if len(neighbors) > 1:
                    candidate = max(neighbors, key=lambda point: len(adjacency[point]))
                    if candidate in path[:-1]:
                        candidate = neighbors[0]
                else:
                    candidate = neighbors[0]
                if candidate in path[:-1]:
                    break
                used.add(current)
                previous, current = current, candidate
                path.append(current)
                if len(path) > 1 and current in path[:-1]:
                    break
            if len(path) < 2:
                continue
            points = [(float(x), float(y)) for y, x in path]
            if _polyline_length(points) <= prune_px:
                continue
            points = _simplify_polyline(points, simplify_px)
            if len(points) >= 2:
                polylines.append(points)

    merged = []
    for polyline in polylines:
        if not merged:
            merged.append(polyline)
            continue
        last = merged[-1]
        gap = math.dist(last[-1], polyline[0])
        if gap <= merge_gap_px and _polyline_length(last + polyline) < _polyline_length(last) + _polyline_length(polyline) + 1.0:
            merged[-1] = last + polyline[1:]
        else:
            merged.append(polyline)
    return merged


def _render_glyph_singleline(face, character, render_px):
    """1文字を高解像度 bitmap にラスタライズし、骨格線へ変換する。"""
    face.set_char_size(render_px * 64)
    glyph_index = face.get_char_index(character)
    face.load_char(character, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
    if not face.glyph.bitmap.buffer:
        return []
    bitmap = face.glyph.bitmap
    pixels = np.frombuffer(bitmap.buffer, dtype=np.uint8)
    rows = bitmap.rows
    width = bitmap.width
    pitch = max(bitmap.pitch, width)
    if pixels.size < rows * pitch:
        pixels = np.resize(pixels, rows * pitch)
    image = np.asarray(pixels[:rows * pitch], dtype=np.uint8).reshape(rows, pitch)
    mask = image[:, :width] > SINGLELINE_THRESHOLD
    if not np.any(mask):
        return []
    skeleton = _zhang_suen_thin(mask)
    polylines = _skeleton_to_polylines(skeleton,
                                       prune_px=SINGLELINE_PRUNE_PX,
                                       simplify_px=SINGLELINE_SIMPLIFY_PX,
                                       merge_gap_px=SINGLELINE_MERGE_GAP_PX)
    if not polylines:
        return []
    offset = [(face.glyph.bitmap_left + x, face.glyph.bitmap_top - y)
              for poly in polylines for x, y in poly]
    if not offset:
        return []
    return [
        [(float(x + cx), float(y + cy)) for x, y in poly]
        for poly, (cx, cy) in zip(polylines, [
            (0.0, 0.0),
        ] * len(polylines))
    ]


def text_to_strokes(text, font_path, size, x, y, curve_step=4.0,
                    font_pixels=180, face_index=0, per_line_size=False):
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
    stroke_lines = []
    line_index = 0
    pen_x = 0.0
    baseline_y = 0.0
    previous_glyph = 0
    load_flags = freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_NO_HINTING
    for character in text:
        if character == '\n':
            pen_x = 0.0
            baseline_y += font_pixels * 1.25
            previous_glyph = 0
            line_index += 1
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
            glyph_strokes = [stroke for stroke in collector.strokes
                             if len(stroke) > 1]
            strokes.extend(glyph_strokes)
            stroke_lines.extend([line_index] * len(glyph_strokes))
        pen_x += face.glyph.advance.x / 64.0
        previous_glyph = glyph_index

    if not strokes:
        raise ValueError('文字から輪郭線を生成できませんでした')
    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    min_x = min(xs)
    min_y = min(ys)
    natural_height = max(ys) - min_y
    if per_line_size:
        line_heights = []
        for current_line in set(stroke_lines):
            line_ys = [py for stroke, stroke_line in zip(strokes, stroke_lines)
                       if stroke_line == current_line for _, py in stroke]
            line_heights.append(max(line_ys) - min(line_ys))
        natural_height = max(line_heights)
    scale = size / max(natural_height, 1.0)
    return [[(x + (px - min_x) * scale, y + (py - min_y) * scale)
             for px, py in stroke] for stroke in strokes]


def _bitmap_buffer_to_array(bitmap):
    """FreeType の bitmap.buffer は list/bytes/memoryview のいずれかなので正規化する。"""
    raw = bitmap.buffer
    if isinstance(raw, (bytes, bytearray, memoryview)):
        return np.frombuffer(raw, dtype=np.uint8)
    if raw is None:
        return np.array([], dtype=np.uint8)
    return np.asarray(list(raw), dtype=np.uint8)


def _bitmap_to_skeleton(mask, threshold):
    """Bitmap のしきい値越え領域を 1px 系の骨格線へ変換する。"""
    if mask.ndim != 2:
        return np.zeros_like(mask, dtype=bool)
    binary = np.asarray(mask, dtype=np.uint8)
    if binary.size == 0:
        return np.zeros_like(binary, dtype=bool)
    if binary.max() <= 1:
        binary = binary.astype(np.uint8)
    else:
        binary = (binary > threshold).astype(np.uint8)
    return _zhang_suen_thin(binary.astype(np.uint8))


def _trace_skeleton_polyline(component, mask):
    """骨格連結成分から長いポリラインを抽出する。"""
    candidates = list(component)
    if not candidates:
        return []

    adjacency = {}
    height, width = mask.shape
    for y, x in candidates:
        neighbors = []
        for ny in range(max(0, y - 1), min(height, y + 2)):
            for nx in range(max(0, x - 1), min(width, x + 2)):
                if (ny, nx) == (y, x):
                    continue
                if mask[ny, nx] and (ny, nx) in component:
                    neighbors.append((ny, nx))
        adjacency[(y, x)] = neighbors

    visited = set()
    polylines = []
    for start in sorted(candidates, key=lambda point: (len(adjacency[point]), -point[0], -point[1])):
        if start in visited:
            continue
        path = [start]
        current = start
        previous = None
        visited.add(start)

        while True:
            next_candidates = [
                neighbor for neighbor in adjacency[current]
                if neighbor != previous and neighbor not in path[:-1]
            ]
            if not next_candidates:
                break
            weighted = sorted(
                next_candidates,
                key=lambda point: (-len(adjacency[point]), abs(point[0] - current[0]) + abs(point[1] - current[1])),
            )
            next_point = weighted[0]
            if next_point in path[:-1]:
                break
            path.append(next_point)
            visited.add(next_point)
            previous, current = current, next_point
            if len(path) > 2 and current == start:
                break

        if len(path) >= 2:
            polylines.append(path)

    return polylines


def _skeleton_to_polylines(mask, prune_px=3, simplify_px=1.5, merge_gap_px=2.0):
    """1ピクセル幅の骨格線を長い polyline にまとめる。"""
    components = _connected_components(mask)
    polylines = []
    for component in components:
        if len(component) < 2:
            continue
        traced = _trace_skeleton_polyline(set(component), mask)
        for path in traced:
            if len(path) < 2:
                continue
            points = [(float(x), float(y)) for y, x in path]
            if _polyline_length(points) <= prune_px:
                continue
            points = _simplify_polyline(points, simplify_px)
            if len(points) >= 2:
                polylines.append(points)

    merged = []
    for polyline in polylines:
        if not merged:
            merged.append(polyline)
            continue
        last = merged[-1]
        gap = math.dist(last[-1], polyline[0])
        if gap <= merge_gap_px:
            merged[-1] = last + polyline[1:]
        else:
            merged.append(polyline)
    return merged


def text_to_singleline_strokes(text, font_path, size, x, y,
                              curve_step=4.0, font_pixels=180,
                              face_index=0, per_line_size=False,
                              render_px=SINGLELINE_RENDER_PX,
                              threshold=SINGLELINE_THRESHOLD,
                              prune_px=SINGLELINE_PRUNE_PX,
                              simplify_px=SINGLELINE_SIMPLIFY_PX,
                              merge_gap_px=SINGLELINE_MERGE_GAP_PX):
    """文字を高解像度ラスター化して骨格化し、一本線のストロークへ変換する。"""
    if not text:
        raise ValueError('描画する文字列が空です')
    if size <= 0:
        raise ValueError('--size は 0 より大きくしてください')

    face = freetype.Face(str(font_path), index=face_index)
    face.set_char_size(render_px * 64)
    strokes = []
    stroke_lines = []
    line_index = 0
    pen_x = 0.0
    baseline_y = 0.0
    previous_glyph = 0

    for character in text:
        if character == '\n':
            pen_x = 0.0
            baseline_y += render_px * 1.25
            previous_glyph = 0
            line_index += 1
            continue

        glyph_index = face.get_char_index(character)
        if previous_glyph and glyph_index and face.has_kerning:
            pen_x += face.get_kerning(previous_glyph, glyph_index).x / 64.0

        face.load_char(character, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        bitmap = face.glyph.bitmap
        if not bitmap.buffer or bitmap.width <= 0 or bitmap.rows <= 0:
            pen_x += face.glyph.advance.x / 64.0
            previous_glyph = glyph_index
            continue

        pixels = _bitmap_buffer_to_array(bitmap)
        pitch = max(bitmap.pitch, bitmap.width)
        if pixels.size < bitmap.rows * pitch:
            pixels = np.resize(pixels, bitmap.rows * pitch)
        image = np.asarray(pixels[:bitmap.rows * pitch], dtype=np.uint8).reshape(bitmap.rows, pitch)
        mask = image[:, :bitmap.width] > threshold
        if not np.any(mask):
            pen_x += face.glyph.advance.x / 64.0
            previous_glyph = glyph_index
            continue

        skeleton = _bitmap_to_skeleton(mask, threshold)
        polylines = _skeleton_to_polylines(
            skeleton,
            prune_px=prune_px,
            simplify_px=simplify_px,
            merge_gap_px=merge_gap_px,
        )
        for polyline in polylines:
            world_points = []
            for px_index, py_index in polyline:
                world_x = pen_x + face.glyph.bitmap_left + px_index
                world_y = baseline_y - (face.glyph.bitmap_top - py_index)
                world_points.append((world_x, world_y))
            if len(world_points) > 1:
                strokes.append(world_points)
                stroke_lines.append(line_index)

        pen_x += face.glyph.advance.x / 64.0
        previous_glyph = glyph_index

    if not strokes:
        raise ValueError('文字から骨格線を生成できませんでした')

    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    min_x = min(xs)
    min_y = min(ys)
    natural_height = max(ys) - min_y
    if per_line_size:
        line_heights = []
        for current_line in set(stroke_lines):
            line_ys = [py for stroke, line_no in zip(strokes, stroke_lines)
                       if line_no == current_line for _, py in stroke]
            if line_ys:
                line_heights.append(max(line_ys) - min(line_ys))
        if line_heights:
            natural_height = max(line_heights)
    scale = size / max(natural_height, 1.0)
    return [[(x + (px - min_x) * scale, y + (py - min_y) * scale)
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


def draw(strokes, dry=False, debug_pen=False, should_stop=None):
    io = DummyIO() if dry else LgpioIO()
    plotter = Plotter(io)
    stopped = False
    try:
        for index, stroke in enumerate(strokes, start=1):
            if should_stop is not None and should_stop():
                stopped = True
                break
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
                if should_stop is not None and should_stop():
                    stopped = True
                    break
                plotter.line_to(*point)
            if stopped:
                break
        plotter.finish()
    except KeyboardInterrupt:
        print('\n中断しました', file=sys.stderr)
        plotter.pen_up()
        io.cleanup()
        stopped = True
    return stopped


def summarize_strokes(strokes):
    """ストロークの数と移動長を計測する。"""
    stroke_count = len(strokes)
    point_count = sum(len(stroke) for stroke in strokes)
    draw_length = sum(math.dist(a, b) for stroke in strokes
                      for a, b in zip(stroke, stroke[1:]))
    penup_length = 0.0
    previous_end = None
    for stroke in strokes:
        if not stroke:
            continue
        if previous_end is not None:
            penup_length += math.dist(previous_end, stroke[0])
        previous_end = stroke[-1]
    return {
        'stroke_count': stroke_count,
        'point_count': point_count,
        'draw_length': draw_length,
        'penup_length': penup_length,
    }


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
    parser.add_argument('--single-line', action='store_true',
                        help='フォント輪郭を一本線骨格へ変換して描画')
    parser.add_argument('--dry', action='store_true', help='GPIOを使わず動作確認')
    parser.add_argument('--svg', help='プレビューSVGの出力先')
    parser.add_argument('--terminal-preview', action='store_true',
                        help='生成画像をターミナルにASCII表示')
    parser.add_argument('--debug-pen', action='store_true',
                        help='PenUp/PenDownと移動座標を表示')
    args = parser.parse_args()

    try:
        font_path = find_meiryo(args.font)
        if args.single_line:
            outline_strokes = text_to_strokes(
                args.text, font_path, args.size, 0, 0,
                curve_step=args.curve_step, face_index=args.face_index,
            )
            strokes = text_to_singleline_strokes(
                args.text, font_path, args.size, 0, 0,
                curve_step=args.curve_step, face_index=args.face_index,
            )
            outline_summary = summarize_strokes(outline_strokes)
            single_summary = summarize_strokes(strokes)
            print('outline: '
                  f'strokes={outline_summary["stroke_count"]} / '
                  f'points={outline_summary["point_count"]} / '
                  f'draw={outline_summary["draw_length"]:.1f} mm / '
                  f'penup={outline_summary["penup_length"]:.1f} mm')
            print('single-line: '
                  f'strokes={single_summary["stroke_count"]} / '
                  f'points={single_summary["point_count"]} / '
                  f'draw={single_summary["draw_length"]:.1f} mm / '
                  f'penup={single_summary["penup_length"]:.1f} mm')
        else:
            strokes = text_to_strokes(
                args.text, font_path, args.size, 0, 0,
                curve_step=args.curve_step, face_index=args.face_index,
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