#!/usr/bin/env python3
"""ペンを上げたまま、左右モーターの割当てと回転方向を確認する。"""

import argparse
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / 'firmware'))

from vplotter import DummyIO, HOME_X, HOME_Y, LgpioIO, Plotter


def main():
	parser = argparse.ArgumentParser(description='ペンを上げたままXY方向を確認する')
	parser.add_argument('--distance', type=float, default=30.0,
						help='確認移動量[mm]')
	parser.add_argument('--dry', action='store_true', help='GPIOを使わず動作確認')
	args = parser.parse_args()
	if not 1 <= args.distance <= 50:
		parser.error('--distance は安全のため 1〜50 mm にしてください')

	print(f'開始前にペンを外し、ゴンドラを HOME ({HOME_X:.0f}, {HOME_Y:.0f}) mm '
		  'へ置いてください。')
	io = DummyIO() if args.dry else LgpioIO()
	plotter = Plotter(io)
	try:
		print(f'X確認: 約{args.distance:.0f} mm右へ動き、元へ戻るのが正常です')
		plotter.jump_to(HOME_X + args.distance, HOME_Y)
		plotter.jump_to(HOME_X, HOME_Y)

		print(f'Y確認: 約{args.distance:.0f} mm下へ動き、元へ戻るのが正常です')
		plotter.jump_to(HOME_X, HOME_Y + args.distance)
		plotter.finish()
	except KeyboardInterrupt:
		print('\n中断しました。モーターを停止します。', file=sys.stderr)
		plotter.pen_up()
		io.cleanup()


if __name__ == '__main__':
	main()