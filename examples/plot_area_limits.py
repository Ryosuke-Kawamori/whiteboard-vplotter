#!/usr/bin/env python3
"""ホワイトボードの安全描画領域を矩形でプロットする。"""

import argparse
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / 'firmware'))

from vplotter import (
    AREA_X_MAX,
    AREA_X_MIN,
    AREA_Y_MAX,
    AREA_Y_MIN,
    LgpioIO,
    Plotter,
)

from examples.image_to_svg import write_board_preview


def limit_strokes(inset=0.0):
    if inset < 0:
        raise ValueError('--inset は 0 以上にしてください')
    x0, x1 = AREA_X_MIN + inset, AREA_X_MAX - inset
    y0, y1 = AREA_Y_MIN + inset, AREA_Y_MAX - inset
    if x0 >= x1 or y0 >= y1:
        raise ValueError('--inset が描画領域に対して大きすぎます')
    return [[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]


def main():
    parser = argparse.ArgumentParser(description='安全描画領域の限界を矩形でプロットする')
    parser.add_argument('--inset', type=float, default=0.0,
                        help='限界から内側へ寄せる距離[mm]')
    parser.add_argument('--svg', default='area_limits.svg',
                        help='盤面プレビューSVGの出力先')
    parser.add_argument('--draw', action='store_true',
                        help='GPIOを使って実際に限界矩形を描く')
    args = parser.parse_args()

    try:
        strokes = limit_strokes(args.inset)
    except ValueError as error:
        parser.error(str(error))

    write_board_preview(args.svg, strokes)
    width = AREA_X_MAX - AREA_X_MIN
    height = AREA_Y_MAX - AREA_Y_MIN
    print(f'描画領域: X={AREA_X_MIN:.0f}..{AREA_X_MAX:.0f} mm '
          f'({width:.0f} mm) / Y={AREA_Y_MIN:.0f}..{AREA_Y_MAX:.0f} mm '
          f'({height:.0f} mm)')
    print(f'プレビュー: {args.svg}')
    if not args.draw:
        print('実際に描く場合は、ペン位置をHOMEへ合わせて --draw を追加してください。')
        return

    plotter = Plotter(LgpioIO())
    try:
        for stroke in strokes:
            plotter.jump_to(*stroke[0])
            for point in stroke[1:]:
                plotter.line_to(*point)
        plotter.finish()
    except KeyboardInterrupt:
        print('\n中断しました', file=sys.stderr)
        plotter.pen_up()
        plotter.io.cleanup()


if __name__ == '__main__':
    main()