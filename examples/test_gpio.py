import lgpio
import time

h = lgpio.gpiochip_open(0)

for pin in (20, 21, 16):
    lgpio.gpio_claim_output(h, pin, 0)

# STEP=HIGH, DIR=HIGH, EN=LOW
lgpio.gpio_write(h, 20, 1)
lgpio.gpio_write(h, 21, 1)
lgpio.gpio_write(h, 16, 0)

print("hold")
time.sleep(60)
