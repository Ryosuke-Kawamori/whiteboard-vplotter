#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vplotter.py -- ホワイトボード用 V-Plotter (ポーラーグラフ) コントローラ
Raspberry Pi + A4988/DRV8825/TMC2209 x2 + SG90サーボ

座標系:
    原点 = 左モーター軸
    X = 右方向 (+)
    Y = 下方向 (+)      ← 重力方向。ポーラーグラフは Y が下向きの方が扱いやすい

使い方:
    python3 vplotter.py text "HELLO WORLD" --size 80
    python3 vplotter.py gcode drawing.gcode
    python3 vplotter.py home
    python3 vplotter.py text "TEST" --dry --svg preview.svg   # PC上で動作確認
"""

import argparse
import math
import re
import sys
import time

# ============================================================
# 1. 機体設定 --- ここを自分の機体に合わせて必ず調整する
# ============================================================

MOTOR_SPACING = 1300.0   # [mm] 左右モーターのプーリー軸間の距離
HOME_X        = MOTOR_SPACING / 2.0
HOME_Y        = 450.0    # [mm] 電源投入時にペン先を置く位置(モーター軸ラインからの距離)

# 描画可能エリア (安全のためのソフトリミット)
AREA_X_MIN, AREA_X_MAX = 150.0, MOTOR_SPACING - 150.0
AREA_Y_MIN, AREA_Y_MAX = 200.0, 950.0

# ベルト/モーター
PULLEY_TEETH  = 20       # GT2プーリーの歯数
BELT_PITCH    = 2.0      # [mm] GT2 = 2.0
STEPS_PER_REV = 200      # 1.8°モーター
MICROSTEP     = 8        # ドライバのマイクロステップ設定 (1/8推奨)
MM_PER_STEP   = (PULLEY_TEETH * BELT_PITCH) / (STEPS_PER_REV * MICROSTEP)  # = 0.025 mm

INVERT_LEFT   = False    # 動作方向が逆なら True にする
INVERT_RIGHT  = True

# 速度
FEED_DRAW = 22.0         # [mm/s] 描画中
FEED_MOVE = 40.0         # [mm/s] ペンアップ移動中
SEG_LEN   = 1.0          # [mm] 直線を分割する長さ(小さいほど正確・遅い)

# GPIO (BCM番号)
PIN_L_STEP, PIN_L_DIR = 20, 21
PIN_R_STEP, PIN_R_DIR = 19, 26
PIN_ENABLE            = 16     # ドライバのEN (LOWで有効)
PIN_SERVO             = 18

SERVO_UP_US   = 1150     # ペンを離す
SERVO_DOWN_US = 1750     # ペンを押しつける
SERVO_WAIT    = 0.35     # [s] サーボ動作待ち

PULSE_US = 3e-6          # STEPパルス幅

try:
    from config import *    # ← 定数定義の「後」ならOK（上書きする）
except ImportError:
    pass
    
# ============================================================
# 2. GPIOバックエンド (lgpio / ダミー)
# ============================================================

class DummyIO:
    """PC上での動作確認用。GPIOを叩かず軌跡だけ記録する。"""
    def __init__(self):
        self.path = []      # [(x, y, pen_down)]
    def setup(self): pass
    def write(self, pin, val): pass
    def pulse(self, left, right): pass
    def servo(self, us): pass
    def cleanup(self): pass


class LgpioIO:
    def __init__(self):
        import lgpio
        self.lg = lgpio
        self.h = lgpio.gpiochip_open(0)
        for p in (PIN_L_STEP, PIN_L_DIR, PIN_R_STEP, PIN_R_DIR, PIN_ENABLE):
            lgpio.gpio_claim_output(self.h, p, 0)
        lgpio.gpio_claim_output(self.h, PIN_SERVO, 0)

    def setup(self):
        self.lg.gpio_write(self.h, PIN_ENABLE, 0)   # ドライバ有効化

    def write(self, pin, val):
        self.lg.gpio_write(self.h, pin, val)

    def pulse(self, left, right):
        """左右のSTEPを同時に立ち上げる"""
        if left:
            self.lg.gpio_write(self.h, PIN_L_STEP, 1)
        if right:
            self.lg.gpio_write(self.h, PIN_R_STEP, 1)
        t = time.perf_counter() + PULSE_US
        while time.perf_counter() < t:
            pass
        if left:
            self.lg.gpio_write(self.h, PIN_L_STEP, 0)
        if right:
            self.lg.gpio_write(self.h, PIN_R_STEP, 0)

    def servo(self, us):
        self.lg.tx_servo(self.h, PIN_SERVO, int(us), 50)

    def cleanup(self):
        self.lg.tx_servo(self.h, PIN_SERVO, 0, 50)
        self.lg.gpio_write(self.h, PIN_ENABLE, 1)
        self.lg.gpiochip_close(self.h)


# ============================================================
# 3. プロッタ本体
# ============================================================

class Plotter:
    def __init__(self, io):
        self.io = io
        self.dry = isinstance(io, DummyIO)
        self.x, self.y = HOME_X, HOME_Y
        self.sl, self.sr = self._ik_steps(self.x, self.y)
        self.pen = False
        io.setup()
        self.pen_up()

    # --- 逆運動学 ---
    @staticmethod
    def _lengths(x, y):
        l = math.hypot(x, y)
        r = math.hypot(MOTOR_SPACING - x, y)
        return l, r

    @staticmethod
    def _ik_steps(x, y):
        l, r = Plotter._lengths(x, y)
        return round(l / MM_PER_STEP), round(r / MM_PER_STEP)

    # --- ペン ---
    def pen_down(self):
        if not self.pen:
            self.io.servo(SERVO_DOWN_US)
            time.sleep(0 if self.dry else SERVO_WAIT)
            self.pen = True

    def pen_up(self):
        if self.pen or self.pen is False:
            self.io.servo(SERVO_UP_US)
            time.sleep(0 if self.dry else SERVO_WAIT)
            self.pen = False

    # --- 低レベル: 目標ステップ数まで両モーターを同期して回す ---
    def _run(self, tl, tr, duration):
        dl, dr = tl - self.sl, tr - self.sr
        if dl == 0 and dr == 0:
            return
        dir_l = 1 if dl > 0 else -1
        dir_r = 1 if dr > 0 else -1
        self.io.write(PIN_L_DIR, 1 if (dir_l > 0) ^ INVERT_LEFT else 0)
        self.io.write(PIN_R_DIR, 1 if (dir_r > 0) ^ INVERT_RIGHT else 0)

        a, b = abs(dl), abs(dr)
        n = max(a, b)
        delay = max(duration, 1e-6) / n
        t0 = time.perf_counter()
        ca = cb = 0
        for i in range(1, n + 1):
            na, nb = a * i // n, b * i // n
            self.io.pulse(na > ca, nb > cb)
            ca, cb = na, nb
            if not self.dry:
                tgt = t0 + i * delay
                rem = tgt - time.perf_counter()
                if rem > 0.0015:
                    time.sleep(rem - 0.001)
                while time.perf_counter() < tgt:
                    pass
        self.sl, self.sr = tl, tr

    # --- 直線補間 ---
    def move_to(self, x, y):
        x = min(max(x, AREA_X_MIN), AREA_X_MAX)
        y = min(max(y, AREA_Y_MIN), AREA_Y_MAX)
        x0, y0 = self.x, self.y
        dist = math.hypot(x - x0, y - y0)
        if dist < 1e-4:
            return
        feed = FEED_DRAW if self.pen else FEED_MOVE
        steps = max(1, int(dist / SEG_LEN))
        seg_t = (dist / feed) / steps
        for i in range(1, steps + 1):
            px = x0 + (x - x0) * i / steps
            py = y0 + (y - y0) * i / steps
            tl, tr = self._ik_steps(px, py)
            self._run(tl, tr, seg_t)
        self.x, self.y = x, y
        if self.dry:
            self.io.path.append((x, y, self.pen))

    def line_to(self, x, y):
        self.pen_down()
        self.move_to(x, y)

    def jump_to(self, x, y):
        self.pen_up()
        self.move_to(x, y)
        if self.dry:
            self.io.path.append((x, y, False))

    def home(self):
        self.pen_up()
        self.move_to(HOME_X, HOME_Y)

    def finish(self):
        self.pen_up()
        self.home()
        self.io.cleanup()


# ============================================================
# 4. 1ストロークフォント (0..1 正規化, y上向き)
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
    'G': [[(1,.82),(.78,1),(.22,1),(0,.8),(0,.2),(.22,0),(.78,0),(1,.2),(1,.45),(.55,.45)]],
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

CHAR_W_RATIO = 0.62      # 文字幅 = size * この比率
GAP_RATIO    = 0.28      # 字間


def text_strokes(text, size, x0, y_baseline, line_gap=1.6):
    """文字列 -> [[(x,y),...], ...] (機械座標, y下向き)"""
    out = []
    cw = size * CHAR_W_RATIO
    adv = cw + size * GAP_RATIO
    cx, cy = x0, y_baseline
    for ch in text.upper():
        if ch == '\n':
            cx, cy = x0, cy + size * line_gap
            continue
        glyph = FONT.get(ch)
        if glyph is None:
            cx += adv
            continue
        for stroke in glyph:
            out.append([(cx + fx * cw, cy - fy * size) for fx, fy in stroke])
        cx += adv
    return out


# ============================================================
# 5. G-code読み込み (G0/G1 + Z または M3/M5 でペン制御)
# ============================================================

GC = re.compile(r'([GMXYZFS])\s*(-?\d*\.?\d+)', re.I)


def run_gcode(p, path, offset=(0.0, 0.0), scale=1.0):
    ox, oy = offset
    cx, cy = p.x, p.y
    with open(path, encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.split(';')[0].strip()
            if not line:
                continue
            w = dict()
            for k, v in GC.findall(line):
                w.setdefault(k.upper(), float(v))
            cmd = w.get('G', w.get('M'))
            if 'M' in w and w['M'] in (3, 5):
                p.pen_down() if w['M'] == 3 else p.pen_up()
                continue
            if 'G' not in w or w['G'] not in (0, 1):
                continue
            if 'Z' in w:
                p.pen_down() if w['Z'] < 0 else p.pen_up()
            nx = ox + w['X'] * scale if 'X' in w else cx
            ny = oy + w['Y'] * scale if 'Y' in w else cy
            if w['G'] == 0:
                p.jump_to(nx, ny)
            else:
                p.line_to(nx, ny)
            cx, cy = nx, ny


# ============================================================
# 6. プレビューSVG出力 (--dry 用)
# ============================================================

def write_svg(path, strokes):
    w, h = MOTOR_SPACING, AREA_Y_MAX + 60
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w/2:.0f}" '
             f'height="{h/2:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">',
             f'<rect width="{w:.0f}" height="{h:.0f}" fill="#fff"/>',
             f'<rect x="{AREA_X_MIN}" y="{AREA_Y_MIN}" '
             f'width="{AREA_X_MAX-AREA_X_MIN}" height="{AREA_Y_MAX-AREA_Y_MIN}" '
             f'fill="none" stroke="#ddd" stroke-dasharray="8 8"/>']
    for s in strokes:
        d = 'M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x, y in s)
        parts.append(f'<path d="{d}" fill="none" stroke="#111" stroke-width="2.5" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append('</svg>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))


# ============================================================
# 7. CLI
# ============================================================

def main():
    ap = argparse.ArgumentParser(description='ホワイトボード V-Plotter')
    ap.add_argument('mode', choices=['text', 'gcode', 'home', 'jog'])
    ap.add_argument('arg', nargs='?', default='')
    ap.add_argument('--size', type=float, default=70.0, help='文字の高さ[mm]')
    ap.add_argument('--x', type=float, default=None, help='開始X[mm]')
    ap.add_argument('--y', type=float, default=None, help='ベースラインY[mm]')
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--dry', action='store_true', help='GPIOを使わず動作確認')
    ap.add_argument('--svg', default=None, help='--dry時のプレビュー出力先')
    a = ap.parse_args()

    io = DummyIO() if a.dry else LgpioIO()
    p = Plotter(io)
    strokes = []

    try:
        if a.mode == 'home':
            p.home()

        elif a.mode == 'jog':
            xs, ys = a.arg.split(',')
            p.jump_to(float(xs), float(ys))

        elif a.mode == 'text':
            x0 = a.x if a.x is not None else AREA_X_MIN + 30
            y0 = a.y if a.y is not None else AREA_Y_MIN + a.size + 40
            strokes = text_strokes(a.arg, a.size, x0, y0)
            for s in strokes:
                p.jump_to(*s[0])
                for pt in s[1:]:
                    p.line_to(*pt)
            p.pen_up()

        elif a.mode == 'gcode':
            ox = a.x if a.x is not None else AREA_X_MIN
            oy = a.y if a.y is not None else AREA_Y_MIN
            run_gcode(p, a.arg, offset=(ox, oy), scale=a.scale)

        p.finish()
    except KeyboardInterrupt:
        print('\n中断しました', file=sys.stderr)
        p.pen_up()
        io.cleanup()

    if a.dry and a.svg and strokes:
        write_svg(a.svg, strokes)
        print(f'プレビューを書き出しました: {a.svg}')
    if a.dry:
        print(f'MM_PER_STEP = {MM_PER_STEP:.4f} mm  '
              f'(分解能 {1/MM_PER_STEP:.0f} step/mm)')


if __name__ == '__main__':
    main()
