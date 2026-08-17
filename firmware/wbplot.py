#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wbplot.py -- ホワイトボードV-Plotter用 G-code ジェネレータ / センダ
対象: BIGTREETECH SKR Pico + Marlin 2.1.3+ (POLARGRAPH)

逆運動学(ベルト長計算)は Marlin 側が行うので、本スクリプトは
デカルト座標のまま G0/G1 を出力する。

使い方:
  python3 wbplot.py text "MTG 10:00" --size 90 --out out.gcode --svg preview.svg
  python3 wbplot.py text "HELLO" --port /dev/ttyACM0
  python3 wbplot.py svgpath drawing.svg --out out.gcode      # SVGのpath(直線化済)
"""

import argparse
import math
import re
import sys
import time

# ============================================================
# 機体ジオメトリ  --- Marlin の Configuration.h と必ず一致させる
# ============================================================

GEOM = dict(
    # Marlin の座標系での描画可能範囲 [mm]
    # 1800x900 ホワイトボード / 脚付きスタンド / モーター間 1900mm 想定
    X_MIN=250.0, X_MAX=1650.0,
    Y_MIN=380.0, Y_MAX=920.0,

    # 待機位置（描画前後に戻る場所）
    PARK_X=950.0, PARK_Y=650.0,
)

FEED_DRAW = 1200      # [mm/min] 描画中 = 20mm/s
FEED_MOVE = 2400      # [mm/min] ペンアップ移動 = 40mm/s

# ペン昇降サーボ (Marlin: M280 P0 S<角度>)
SERVO_INDEX = 0
ANGLE_UP    = 30
ANGLE_DOWN  = 85
SERVO_DWELL = 300     # [ms] サーボ動作待ち


# ============================================================
# 1ストロークフォント (0..1 正規化, y上向き)
# ============================================================

FONT = {
    ' ': [],
    'A': [[(0,0),(.5,1),(1,0)], [(.18,.35),(.82,.35)]],
    'B': [[(0,0),(0,1),(.7,1),(.92,.85),(.92,.65),(.7,.52),(0,.52)],
          [(.7,.52),(.98,.36),(.98,.15),(.72,0),(0,0)]],
    'C': [[(1,.82),(.78,1),(.22,1),(0,.8),(0,.2),(.22,0),(.78,0),(1,.18)]],
    'D': [[(0,0),(0,1),(.62,1),(.92,.72),(.92,.28),(.62,0),(0,0)]],
    'E': [[(1,1),(0,1),(0,0),(1,0)], [(0,.5),(.75,.5)]],
    'F': [[(1,1),(0,1),(0,0)], [(0,.52),(.75,.52)]],
    'G': [[(1,.82),(.78,1),(.22,1),(0,.8),(0,.2),(.78,0),(1,.2),(1,.45),(.55,.45)]],
    'H': [[(0,0),(0,1)], [(1,0),(1,1)], [(0,.5),(1,.5)]],
    'I': [[(.2,1),(.8,1)], [(.5,1),(.5,0)], [(.2,0),(.8,0)]],
    'J': [[(.85,1),(.85,.22),(.62,0),(.22,0),(0,.22)]],
    'K': [[(0,0),(0,1)], [(1,1),(0,.45)], [(.35,.63),(1,0)]],
    'L': [[(0,1),(0,0),(1,0)]],
    'M': [[(0,0),(0,1),(.5,.38),(1,1),(1,0)]],
    'N': [[(0,0),(0,1),(1,0),(1,1)]],
    'O': [[(.22,0),(.78,0),(1,.2),(1,.8),(.78,1),(.22,1),(0,.8),(0,.2),(.22,0)]],
    'P': [[(0,0),(0,1),(.72,1),(.96,.82),(.96,.62),(.72,.45),(0,.45)]],
    'Q': [[(.22,0),(.78,0),(1,.2),(1,.8),(.78,1),(.22,1),(0,.8),(0,.2),(.22,0)],
          [(.62,.26),(1,0)]],
    'R': [[(0,0),(0,1),(.72,1),(.96,.82),(.96,.62),(.72,.45),(0,.45)], [(.45,.45),(1,0)]],
    'S': [[(1,.85),(.75,1),(.25,1),(0,.85),(0,.63),(.2,.5),(.8,.5),(1,.37),(1,.15),
           (.75,0),(.25,0),(0,.15)]],
    'T': [[(0,1),(1,1)], [(.5,1),(.5,0)]],
    'U': [[(0,1),(0,.2),(.22,0),(.78,0),(1,.2),(1,1)]],
    'V': [[(0,1),(.5,0),(1,1)]],
    'W': [[(0,1),(.25,0),(.5,.6),(.75,0),(1,1)]],
    'X': [[(0,0),(1,1)], [(0,1),(1,0)]],
    'Y': [[(0,1),(.5,.5),(1,1)], [(.5,.5),(.5,0)]],
    'Z': [[(0,1),(1,1),(0,0),(1,0)]],
    '0': [[(.22,0),(.78,0),(1,.2),(1,.8),(.78,1),(.22,1),(0,.8),(0,.2),(.22,0)],
          [(.15,.25),(.85,.75)]],
    '1': [[(.15,.78),(.5,1),(.5,0)], [(.18,0),(.82,0)]],
    '2': [[(0,.82),(.25,1),(.75,1),(1,.82),(1,.62),(0,.15),(0,0),(1,0)]],
    '3': [[(0,1),(1,1),(.45,.56)],
          [(.45,.56),(.8,.56),(1,.4),(1,.15),(.75,0),(.25,0),(0,.15)]],
    '4': [[(.78,0),(.78,1),(0,.3),(1,.3)]],
    '5': [[(1,1),(0,1),(0,.56),(.75,.56),(1,.4),(1,.15),(.75,0),(.25,0),(0,.15)]],
    '6': [[(1,.85),(.75,1),(.25,1),(0,.8),(0,.2),(.22,0),(.78,0),(1,.2),(1,.38),
           (.78,.56),(.22,.56),(0,.38)]],
    '7': [[(0,1),(1,1),(.35,0)]],
    '8': [[(.25,.56),(0,.7),(0,.86),(.25,1),(.75,1),(1,.86),(1,.7),(.75,.56),
           (.25,.56),(0,.4),(0,.15),(.25,0),(.75,0),(1,.15),(1,.4),(.75,.56)]],
    '9': [[(0,.15),(.25,0),(.75,0),(1,.2),(1,.8),(.78,1),(.22,1),(0,.8),(0,.62),
           (.22,.45),(.78,.45),(1,.62)]],
    '.': [[(.42,0),(.58,0)]],
    ',': [[(.55,.08),(.38,-.12)]],
    '-': [[(.1,.5),(.9,.5)]],
    '+': [[(.1,.5),(.9,.5)], [(.5,.14),(.5,.86)]],
    '=': [[(.1,.36),(.9,.36)], [(.1,.64),(.9,.64)]],
    ':': [[(.42,.24),(.58,.24)], [(.42,.72),(.58,.72)]],
    '!': [[(.5,1),(.5,.28)], [(.5,0),(.5,.08)]],
    '?': [[(0,.8),(.22,1),(.78,1),(1,.8),(1,.64),(.5,.4),(.5,.26)], [(.5,0),(.5,.08)]],
    '/': [[(0,0),(1,1)]],
    '(': [[(.7,1),(.35,.7),(.35,.3),(.7,0)]],
    ')': [[(.3,1),(.65,.7),(.65,.3),(.3,0)]],
    '*': [[(.5,.3),(.5,.9)], [(.2,.45),(.8,.75)], [(.8,.45),(.2,.75)]],
    '#': [[(.28,0),(.38,1)], [(.62,0),(.72,1)], [(.12,.35),(.88,.35)], [(.12,.68),(.88,.68)]],
}

CHAR_W_RATIO = 0.62
GAP_RATIO    = 0.28
LINE_GAP     = 1.7


def text_strokes(text, size, x0, y_top):
    """文字列 -> ストローク列。Marlin座標(Y上が小さい値)で返す。
    y_top = 1行目の文字の上端 Y"""
    out = []
    cw  = size * CHAR_W_RATIO
    adv = cw + size * GAP_RATIO
    cx, cy_base = x0, y_top + size          # ベースライン(Yは下向きに増える)
    for ch in text.upper():
        if ch == '\n':
            cx, cy_base = x0, cy_base + size * LINE_GAP
            continue
        g = FONT.get(ch)
        if g is None:
            cx += adv
            continue
        for st in g:
            out.append([(cx + fx * cw, cy_base - fy * size) for fx, fy in st])
        cx += adv
    return out


def fit_check(strokes):
    """描画エリアからはみ出していないか確認"""
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    if not xs:
        return None
    bad = []
    if min(xs) < GEOM['X_MIN']: bad.append(f"左に {GEOM['X_MIN']-min(xs):.0f}mm はみ出し")
    if max(xs) > GEOM['X_MAX']: bad.append(f"右に {max(xs)-GEOM['X_MAX']:.0f}mm はみ出し")
    if min(ys) < GEOM['Y_MIN']: bad.append(f"上に {GEOM['Y_MIN']-min(ys):.0f}mm はみ出し")
    if max(ys) > GEOM['Y_MAX']: bad.append(f"下に {max(ys)-GEOM['Y_MAX']:.0f}mm はみ出し")
    return (min(xs), min(ys), max(xs), max(ys)), bad


# ============================================================
# G-code 生成
# ============================================================

def gen_gcode(strokes):
    g = []
    a = g.append
    a('; ---- whiteboard V-plotter (Marlin POLARGRAPH) ----')
    a('G21')                      # mm
    a('G90')                      # 絶対座標
    a(f'M280 P{SERVO_INDEX} S{ANGLE_UP}')
    a(f'G4 P{SERVO_DWELL}')
    a(f'G0 X{GEOM["PARK_X"]:.2f} Y{GEOM["PARK_Y"]:.2f} F{FEED_MOVE}')

    for st in strokes:
        if len(st) < 2:
            continue
        x, y = st[0]
        a(f'G0 X{x:.2f} Y{y:.2f} F{FEED_MOVE}')
        a(f'M280 P{SERVO_INDEX} S{ANGLE_DOWN}')
        a(f'G4 P{SERVO_DWELL}')
        for x, y in st[1:]:
            a(f'G1 X{x:.2f} Y{y:.2f} F{FEED_DRAW}')
        a(f'M280 P{SERVO_INDEX} S{ANGLE_UP}')
        a(f'G4 P{SERVO_DWELL}')

    a(f'G0 X{GEOM["PARK_X"]:.2f} Y{GEOM["PARK_Y"]:.2f} F{FEED_MOVE}')
    a('M400')
    a('; ---- end ----')
    return g


def estimate_time(strokes):
    """おおよその所要時間[s]"""
    t = 0.0
    px, py = GEOM['PARK_X'], GEOM['PARK_Y']
    for st in strokes:
        if len(st) < 2:
            continue
        t += math.dist((px, py), st[0]) / (FEED_MOVE / 60.0)
        t += SERVO_DWELL / 1000.0 * 2
        for i in range(1, len(st)):
            t += math.dist(st[i-1], st[i]) / (FEED_DRAW / 60.0)
        px, py = st[-1]
    return t


# ============================================================
# SVG読み込み (直線/ポリライン化済みの path, polyline のみ)
# ============================================================

def load_svg(path, scale=1.0, ox=None, oy=None):
    ox = GEOM['X_MIN'] if ox is None else ox
    oy = GEOM['Y_MIN'] if oy is None else oy
    src = open(path, encoding='utf-8').read()
    strokes = []

    for d in re.findall(r'\bd\s*=\s*"([^"]+)"', src):
        cur, sub = None, []
        for cmd, args in re.findall(r'([MmLlHhVvZz])([^MmLlHhVvZz]*)', d):
            nums = [float(v) for v in re.findall(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?', args)]
            if cmd in 'Mm':
                if len(sub) > 1:
                    strokes.append(sub)
                sub = []
                for i in range(0, len(nums) - 1, 2):
                    p = (nums[i], nums[i+1])
                    cur = p if cmd == 'M' else (cur[0]+p[0], cur[1]+p[1]) if cur else p
                    sub.append(cur)
            elif cmd in 'Ll':
                for i in range(0, len(nums) - 1, 2):
                    p = (nums[i], nums[i+1])
                    cur = p if cmd == 'L' else (cur[0]+p[0], cur[1]+p[1])
                    sub.append(cur)
            elif cmd in 'HhVv':
                for v in nums:
                    if cmd == 'H':   cur = (v, cur[1])
                    elif cmd == 'h': cur = (cur[0]+v, cur[1])
                    elif cmd == 'V': cur = (cur[0], v)
                    else:            cur = (cur[0], cur[1]+v)
                    sub.append(cur)
            elif cmd in 'Zz' and sub:
                sub.append(sub[0])
        if len(sub) > 1:
            strokes.append(sub)

    for pts in re.findall(r'<pol(?:yline|ygon)[^>]*points\s*=\s*"([^"]+)"', src):
        n = [float(v) for v in re.findall(r'-?\d*\.?\d+', pts)]
        strokes.append([(n[i], n[i+1]) for i in range(0, len(n)-1, 2)])

    return [[(ox + x*scale, oy + y*scale) for x, y in s] for s in strokes]


# ============================================================
# プレビューSVG
# ============================================================

def write_svg(path, strokes):
    W, H = 1900, 1050
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W//2}" height="{H//2}" '
         f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#fafafa"/>',
         f'<rect x="{GEOM["X_MIN"]}" y="{GEOM["Y_MIN"]}" '
         f'width="{GEOM["X_MAX"]-GEOM["X_MIN"]}" height="{GEOM["Y_MAX"]-GEOM["Y_MIN"]}" '
         f'fill="#fff" stroke="#c00" stroke-dasharray="10 10"/>']
    for s in strokes:
        d = 'M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x, y in s)
        p.append(f'<path d="{d}" fill="none" stroke="#111" stroke-width="4" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')
    p.append('</svg>')
    open(path, 'w', encoding='utf-8').write('\n'.join(p))


# ============================================================
# シリアル送信 (ok待ちハンドシェイク)
# ============================================================

def send_serial(lines, port, baud=250000):
    try:
        import serial
    except ImportError:
        sys.exit('pyserial が必要です:  pip install pyserial')

    ser = serial.Serial(port, baud, timeout=30)
    time.sleep(2.0)
    ser.reset_input_buffer()
    total = len(lines)
    try:
        for i, ln in enumerate(lines, 1):
            if ln.startswith(';') or not ln.strip():
                continue
            ser.write((ln + '\n').encode())
            while True:
                r = ser.readline().decode(errors='ignore').strip()
                if not r:
                    print(f'  応答なし: {ln}', file=sys.stderr)
                    break
                if r.lower().startswith('ok'):
                    break
                if r.lower().startswith(('error', '!!')):
                    sys.exit(f'ファーム側エラー: {r}  (行: {ln})')
            if i % 20 == 0:
                print(f'\r  {i}/{total}', end='', flush=True)
        print(f'\r  {total}/{total}  完了')
    except KeyboardInterrupt:
        print('\n中断: ペンを上げます')
        ser.write(f'M280 P{SERVO_INDEX} S{ANGLE_UP}\n'.encode())
    finally:
        ser.close()


# ============================================================
# CLI
# ============================================================

def main():
    ap = argparse.ArgumentParser(description='ホワイトボードV-Plotter G-code生成/送信')
    ap.add_argument('mode', choices=['text', 'svgpath'])
    ap.add_argument('arg')
    ap.add_argument('--size', type=float, default=90.0, help='文字の高さ[mm]')
    ap.add_argument('--x', type=float, default=None)
    ap.add_argument('--y', type=float, default=None)
    ap.add_argument('--scale', type=float, default=1.0, help='svgpath用')
    ap.add_argument('--out', default=None, help='G-code出力先')
    ap.add_argument('--svg', default=None, help='プレビューSVG出力先')
    ap.add_argument('--port', default=None, help='例 /dev/ttyACM0')
    ap.add_argument('--baud', type=int, default=250000)
    a = ap.parse_args()

    if a.mode == 'text':
        x0 = a.x if a.x is not None else GEOM['X_MIN'] + 20
        y0 = a.y if a.y is not None else GEOM['Y_MIN'] + 20
        strokes = text_strokes(a.arg, a.size, x0, y0)
    else:
        strokes = load_svg(a.arg, a.scale, a.x, a.y)

    if not strokes:
        sys.exit('描くものがありません')

    bbox, bad = fit_check(strokes)
    print(f'ストローク数: {len(strokes)}')
    print(f'範囲: X {bbox[0]:.0f}〜{bbox[2]:.0f} / Y {bbox[1]:.0f}〜{bbox[3]:.0f} mm')
    print(f'想定時間: 約 {estimate_time(strokes)/60:.1f} 分')
    if bad:
        print('⚠️  ' + ' / '.join(bad), file=sys.stderr)
        print('   --size を小さくするか --x --y で移動してください', file=sys.stderr)

    g = gen_gcode(strokes)

    if a.svg:
        write_svg(a.svg, strokes)
        print(f'プレビュー: {a.svg}')
    if a.out:
        open(a.out, 'w').write('\n'.join(g) + '\n')
        print(f'G-code: {a.out}  ({len(g)}行)')
    if a.port:
        if bad:
            sys.exit('はみ出しがあるため送信を中止しました')
        print(f'送信中 -> {a.port}')
        send_serial(g, a.port, a.baud)
    if not (a.out or a.svg or a.port):
        print('\n'.join(g))


if __name__ == '__main__':
    main()
