import math
import time
import lgpio


# ============================================================
# CONFIG
# ============================================================

# Raspberry Pi BCM GPIO
L_STEP = 20
L_DIR  = 21

R_STEP = 19
R_DIR  = 26

EN = 16


# 左右プーリー軸中心間距離 [mm]
MOTOR_SPACING = 1800.0


# 実行開始時のペン位置
START_X = MOTOR_SPACING / 2.0
START_Y = 450.0


# GT2 20T + 1/8 microstep
#
# 20T × 2mm = 40mm / revolution
# 200step × 8 = 1600 microstep / revolution
# 40 / 1600 = 0.025mm / step
MM_PER_STEP = 0.025


# 1ステップごとの待ち時間
STEP_DELAY = 0.0015


# XY直線補間の細かさ
SEGMENT_MM = 1.0


# 左右モーターのDIR反転
INVERT_LEFT  = False
INVERT_RIGHT = True


# ============================================================
# STATE
# ============================================================

h = None

x = START_X
y = START_Y

cur_l = None
cur_r = None


# ============================================================
# KINEMATICS
# ============================================================

def lengths(px, py):
    """
    XY座標から左右のベルト長を計算する。

    左モーター  = (0, 0)
    右モーター  = (MOTOR_SPACING, 0)

    x: 右方向がプラス
    y: 下方向がプラス
    """

    left = math.hypot(px, py)

    right = math.hypot(
        MOTOR_SPACING - px,
        py
    )

    return left, right


def to_steps(px, py):
    """
    XY座標を左右モーターの絶対ステップ位置へ変換。
    """

    left_mm, right_mm = lengths(px, py)

    left_steps = round(left_mm / MM_PER_STEP)
    right_steps = round(right_mm / MM_PER_STEP)

    return left_steps, right_steps


# ============================================================
# SETUP / CLEANUP
# ============================================================

def setup():
    global h
    global x, y
    global cur_l, cur_r

    if h is not None:
        return

    h = lgpio.gpiochip_open(0)

    lgpio.gpio_claim_output(h, L_STEP, 0)
    lgpio.gpio_claim_output(h, L_DIR, 0)

    lgpio.gpio_claim_output(h, R_STEP, 0)
    lgpio.gpio_claim_output(h, R_DIR, 0)

    lgpio.gpio_claim_output(h, EN, 1)

    x = START_X
    y = START_Y

    cur_l, cur_r = to_steps(x, y)

    # TMC2209 enable
    lgpio.gpio_write(h, EN, 0)

    time.sleep(0.3)

    print("================================")
    print("V-PLOTTER READY")
    print("================================")
    print(f"MOTOR_SPACING : {MOTOR_SPACING} mm")
    print(f"START         : ({x:.1f}, {y:.1f})")
    print(f"LEFT STEPS    : {cur_l}")
    print(f"RIGHT STEPS   : {cur_r}")
    print()


def cleanup():
    global h

    if h is None:
        return

    # TMC2209 disable
    lgpio.gpio_write(h, EN, 1)

    lgpio.gpiochip_close(h)

    h = None

    print("V-PLOTTER OFF")


# ============================================================
# LOW LEVEL MOTOR MOVE
# ============================================================

def belt_move_to(tx, ty):
    """
    指定XY位置に対応する左右ベルト長まで、
    左右モーターを同期してステップさせる。
    """

    global cur_l, cur_r

    if h is None:
        raise RuntimeError("setup() を先に呼んでください")

    target_l, target_r = to_steps(tx, ty)

    dl = target_l - cur_l
    dr = target_r - cur_r


    # --------------------------------------------------------
    # DIR
    # --------------------------------------------------------

    l_dir = 1 if dl >= 0 else 0
    r_dir = 1 if dr >= 0 else 0

    if INVERT_LEFT:
        l_dir ^= 1

    if INVERT_RIGHT:
        r_dir ^= 1

    lgpio.gpio_write(h, L_DIR, l_dir)
    lgpio.gpio_write(h, R_DIR, r_dir)


    # --------------------------------------------------------
    # 必要ステップ数
    # --------------------------------------------------------

    al = abs(dl)
    ar = abs(dr)

    total = max(al, ar)

    if total == 0:
        return


    done_l = 0
    done_r = 0


    # --------------------------------------------------------
    # 左右同期
    # --------------------------------------------------------

    for i in range(1, total + 1):

        next_l = al * i // total
        next_r = ar * i // total

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


# ============================================================
# XY MOVE
# ============================================================

def move_to(tx, ty, segment_mm=None):
    """
    XY座標上を直線移動する。

    V-PlotterはXYとベルト長の関係が非線形なので、
    XY上で細かく分割しながら逆運動学を計算する。
    """

    global x, y

    if segment_mm is None:
        segment_mm = SEGMENT_MM


    sx = x
    sy = y

    dx = tx - sx
    dy = ty - sy

    distance = math.hypot(dx, dy)

    if distance < 0.001:
        return


    segments = max(
        1,
        math.ceil(distance / segment_mm)
    )


    for i in range(1, segments + 1):

        ratio = i / segments

        px = sx + dx * ratio
        py = sy + dy * ratio

        belt_move_to(px, py)


    x = tx
    y = ty


# ============================================================
# HELPERS
# ============================================================

def move_relative(dx, dy):
    """
    現在位置から相対移動。
    """

    move_to(
        x + dx,
        y + dy
    )


def get_position():
    """
    現在コードが認識しているXY位置を返す。
    """

    return x, y


def home_center():
    """
    開始中央位置へ戻る。
    """

    move_to(
        START_X,
        START_Y
    )