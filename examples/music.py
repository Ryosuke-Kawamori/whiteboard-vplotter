import time
import lgpio

STEP_PIN = 23
DIR_PIN = 24
EN_PIN = 25

NOTES = {
    "C4": 261.63,
    "D4": 293.66,
    "E4": 329.63,
    "F4": 349.23,
    "G4": 392.00,
    "A4": 440.00,
    "B4": 493.88,
    "C5": 523.25,
}

MELODY = [
    ("C4", 0.4),
    ("D4", 0.4),
    ("E4", 0.4),
    ("F4", 0.4),
    ("G4", 0.8),
    ("G4", 0.8),

    ("A4", 0.4),
    ("A4", 0.4),
    ("A4", 0.4),
    ("A4", 0.4),
    ("G4", 1.2),
]

h = lgpio.gpiochip_open(0)

lgpio.gpio_claim_output(h, STEP_PIN, 0)
lgpio.gpio_claim_output(h, DIR_PIN, 0)
lgpio.gpio_claim_output(h, EN_PIN, 1)

direction = 0

def play_note(freq, duration):
    global direction

    half_period = 1.0 / (2.0 * freq)
    end_time = time.monotonic() + duration

    pulses = 0

    while time.monotonic() < end_time:
        lgpio.gpio_write(h, STEP_PIN, 1)
        time.sleep(half_period)

        lgpio.gpio_write(h, STEP_PIN, 0)
        time.sleep(half_period)

        pulses += 1

        # 軸が一方向へ行き続けないように往復させる
        if pulses >= 20:
            direction ^= 1
            lgpio.gpio_write(h, DIR_PIN, direction)
            pulses = 0


try:
    # TMC2209 enable = LOW
    lgpio.gpio_write(h, EN_PIN, 0)

    for note, duration in MELODY:
        play_note(NOTES[note], duration)
        time.sleep(0.05)

finally:
    lgpio.gpio_write(h, EN_PIN, 1)
    lgpio.gpiochip_close(h)