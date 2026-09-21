#!/usr/bin/env python3
"""左右のモーターを個別に少量だけ動かす配線診断。"""

import argparse
import pathlib
import sys
import time

import lgpio

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / 'firmware'))

from vplotter import (
    PIN_ENABLE,
    PIN_L_DIR,
    PIN_L_STEP,
    PIN_R_DIR,
    PIN_R_STEP,
)


def main():
    parser = argparse.ArgumentParser(description='モーターを個別に動かす配線診断')
    parser.add_argument('motor', choices=('left', 'right'), help='確認するモーター')
    parser.add_argument('--steps', type=int, default=100, help='パルス数（既定: 100）')
    parser.add_argument('--reverse', action='store_true', help='逆方向へ回す')
    args = parser.parse_args()
    if not 1 <= args.steps <= 400:
        parser.error('--steps は安全のため 1〜400 にしてください')

    step_pin, direction_pin = {
        'left': (PIN_L_STEP, PIN_L_DIR),
        'right': (PIN_R_STEP, PIN_R_DIR),
    }[args.motor]

    handle = lgpio.gpiochip_open(0)
    try:
        for pin in (PIN_L_STEP, PIN_L_DIR, PIN_R_STEP, PIN_R_DIR, PIN_ENABLE):
            lgpio.gpio_claim_output(handle, pin, 0)
        lgpio.gpio_write(handle, PIN_ENABLE, 0)
        lgpio.gpio_write(handle, direction_pin, int(not args.reverse))
        print(f'{args.motor}: {args.steps} steps '
              f'({"reverse" if args.reverse else "forward"})')
        for _ in range(args.steps):
            lgpio.gpio_write(handle, step_pin, 1)
            time.sleep(0.002)
            lgpio.gpio_write(handle, step_pin, 0)
            time.sleep(0.002)
    finally:
        lgpio.gpio_write(handle, PIN_ENABLE, 1)
        lgpio.gpiochip_close(handle)


if __name__ == '__main__':
    main()