import sys, pathlib
sys.path.insert(0, str(pathlib.Path('firmware').resolve()))
from vplotter import Plotter, LgpioIO

p = Plotter(LgpioIO())
p.jump_to(950, 650)    # HOMEにペンを手で置いてから実行
p.pen_down()
p.line_to(1150, 650)   # → 右へ200mm
p.line_to(1150, 800)   # → 下へ150mm
p.finish()