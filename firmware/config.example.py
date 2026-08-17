# ============================================================
# config.example.py
#
# 機体固有の実測値。これを config.py にコピーして使う。
#   cp config.example.py config.py
#
# config.py は .gitignore に入れてあるので、実測値をコミットして
# しまう事故が起きない。プリンタや盤が変わっても衝突しない。
# ============================================================

# ---- ジオメトリ(必ず実測して上書き) ----
MOTOR_SPACING = 1900.0   # 左右プーリー軸の中心間距離 [mm]
HOME_X        = 950.0    # 起動時にペン先を置く位置
HOME_Y        = 650.0

AREA_X_MIN, AREA_X_MAX = 250.0, 1650.0
AREA_Y_MIN, AREA_Y_MAX = 380.0, 920.0

# ---- 駆動系 ----
PULLEY_TEETH  = 20
BELT_PITCH    = 2.0      # GT2
STEPS_PER_REV = 200      # 1.8度
MICROSTEP     = 8        # ドライバの設定と一致させる

INVERT_LEFT   = False    # 回転方向が逆なら True
INVERT_RIGHT  = True

# ---- 速度 ----
FEED_DRAW = 18.0         # [mm/s]
FEED_MOVE = 35.0
SEG_LEN   = 1.5

# ---- GPIO (BCM) ----
PIN_L_STEP, PIN_L_DIR = 20, 21
PIN_R_STEP, PIN_R_DIR = 19, 26
PIN_ENABLE            = 16
PIN_SERVO             = 18

# ---- サーボ ----
SERVO_UP_US   = 1150
SERVO_DOWN_US = 1750
SERVO_WAIT    = 0.35
