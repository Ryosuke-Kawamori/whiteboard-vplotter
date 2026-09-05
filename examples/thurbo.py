import lgpio, time
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, 18, 0)
for us in [1000, 1500, 2000, 1500]:
    print(us)
    lgpio.tx_servo(h, 18, us, 50)
    time.sleep(1.5)
lgpio.tx_servo(h, 18, 0, 50)
lgpio.gpiochip_close(h)