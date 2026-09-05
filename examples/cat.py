#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cat.py --- ホワイトボードに猫を描く
vplotter.py と同じディレクトリに置いて使う。

  python3 cat.py --dry --svg cat_preview.svg   # まずプレビュー
  python3 cat.py                               # 描く(下中央・高さ180mm)
  python3 cat.py --size 250 --x 950            # サイズ・位置指定
"""

import argparse
import math
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent / 'firmware'):
    if (_p / 'vplotter.py').exists():
        sys.path.insert(0, str(_p))
        break


from vplotter import (Plotter, DummyIO, LgpioIO, write_svg,
                      AREA_X_MIN, AREA_X_MAX, AREA_Y_MIN, AREA_Y_MAX)

# ------------------------------------------------------------
# ストローク生成ヘルパー (単位座標系: x 0..1, y 0..1, y上向き)
# ------------------------------------------------------------

def arc(cx, cy, rx, ry, a0, a1, n=24):
    """楕円弧。角度は度、反時計回り。"""
    return [(cx + rx*math.cos(math.radians(a)),
             cy + ry*math.sin(math.radians(a)))
            for a in [a0 + (a1-a0)*i/n for i in range(n+1)]]


def cat_strokes():
    """かわいい猫(正面・お座り)。ストロークのリストを返す。"""
    S = []

    # ---- 頭の輪郭 + 耳 (一筆) ----
    # 頭: 中心(0.5, 0.66) r=0.17。上側を耳で置き換える
    head = []
    head += arc(0.5, 0.66, 0.17, 0.155, 150, 390)      # 左上->下->右上
    # 右耳: 輪郭の続きから上へ
    head += [(0.685, 0.77), (0.66, 0.93), (0.54, 0.815)]
    # 頭頂部を渡る
    head += [(0.46, 0.815)]
    # 左耳
    head += [(0.34, 0.93), (0.315, 0.77)]
    head.append(head[0])          # 輪郭を閉じる
    S.append(head)

    # ---- 耳の内側(ちょん、と1本ずつ) ----
    S.append([(0.62, 0.80), (0.635, 0.875)])
    S.append([(0.38, 0.80), (0.365, 0.875)])

    # ---- 目 (にっこり ^ ^ ) ----
    S.append(arc(0.435, 0.685, 0.032, 0.028, 30, 150, 8))
    S.append(arc(0.565, 0.685, 0.032, 0.028, 30, 150, 8))

    # ---- 鼻 + ω の口 (2ストロークに分割) ----
    S.append([(0.5, 0.635), (0.5, 0.607)]
             + arc(0.47, 0.607, 0.030, 0.026, 0, -180, 10))
    S.append(arc(0.53, 0.607, 0.030, 0.026, 180, 360, 10))

    # ---- ひげ (左右3本ずつ) ----
    for side in (-1, 1):
        for i, dy in enumerate([0.035, 0.0, -0.035]):
            x0 = 0.5 + side*0.20
            S.append([(x0, 0.63 + dy),
                      (x0 + side*0.13, 0.64 + dy*1.8)])

    # ---- 体 (頭の下から丸く・一筆) ----
    body = arc(0.5, 0.30, 0.19, 0.245, 128, 412, 32)
    S.append(body)

    # ---- 前足 (縦線2本 + 足先) ----
    S.append([(0.44, 0.30), (0.44, 0.09)])
    S.append([(0.56, 0.30), (0.56, 0.09)])

    # ---- しっぽ (右からくるん) ----
    tail = arc(0.80, 0.16, 0.115, 0.115, -90, 120, 20)
    tail += arc(0.735, 0.315, 0.05, 0.05, -60, 120, 12)
    S.append(tail)

    return S


def to_machine(strokes, size, cx, y_bottom, aspect=0.85):
    """単位座標 -> 機械座標(y下向き)"""
    w = size * aspect
    out = []
    for s in strokes:
        out.append([(cx + (x - 0.5) * w, y_bottom - y * size) for x, y in s])
    return out


# ------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description='ホワイトボードに猫を描く')
    ap.add_argument('--size', type=float, default=180.0, help='猫の高さ[mm]')
    ap.add_argument('--x', type=float, default=(AREA_X_MIN + AREA_X_MAX) / 2,
                    help='中心X[mm] (既定=盤中央)')
    ap.add_argument('--y', type=float, default=AREA_Y_MAX - 15,
                    help='足元Y[mm] (既定=描画エリア下端-15)')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--svg', default=None)
    a = ap.parse_args()

    strokes = to_machine(cat_strokes(), a.size, a.x, a.y)

    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    print(f'範囲: X {min(xs):.0f}〜{max(xs):.0f} / Y {min(ys):.0f}〜{max(ys):.0f}')
    if (min(xs) < AREA_X_MIN or max(xs) > AREA_X_MAX or
            min(ys) < AREA_Y_MIN or max(ys) > AREA_Y_MAX):
        sys.exit('⚠️ 描画エリアからはみ出します。--size を小さくしてください')

    io = DummyIO() if a.dry else LgpioIO()
    p = Plotter(io)
    try:
        for s in strokes:
            p.jump_to(*s[0])
            for pt in s[1:]:
                p.line_to(*pt)
        p.finish()
    except KeyboardInterrupt:
        p.pen_up()
        io.cleanup()

    if a.dry and a.svg:
        write_svg(a.svg, strokes)
        print(f'プレビュー: {a.svg}')


if __name__ == '__main__':
    main()