import time
import lgpio

STEP_PIN = 20
DIR_PIN = 21
EN_PIN = 16

# 低音中心。モーター/机の共振点探し用
TEST_FREQS = [
    80,
    90,
    100,
    110,
    120,
    130.81,   # C3
    146.83,   # D3
    164.81,   # E3
    174.61,   # F3
    196.00,   # G3
    220.00,   # A3
    246.94,   # B3
    261.63,   # C4
    300,
    400,
    500,
    600
]

DURATION = 2.0
STEPS_BEFORE_REVERSE = 120

h = lgpio.gpiochip_open(0)

lgpio.gpio_claim_output(h, STEP_PIN, 0)
lgpio.gpio_claim_output(h, DIR_PIN, 0)
lgpio.gpio_claim_output(h, EN_PIN, 1)

direction = 0


def play_tone(freq, duration):
    global direction

    half_period = 1.0 / (2.0 * freq)
    end_time = time.monotonic() + duration
    steps = 0

    while time.monotonic() < end_time:
        lgpio.gpio_write(h, STEP_PIN, 1)
        time.sleep(half_period)

        lgpio.gpio_write(h, STEP_PIN, 0)
        time.sleep(half_period)

        steps += 1

        # 一方向へ走り続けないように往復
        if steps >= STEPS_BEFORE_REVERSE:
            direction ^= 1
            lgpio.gpio_write(h, DIR_PIN, direction)
            steps = 0


try:
    # TMC2209 enable = LOW
    lgpio.gpio_write(h, EN_PIN, 0)

    for freq in TEST_FREQS:
        print(f"Playing {freq:.2f} Hz")
        play_tone(freq, DURATION)
        time.sleep(0.5)

finally:
    lgpio.gpio_write(h, EN_PIN, 1)
    lgpio.gpiochip_close(h)