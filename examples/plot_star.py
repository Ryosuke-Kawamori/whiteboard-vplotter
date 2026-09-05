import math
import time
import lgpio

# GPIO (BCM)
L_STEP = 20
L_DIR  = 21
R_STEP = 19
R_DIR  = 26
EN     = 16

# 実機に合わせる
MOTOR_SPACING = 1800.0   # 左右プーリー軸中心間 [mm]
MM_PER_STEP   = 0.025    # 20T GT2, 200step, 1/8 microstep想定

STEP_DELAY = 0.0015

# 開始位置：左右の中央
x = MOTOR_SPACING / 2.0
y = 450.0

h = lgpio.gpiochip_open(0)

for pin in (L_STEP, L_DIR, R_STEP, R_DIR, EN):
    lgpio.gpio_claim_output(h, pin, 0)


def lengths(px, py):
    left = math.hypot(px, py)
    right = math.hypot(MOTOR_SPACING - px, py)
    return left, right


def to_steps(px, py):
    l, r = lengths(px, py)
    return round(l / MM_PER_STEP), round(r / MM_PER_STEP)


cur_l, cur_r = to_steps(x, y)


def move_to(tx, ty):
    global x, y, cur_l, cur_r

    target_l, target_r = to_steps(tx, ty)

    dl = target_l - cur_l
    dr = target_r - cur_r

    lgpio.gpio_write(h, L_DIR, 1 if dl >= 0 else 0)
    lgpio.gpio_write(h, R_DIR, 1 if dr >= 0 else 0)

    al = abs(dl)
    ar = abs(dr)
    n = max(al, ar)

    if n == 0:
        return

    done_l = 0
    done_r = 0

    for i in range(1, n + 1):
        next_l = al * i // n
        next_r = ar * i // n

        step_l = next_l > done_l
        step_r = next_r > done_r

        if step_l:
            lgpio.gpio_write(h, L_STEP, 1)

        if step_r:
            lgpio.gpio_write(h, R_STEP, 1)

        time.sleep(0.00001)

        if step_l:
            lgpio.gpio_write(h, L_STEP, 0)

        if step_r:
            lgpio.gpio_write(h, R_STEP, 0)

        done_l = next_l
        done_r = next_r

        time.sleep(STEP_DELAY)

    cur_l = target_l
    cur_r = target_r
    x = tx
    y = ty


def point(cx, cy, r, deg):
    a = math.radians(deg)
    return (
        cx + r * math.cos(a),
        cy + r * math.sin(a)
    )


try:
    lgpio.gpio_write(h, EN, 0)

    cx = MOTOR_SPACING / 2.0
    cy = 450.0
    r = 60.0

    # 上向き三角
    t1 = [
        point(cx, cy, r, -90),
        point(cx, cy, r, 30),
        point(cx, cy, r, 150),
    ]

    # 下向き三角
    t2 = [
        point(cx, cy, r, 90),
        point(cx, cy, r, 210),
        point(cx, cy, r, 330),
    ]

    print("Drawing triangle 1")
    move_to(*t1[0])
    move_to(*t1[1])
    move_to(*t1[2])
    move_to(*t1[0])

    print("Drawing triangle 2")
    move_to(*t2[0])
    move_to(*t2[1])
    move_to(*t2[2])
    move_to(*t2[0])

    print("Done")

finally:
    lgpio.gpio_write(h, EN, 1)
    lgpio.gpiochip_close(h)