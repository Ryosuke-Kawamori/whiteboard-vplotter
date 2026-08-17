# ============================================================
# Makefile --- .scad から .stl を一括生成する
#
#   make          全部ビルド
#   make clean    生成物を消す
#   make mount    1つだけビルド
#
# STL はリポジトリに入れず、必要なときに生成する方針。
# OpenSCAD が PATH に必要:
#   macOS  /Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
#   Linux  sudo apt install openscad
# ============================================================

OPENSCAD ?= openscad
CADDIR   := cad
OUTDIR   := build

SOURCES := $(wildcard $(CADDIR)/*.scad)
TARGETS := $(patsubst $(CADDIR)/%.scad,$(OUTDIR)/%.stl,$(SOURCES))

.PHONY: all clean list

all: $(TARGETS)

$(OUTDIR)/%.stl: $(CADDIR)/%.scad | $(OUTDIR)
	@echo "  SCAD  $< -> $@"
	@$(OPENSCAD) -o $@ $< 2>&1 | grep -v '^ECHO' || true

$(OUTDIR):
	@mkdir -p $(OUTDIR)

# 個別ターゲット: make mount のように書けるようにする
%: $(OUTDIR)/%.stl
	@:

list:
	@echo "ビルド対象:"
	@for f in $(SOURCES); do echo "  $$f"; done

clean:
	rm -rf $(OUTDIR)
