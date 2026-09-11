#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
characters.py --- ホワイトボードにかわいいキャラクターを描く (完成版)
リポジトリの examples/ に置く。firmware/vplotter.py を自動で見つける。

使い方:
  python3 examples/characters.py list                  # キャラ一覧
  python3 examples/characters.py cat1                  # 一筆書き猫(サーボ不要)
  python3 examples/characters.py rabbit --size 250     # サイズ指定
  python3 examples/characters.py all                   # 全員整列
  python3 examples/characters.py cat --dry --svg p.svg # プレビューのみ

描く前に: モーターを脱力してペン先を HOME (MOTOR_SPACING/2, HOME_Y) に
手で置いてから実行すること。ここが唯一の座標基準。
"""

import argparse
import math
import pathlib
import sys

# ---- firmware/vplotter.py を探して import パスに追加 ----
_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent / 'firmware', _HERE.parent):
    if (_p / 'vplotter.py').exists():
        sys.path.insert(0, str(_p))
        break
else:
    sys.exit('vplotter.py が見つかりません。リポジトリ構成を確認してください')

from vplotter import (Plotter, DummyIO, LgpioIO, write_svg,
                      AREA_X_MIN, AREA_X_MAX, AREA_Y_MIN, AREA_Y_MAX,
                      FEED_DRAW, FEED_MOVE)

# ============================================================
# ヘルパー (単位座標: x 0..1 / y 0..1 / y上向き)
# ============================================================

def arc(cx, cy, rx, ry, a0, a1, n=24):
    """楕円弧。角度は度。a0 -> a1 へ補間(減少方向なら時計回り)"""
    return [(cx + rx * math.cos(math.radians(a)),
             cy + ry * math.sin(math.radians(a)))
            for a in [a0 + (a1 - a0) * i / n for i in range(n + 1)]]

# ============================================================
# キャラクター定義
#   関数がストローク(点列)のリストを返す。
#   1ストローク = ペンを下ろしたまま描く1本の線。
# ============================================================

def cat():
    """正面お座り猫。にっこり目とωの口。"""
    S = []
    head = arc(0.5, 0.66, 0.17, 0.155, 150, 390)
    head += [(0.685, 0.77), (0.66, 0.93), (0.54, 0.815), (0.46, 0.815),
             (0.34, 0.93), (0.315, 0.77)]
    head.append(head[0])
    S.append(head)                                          # 頭+耳
    S.append([(0.62, 0.80), (0.635, 0.875)])                # 耳内側
    S.append([(0.38, 0.80), (0.365, 0.875)])
    S.append(arc(0.435, 0.685, 0.032, 0.028, 30, 150, 8))   # 目 ^ ^
    S.append(arc(0.565, 0.685, 0.032, 0.028, 30, 150, 8))
    S.append([(0.5, 0.635), (0.5, 0.607)]                   # 鼻+口(左)
             + arc(0.47, 0.607, 0.030, 0.026, 0, -180, 10))
    S.append(arc(0.53, 0.607, 0.030, 0.026, 180, 360, 10))  # 口(右)
    for side in (-1, 1):                                    # ひげ
        for dy in (0.035, 0.0, -0.035):
            x0 = 0.5 + side * 0.20
            S.append([(x0, 0.63 + dy), (x0 + side * 0.13, 0.64 + dy * 1.8)])
    S.append(arc(0.5, 0.30, 0.19, 0.245, 128, 412, 32))     # 体
    S.append([(0.44, 0.30), (0.44, 0.09)])                  # 前足
    S.append([(0.56, 0.30), (0.56, 0.09)])
    S.append(arc(0.80, 0.16, 0.115, 0.115, -90, 120, 20)    # しっぽ
             + arc(0.735, 0.315, 0.05, 0.05, -60, 120, 12))
    return S


def cat_oneline():
    """一筆書きの横向き猫。ペンを一度も上げない = サーボ不要。
    しっぽの先スタート -> おしりの下ゴール。較正チェックにも最適。"""
    P = []
    P += [(0.985, 0.60)]                                    # しっぽの先
    P += arc(0.905, 0.44, 0.085, 0.16, 15, -75, 12)
    P += [(0.90, 0.24), (0.88, 0.10)]
    P += [(0.42, 0.10)]                                     # 地面
    P += arc(0.375, 0.10, 0.045, 0.055, 0, 180, 8)          # 前足のぷに
    P += [(0.315, 0.28), (0.265, 0.44)]                     # 胸
    P += [(0.215, 0.515), (0.178, 0.55), (0.158, 0.60),     # あご->鼻
          (0.168, 0.66), (0.185, 0.72)]                     # ->おでこ
    P += [(0.21, 0.87), (0.29, 0.75)]                       # 前耳
    P += [(0.36, 0.77)]
    P += [(0.44, 0.89), (0.468, 0.72)]                      # 後耳
    P += arc(0.55, 0.32, 0.34, 0.44, 98, 8, 24)             # 背中
    P += [(0.90, 0.24), (0.885, 0.10)]                      # おしり
    return [P]


def ghost():
    """おばけ。波々の裾と「あー」の口。"""
    S = []
    body = arc(0.5, 0.58, 0.27, 0.30, 0, 180, 26)
    body += [(0.23, 0.58), (0.23, 0.16)]
    for i in range(4):
        body += arc(0.23 + i * 0.135 + 0.0675, 0.16, 0.0675, 0.06, 180, 360, 8)
    body += [(0.77, 0.58)]
    S.append(body)
    S.append(arc(0.42, 0.60, 0.022, 0.045, 90, 450, 12))
    S.append(arc(0.58, 0.60, 0.022, 0.045, 90, 450, 12))
    S.append(arc(0.5, 0.47, 0.045, 0.055, 0, 360, 14))
    S.append(arc(0.20, 0.42, 0.06, 0.05, 60, 300, 10))
    S.append(arc(0.80, 0.42, 0.06, 0.05, -120, 120, 10))
    return S


def rabbit():
    """うさぎ。長い耳・ほっぺ・前歯。"""
    S = []
    S.append(arc(0.5, 0.42, 0.235, 0.215, 0, 360, 36))
    S.append(arc(0.40, 0.76, 0.065, 0.185, 0, 360, 24))
    S.append(arc(0.60, 0.76, 0.065, 0.185, 0, 360, 24))
    S.append(arc(0.40, 0.76, 0.028, 0.11, 0, 360, 16))
    S.append(arc(0.60, 0.76, 0.028, 0.11, 0, 360, 16))
    S.append(arc(0.42, 0.47, 0.018, 0.018, 0, 360, 10))
    S.append(arc(0.58, 0.47, 0.018, 0.018, 0, 360, 10))
    S.append([(0.5, 0.415), (0.5, 0.39)]
             + arc(0.475, 0.39, 0.025, 0.022, 0, -180, 8))
    S.append(arc(0.525, 0.39, 0.025, 0.022, 180, 360, 8))
    S.append(arc(0.335, 0.385, 0.03, 0.02, 20, 160, 8))
    S.append(arc(0.665, 0.385, 0.03, 0.02, 20, 160, 8))
    S.append([(0.48, 0.352), (0.48, 0.318), (0.52, 0.318), (0.52, 0.352)])
    return S


def penguin():
    """ペンギン。たまご体型とおなか。"""
    S = []
    S.append(arc(0.5, 0.48, 0.27, 0.38, 0, 360, 40))
    S.append(arc(0.5, 0.38, 0.185, 0.24, -25, 205, 26))
    S.append(arc(0.41, 0.66, 0.02, 0.02, 0, 360, 10))
    S.append(arc(0.59, 0.66, 0.02, 0.02, 0, 360, 10))
    S.append([(0.455, 0.585), (0.5, 0.615), (0.545, 0.585),
              (0.5, 0.555), (0.455, 0.585)])
    S.append(arc(0.205, 0.44, 0.075, 0.17, 60, 285, 14))
    S.append(arc(0.795, 0.44, 0.075, 0.17, -105, 120, 14))
    S.append(arc(0.40, 0.095, 0.06, 0.035, 180, 360, 8))
    S.append(arc(0.60, 0.095, 0.06, 0.035, 180, 360, 8))
    return S


CHARACTERS = {
    'cat':     (cat,         'お座り猫(要サーボ)'),
    'cat1':    (cat_oneline, '一筆書き猫(サーボ不要)'),
    'ghost':   (ghost,       'おばけ(要サーボ)'),
    'rabbit':  (rabbit,      'うさぎ(要サーボ)'),
    'penguin': (penguin,     'ペンギン(要サーボ)'),
}

# ============================================================
# 座標変換・情報表示
# ============================================================

def to_machine(strokes, size, cx, y_bottom, aspect=0.85):
    """単位座標 -> 機械座標(y下向き)。size=高さmm, cx=中心X, y_bottom=足元"""
    w = size * aspect
    return [[(cx + (x - 0.5) * w, y_bottom - y * size) for x, y in s]
            for s in strokes]


def bounds(strokes):
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    return min(xs), min(ys), max(xs), max(ys)


def path_stats(strokes):
    """描画長・移動長・所要時間の見積り"""
    draw = sum(math.dist(s[i], s[i + 1])
               for s in strokes for i in range(len(s) - 1))
    move, prev = 0.0, None
    for s in strokes:
        if prev is not None:
            move += math.dist(prev, s[0])
        prev = s[-1]
    t = draw / FEED_DRAW + move / FEED_MOVE + len(strokes) * 0.8
    return draw, move, t


def check_fit(strokes, name):
    x0, y0, x1, y1 = bounds(strokes)
    print(f'{name}: X {x0:.0f}〜{x1:.0f} / Y {y0:.0f}〜{y1:.0f} mm')
    ok = (x0 >= AREA_X_MIN and x1 <= AREA_X_MAX and
          y0 >= AREA_Y_MIN and y1 <= AREA_Y_MAX)
    if not ok:
        print('⚠️ 描画エリア外にはみ出します。--size / --x / --y を調整してください',
              file=sys.stderr)
    return ok


def draw(p, strokes):
    for s in strokes:
        p.jump_to(*s[0])
        for pt in s[1:]:
            p.line_to(*pt)

# ============================================================
# CLI
# ============================================================

def main():
    names = sorted(CHARACTERS) + ['all', 'list']
    ap = argparse.ArgumentParser(
        description='ホワイトボードにかわいいキャラクターを描く')
    ap.add_argument('char', choices=names, help='キャラ名 / all / list')
    ap.add_argument('--size', type=float, default=180.0, help='高さ[mm]')
    ap.add_argument('--x', type=float, default=None, help='中心X[mm]')
    ap.add_argument('--y', type=float, default=None, help='足元Y[mm]')
    ap.add_argument('--aspect', type=float, default=0.85,
                    help='横/縦比。較正前に細長く出る場合の応急補正')
    ap.add_argument('--dry', action='store_true', help='GPIOを使わない')
    ap.add_argument('--svg', default=None, help='プレビューSVGの出力先')
    a = ap.parse_args()

    if a.char == 'list':
        for k, (_, desc) in sorted(CHARACTERS.items()):
            print(f'  {k:8} {desc}')
        return

    y_bottom = a.y if a.y is not None else AREA_Y_MAX - 15

    # ---- ストロークを組み立て ----
    if a.char == 'all':
        members = ['cat', 'rabbit', 'penguin', 'ghost']
        n = len(members)
        span = AREA_X_MAX - AREA_X_MIN
        pitch = span / n
        size = min(a.size, pitch / a.aspect * 0.9)
        strokes = []
        for i, name in enumerate(members):
            cx = AREA_X_MIN + pitch * (i + 0.5)
            strokes += to_machine(CHARACTERS[name][0](), size, cx,
                                  y_bottom, a.aspect)
        label = f'all({size:.0f}mm)'
    else:
        cx = a.x if a.x is not None else (AREA_X_MIN + AREA_X_MAX) / 2
        strokes = to_machine(CHARACTERS[a.char][0](), a.size, cx,
                             y_bottom, a.aspect)
        label = a.char

    if not check_fit(strokes, label):
        sys.exit(1)
    d, m, t = path_stats(strokes)
    print(f'描画 {d/1000:.2f}m / 空移動 {m/1000:.2f}m / 約{t/60:.1f}分')

    # ---- 実行 ----
    io = DummyIO() if a.dry else LgpioIO()
    p = Plotter(io)
    try:
        draw(p, strokes)
        p.finish()
    except KeyboardInterrupt:
        print('\n中断: ペンを上げて終了します', file=sys.stderr)
        p.pen_up()
        io.cleanup()

    if a.dry and a.svg:
        write_svg(a.svg, strokes)
        print(f'プレビュー: {a.svg}')


if __name__ == '__main__':
    main()