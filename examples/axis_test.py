from vplotter_motion import (
    setup,
    cleanup,
    move_to,
    MOTOR_SPACING,
)

cx = MOTOR_SPACING / 2.0
cy = 450.0

try:
    setup()

    print("START: center")
    move_to(cx, cy)

    print("TEST X: +100 mm")
    move_to(cx + 100, cy)

    print("BACK TO CENTER")
    move_to(cx, cy)

    print("TEST Y: +100 mm")
    move_to(cx, cy + 100)

    print("BACK TO CENTER")
    move_to(cx, cy)

    print("DONE")

finally:
    cleanup()