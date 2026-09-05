import time
import lgpio

L_STEP = 20
L_DIR  = 21

R_STEP = 19
R_DIR  = 26

EN = 16

STEP_DELAY = 0.002
STEPS = 800

h = lgpio.gpiochip_open(0)

for pin in (L_STEP, L_DIR, R_STEP, R_DIR, EN):
    lgpio.gpio_claim_output(h, pin, 0)


def pulse(pin, count=STEPS):
    for _ in range(count):
        lgpio.gpio_write(h, pin, 1)
        time.sleep(STEP_DELAY)
        lgpio.gpio_write(h, pin, 0)
        time.sleep(STEP_DELAY)


def pulse_both(count=STEPS):
    for _ in range(count):
        lgpio.gpio_write(h, L_STEP, 1)
        lgpio.gpio_write(h, R_STEP, 1)

        time.sleep(STEP_DELAY)

        lgpio.gpio_write(h, L_STEP, 0)
        lgpio.gpio_write(h, R_STEP, 0)

        time.sleep(STEP_DELAY)


try:
    # TMC2209 enable = LOW
    lgpio.gpio_write(h, EN, 0)

    print("1. Left motor forward")
    lgpio.gpio_write(h, L_DIR, 1)
    pulse(L_STEP)

    time.sleep(1)

    print("2. Left motor reverse")
    lgpio.gpio_write(h, L_DIR, 0)
    pulse(L_STEP)

    time.sleep(1)

    print("3. Right motor forward")
    lgpio.gpio_write(h, R_DIR, 1)
    pulse(R_STEP)

    time.sleep(1)

    print("4. Right motor reverse")
    lgpio.gpio_write(h, R_DIR, 0)
    pulse(R_STEP)

    time.sleep(1)

    print("5. Both motors same direction")
    lgpio.gpio_write(h, L_DIR, 1)
    lgpio.gpio_write(h, R_DIR, 1)
    pulse_both()

    time.sleep(1)

    print("6. Both motors opposite directions")
    lgpio.gpio_write(h, L_DIR, 1)
    lgpio.gpio_write(h, R_DIR, 0)
    pulse_both()

finally:
    lgpio.gpio_write(h, EN, 1)
    lgpio.gpiochip_close(h)