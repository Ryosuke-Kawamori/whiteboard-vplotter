#!/usr/bin/env python3
"""サーボだけを滑らかに往復させる実機テスト。"""

import argparse
import pathlib
import sys
import time


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'firmware'))

from vplotter import PIN_SERVO, Plotter


class ServoOnlyIO:
    def __init__(self):
        import lgpio

        self.lg = lgpio
        self.h = lgpio.gpiochip_open(0)
        self.servo_active = False
        lgpio.gpio_claim_output(self.h, PIN_SERVO, 0)

    def setup(self):
        pass

    def write(self, pin, val):
        pass

    def pulse(self, left, right):
        pass

    def servo(self, us):
        us = int(us)
        if us == 0:
            if self.servo_active:
                self.lg.tx_pwm(self.h, PIN_SERVO, 0, 0)
                self.servo_active = False
            return
        self.lg.tx_servo(self.h, PIN_SERVO, us, 50)
        self.servo_active = True

    def cleanup(self):
        self.servo(0)
        self.lg.gpiochip_close(self.h)


def main():
    parser = argparse.ArgumentParser(description='サーボのスムーズ移動を実機で確認する')
    parser.add_argument('--cycles', type=int, default=2, help='DOWN/UPの往復回数')
    parser.add_argument('--hold', type=float, default=0.5, help='各位置での停止時間 [s]')
    args = parser.parse_args()

    io = ServoOnlyIO()
    plotter = Plotter(io)
    try:
        for cycle in range(1, max(0, args.cycles) + 1):
            print(f'{cycle}/{args.cycles}: PEN DOWN')
            plotter.pen_down()
            time.sleep(max(0.0, args.hold))
            print(f'{cycle}/{args.cycles}: PEN UP')
            plotter.pen_up()
            time.sleep(max(0.0, args.hold))
    except KeyboardInterrupt:
        print('\n停止します')
    finally:
        plotter.pen_up()
        io.cleanup()


if __name__ == '__main__':
    main()