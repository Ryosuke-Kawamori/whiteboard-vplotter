#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
characters.py --- ホワイトボードにかわいいキャラクターを描く
examples/ に置く。

  python3 examples/characters.py rabbit --dry --svg preview.svg
  python3 examples/characters.py ghost
  python3 examples/characters.py penguin --size 250 --x 500
  python3 examples/characters.py cat

複数並べる:
  python3 examples/characters.py cat --x 500
  python3 examples/characters.py rabbit --x 950
  python3 examples/characters.py penguin --x 1400
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
# ヘルパー (単位座標: x 0..1, y 0..1, y上向き)
# ------------------------------------------------------------

def arc(cx, cy, rx, ry, a0, a1, n=24):
    return [(cx + rx*math.cos(math.radians(a)),
             cy + ry*math.sin(math.radians(a)))
            for a in [a0 + (a1-a0)*i/n for i in range(n+1)]]

# ------------------------------------------------------------
# キャラクター定義
# ------------------------------------------------------------

def cat():
    S = []
    head = arc(0.5, 0.66, 0.17, 0.155, 150, 390)
    head += [(0.685, 0.77), (0.66, 0.93), (0.54, 0.815), (0.46, 0.815),
             (0.34, 0.93), (0.315, 0.77)]
    head.append(head[0])
    S.append(head)
    S.append([(0.62, 0.80), (0.635, 0.875)])
    S.append([(0.38, 0.80), (0.365, 0.875)])
    S.append(arc(0.435, 0.685, 0.032, 0.028, 30, 150, 8))
    S.append(arc(0.565, 0.685, 0.032, 0.028, 30, 150, 8))
    S.append([(0.5, 0.635), (0.5, 0.607)]
             + arc(0.47, 0.607, 0.030, 0.026, 0, -180, 10))
    S.append(arc(0.53, 0.607, 0.030, 0.026, 180, 360, 10))
    for side in (-1, 1):
        for dy in (0.035, 0.0, -0.035):
            x0 = 0.5 + side*0.20
            S.append([(x0, 0.63 + dy), (x0 + side*0.13, 0.64 + dy*1.8)])
    S.append(arc(0.5, 0.30, 0.19, 0.245, 128, 412, 32))
    S.append([(0.44, 0.30), (0.44, 0.09)])
    S.append([(0.56, 0.30), (0.56, 0.09)])
    S.append(arc(0.80, 0.16, 0.115, 0.115, -90, 120, 20)
             + arc(0.735, 0.315, 0.05, 0.05, -60, 120, 12))
    return S


def ghost():
    S = []
    body = arc(0.5, 0.58, 0.27, 0.30, 0, 180, 26)
    body += [(0.23, 0.58), (0.23, 0.16)]
    for i in range(4):                       # 波々の裾
        body += arc(0.23 + i*0.135 + 0.0675, 0.16, 0.0675, 0.06, 180, 360, 8)
    body += [(0.77, 0.58)]
    S.append(body)
    S.append(arc(0.42, 0.60, 0.022, 0.045, 90, 450, 12))   # 目
    S.append(arc(0.58, 0.60, 0.022, 0.045, 90, 450, 12))
    S.append(arc(0.5, 0.47, 0.045, 0.055, 0, 360, 14))     # 口
    S.append(arc(0.20, 0.42, 0.06, 0.05, 60, 300, 10))     # 手
    S.append(arc(0.80, 0.42, 0.06, 0.05, -120, 120, 10))
    return S


def rabbit():
    S = []
    S.append(arc(0.5, 0.42, 0.235, 0.215, 0, 360, 36))     # 頭
    S.append(arc(0.40, 0.76, 0.065, 0.185, 0, 360, 24))    # 耳
    S.append(arc(0.60, 0.76, 0.065, 0.185, 0, 360, 24))
    S.append(arc(0.40, 0.76, 0.028, 0.11, 0, 360, 16))     # 耳内側
    S.append(arc(0.60, 0.76, 0.028, 0.11, 0, 360, 16))
    S.append(arc(0.42, 0.47, 0.018, 0.018, 0, 360, 10))    # 目
    S.append(arc(0.58, 0.47, 0.018, 0.018, 0, 360, 10))
    S.append([(0.5, 0.415), (0.5, 0.39)]                   # 鼻+口
             + arc(0.475, 0.39, 0.025, 0.022, 0, -180, 8))
    S.append(arc(0.525, 0.39, 0.025, 0.022, 180, 360, 8))
    S.append(arc(0.335, 0.385, 0.03, 0.02, 20, 160, 8))    # ほっぺ
    S.append(arc(0.665, 0.385, 0.03, 0.02, 20, 160, 8))
    S.append([(0.48, 0.352), (0.48, 0.318),                # 前歯
              (0.52, 0.318), (0.52, 0.352)])
    return S


def penguin():
    S = []
    S.append(arc(0.5, 0.48, 0.27, 0.38, 0, 360, 40))       # 体
    S.append(arc(0.5, 0.38, 0.185, 0.24, -25, 205, 26))    # おなか
    S.append(arc(0.41, 0.66, 0.02, 0.02, 0, 360, 10))      # 目
    S.append(arc(0.59, 0.66, 0.02, 0.02, 0, 360, 10))
    S.append([(0.455, 0.585), (0.5, 0.615), (0.545, 0.585),# くちばし
              (0.5, 0.555), (0.455, 0.585)])
    S.append(arc(0.205, 0.44, 0.075, 0.17, 60, 285, 14))   # 羽
    S.append(arc(0.795, 0.44, 0.075, 0.17, -105, 120, 14))
    S.append(arc(0.40, 0.095, 0.06, 0.035, 180, 360, 8))   # 足
    S.append(arc(0.60, 0.095, 0.06, 0.035, 180, 360, 8))
    return S


def cat_oneline():
    """一筆書きの横向き猫。ペンを一度も上げない = サーボ不要。
    スタート(しっぽの先) -> ゴール(おしりの下)"""
    P = []
    P += [(0.985, 0.60)]                                   # しっぽの先
    P += arc(0.905, 0.44, 0.085, 0.16, 15, -75, 12)
    P += [(0.90, 0.24), (0.88, 0.10)]
    P += [(0.42, 0.10)]                                    # 地面
    P += arc(0.375, 0.10, 0.045, 0.055, 0, 180, 8)         # 前足
    P += [(0.315, 0.28), (0.265, 0.44)]                    # 胸
    P += [(0.215, 0.515), (0.178, 0.55), (0.158, 0.60),    # あご->鼻
          (0.168, 0.66), (0.185, 0.72)]                    # ->おでこ
    P += [(0.21, 0.87), (0.29, 0.75)]                      # 前耳
    P += [(0.36, 0.77)]
    P += [(0.44, 0.89), (0.468, 0.72)]                     # 後耳
    P += arc(0.55, 0.32, 0.34, 0.44, 98, 8, 24)            # 背中
    P += [(0.90, 0.24), (0.885, 0.10)]                     # おしり
    return [P]


CHARACTERS = {'cat': cat, 'ghost': ghost, 'rabbit': rabbit,
              'penguin': penguin, 'cat1': cat_oneline}

# ------------------------------------------------------------

def to_machine(strokes, size, cx, y_bottom, aspect=0.85):
    w = size * aspect
    return [[(cx + (x - 0.5)*w, y_bottom - y*size) for x, y in s]
            for s in strokes]


def main():
    ap = argparse.ArgumentParser(description='かわいいキャラクターを描く')
    ap.add_argument('char', choices=sorted(CHARACTERS), help='キャラクター名')
    ap.add_argument('--size', type=float, default=180.0, help='高さ[mm]')
    ap.add_argument('--x', type=float, default=(AREA_X_MIN + AREA_X_MAX)/2)
    ap.add_argument('--y', type=float, default=AREA_Y_MAX - 15,
                    help='足元のY[mm]')
    ap.add_argument('--aspect', type=float, default=0.85,
                    help='横/縦の比。細長く出るなら大きく(較正前の応急用)')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--svg', default=None)
    a = ap.parse_args()

    strokes = to_machine(CHARACTERS[a.char](), a.size, a.x, a.y, a.aspect)

    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    print(f'{a.char}: X {min(xs):.0f}〜{max(xs):.0f} / Y {min(ys):.0f}〜{max(ys):.0f}')
    if (min(xs) < AREA_X_MIN or max(xs) > AREA_X_MAX or
            min(ys) < AREA_Y_MIN or max(ys) > AREA_Y_MAX):
        sys.exit('⚠️ 描画エリアからはみ出します。--size か --x --y を調整してください')

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