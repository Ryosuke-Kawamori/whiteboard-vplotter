# Whiteboard V-Plotter

ホワイトボード（1800×900mm・脚付きスタンド）に文字を描くポーラーグラフ。
Raspberry Pi から TMC2209 経由で NEMA17 を直接叩く構成。

## 構成

```
Raspberry Pi ── GPIO ── TMC2209 ×2 ── NEMA17 ×2 ── GT2ベルト ── ゴンドラ
                     └─ GPIO18 ─── MG90S(ペン昇降)
```

| 項目 | 値 |
|---|---|
| モーター | NEMA17 42×42×40 / 1.8° / 0.4N·m / 1.5A / D軸 φ5×25 |
| ドライバ | TMC2209（STEP/DIR モード、1/8 マイクロステップ） |
| 伝動 | GT2 6mm ベルト + 20T プーリー → 80 steps/mm |
| 電源 | 12V 4A |
| 描画エリア | 1400 × 580mm（案A） |

## ディレクトリ

```
firmware/   Raspberry Pi 側の制御コード
cad/        OpenSCAD ソース（.scad のみ。STL は生成する）
docs/       図・組立メモ
build/      生成された STL（git 管理外）
```

## セットアップ

### Raspberry Pi

```bash
sudo apt install python3-lgpio
git clone <このリポジトリ>
cd whiteboard-vplotter/firmware
cp config.example.py config.py
# config.py の MOTOR_SPACING などを実測値に書き換える
```

### 動作確認（GPIO なしで軌跡だけ見る）

```bash
python3 vplotter.py text "HELLO" --size 90 --dry --svg preview.svg
```

### 実際に描く

```bash
python3 vplotter.py jog "700,500"          # 回転方向の確認
python3 vplotter.py text "MTG 10:00" --size 90
```

## CAD

```bash
make            # cad/*.scad を build/*.stl に一括変換
make clean
```

STL はリポジトリに含めない。寸法は各自の実測値に依存するため、
`.scad` の先頭パラメータを直してから生成する。

| ファイル | 説明 |
|---|---|
| `mount.scad` | モーターマウント（1部品・左右共通） |
| `gondola.scad` | ゴンドラ + サーボ式ペンリフト |
| `bushing.scad` | マーカー径のアダプター |
| `pads.scad` | クランプの保護パッド（TPU 推奨） |
| `arm_extension.scad` | 案B用の延長アーム |

## 立ち上げ手順

1. 机の上でモーター1台＋ドライバ＋Pi を配線、`jog` で回転確認
2. TMC2209 の Vref 調整（0.6A 目安。定格 1.5A まで上げない）
3. 2台目を追加、`INVERT_LEFT/RIGHT` を確定
4. サーボの UP/DOWN 角度出し
5. ボードに設置 → **プーリー軸間を実測して `MOTOR_SPACING` に入れる**

## 設計メモ

- 律速はモータートルクではなく **クランプの摩擦** と **機構の剛性**
- 必要トルク 2.74 N·cm に対し保持トルク 40 N·cm（14.6倍）
- ベルト角は 20° を下限とした（`sin²θ` で剛性が落ちるため）
- ベルト面を盤面より 30mm 手前に出すことでゴンドラが盤にもたれ、
  ペン圧が生まれる（バネ不要）

## 案B（描画エリア拡大）

モーターを 262mm 上に伸ばすと 580mm → 850mm（盤面全体）になる。
`arm_extension.scad` にアーム・ブレース・追加クランプ。
ブレースは必須（無しだとクランプ保持力が不足する）。

## ライセンス

MIT
