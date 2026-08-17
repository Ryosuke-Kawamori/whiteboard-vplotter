// ============================================================
// gondola.scad
// V-Plotter 用ゴンドラ (ベアリング不要 / サーボ式ペンリフト)
//
// 動作原理:
//   ベルト取付点が盤面より前(board_offset)にあるため、自重で
//   ゴンドラが盤に「もたれ」、ペン先が盤面に押し付けられる。
//   ペンを上げるときは、サーボの足がペン先の下で盤を押し、
//   ゴンドラ全体を後ろに傾けてペン先を離す。
//
// 部品: MG90S x1 / M3ネジ数本 / 輪ゴム or 小さいバネ
// 印刷: PLA 可 / 壁3本 / インフィル25% / 平置き
// ============================================================

// ---------- マーカー実測値 ----------
marker_d_big   = 20.0;  // 太い部分の直径 ★実測
marker_d_small = 15.0;  // 細い部分の直径 ★実測
marker_len     = 140.0; // 全長 ★実測

// ---------- ジオメトリ ----------
plate_t     = 4;     // 本体プレート厚
arm_span    = 96;    // 左右のベルト取付点の間隔
arm_rise    = 42;    // ペン軸からベルト取付点までの高さ
sleeve_h    = 34;    // マーカー保持スリーブの高さ
sleeve_wall = 3.2;
clamp_slot  = 2.6;   // 締め付けスリットの幅

// ---------- GT2ベルト固定 ----------
belt_w      = 6.4;   // 6mm幅 + ゆとり
belt_t      = 1.6;   // ベルト厚(歯を含む)
belt_teeth  = 8;     // 噛ませる歯数
belt_pitch  = 2.0;

// ---------- MG90S ----------
servo_l  = 23.0;
servo_w  = 12.4;
servo_h  = 22.8;
servo_ear_w = 32.4;  // 耳を含む全長
servo_ear_t = 2.6;
servo_ear_z = 15.8;  // 底面から耳までの高さ

m3_d = 3.3;
m2_d = 2.2;

$fn = 72;

// ============================================================

module belt_clamp() {
    // GT2の歯にかみ合う溝。ベルトを差し込んでM3で締める。
    difference() {
        translate([-8, -belt_w/2 - 3, 0])
            cube([16, belt_w + 6, 14]);
        // ベルト通し
        translate([-9, -belt_w/2, 4])
            cube([18, belt_w, belt_t + 0.4]);
        // 歯溝
        for (i = [0 : belt_teeth - 1])
            translate([-belt_teeth * belt_pitch/2 + i * belt_pitch, -belt_w/2, 4 + belt_t])
                cube([belt_pitch * 0.55, belt_w, 1.0]);
        // 締めネジ
        translate([0, 0, -1]) cylinder(d = m3_d, h = 20);
    }
}

module marker_sleeve() {
    // 上下2段。太い部分を掴み、スリットで径を吸収する。
    difference() {
        union() {
            cylinder(d = marker_d_big + sleeve_wall * 2, h = sleeve_h);
            // 締め付け耳
            translate([-(marker_d_big/2 + sleeve_wall + 7), -5, 0])
                cube([9, 10, sleeve_h]);
        }
        // マーカー穴(上が太く、下が細い想定なら段を付ける)
        translate([0, 0, -1])
            cylinder(d = marker_d_big + 0.5, h = sleeve_h + 2);
        // 締め付けスリット
        translate([-40, -clamp_slot/2, -1])
            cube([40, clamp_slot, sleeve_h + 2]);
        // 締め付けネジ(スリットを跨ぐ)
        for (z = [9, sleeve_h - 9])
            translate([-(marker_d_big/2 + sleeve_wall + 3), -12, z])
                rotate([-90, 0, 0]) cylinder(d = m3_d, h = 24);
    }
}

module servo_pocket() {
    // MG90S の本体+耳の逃げ
    translate([-servo_l/2, -servo_w/2, 0])
        cube([servo_l, servo_w, servo_h + 1]);
    translate([-servo_ear_w/2, -servo_w/2, servo_ear_z])
        cube([servo_ear_w, servo_w, servo_ear_t + 0.3]);
    // 耳のネジ
    for (x = [-1, 1])
        translate([x * 14.0, 0, servo_ear_z - 6])
            cylinder(d = m2_d, h = 14);
}

module body() {
    difference() {
        union() {
            // 中央プレート
            hull() {
                cylinder(d = marker_d_big + sleeve_wall * 2 + 8, h = plate_t);
                for (x = [-1, 1])
                    translate([x * arm_span/2, arm_rise, 0])
                        cylinder(d = 16, h = plate_t);
                translate([0, -46, 0]) cylinder(d = 20, h = plate_t);
            }
            // マーカースリーブ
            translate([0, 0, plate_t]) marker_sleeve();
            // サーボ台座
            translate([0, -46, plate_t])
                difference() {
                    translate([-servo_ear_w/2 - 2, -servo_w/2 - 3, 0])
                        cube([servo_ear_w + 4, servo_w + 6, servo_h + 2]);
                    translate([0, 0, -0.5]) servo_pocket();
                }
        }
        // マーカー貫通穴
        translate([0, 0, -1])
            cylinder(d = marker_d_big + 0.5, h = plate_t + 2);
        // 軽量化 & 視認用の窓
        for (x = [-1, 1])
            translate([x * arm_span/4, arm_rise/2, -1])
                cylinder(d = 13, h = plate_t + 2);
    }

    // ベルト固定部(左右)
    for (x = [-1, 1])
        translate([x * arm_span/2, arm_rise, plate_t])
            rotate([0, 0, x * 34])   // ベルトが伸びる方向へ向ける
                belt_clamp();
}

// ---------- サーボの足(ペンを上げるときに盤を押す) ----------
module servo_foot() {
    difference() {
        union() {
            // ホーンに被せる部分
            translate([0, 0, 0]) cylinder(d = 9, h = 5);
            translate([-3, 0, 0]) cube([6, 24, 5]);
            // 盤に当たる丸い足
            translate([0, 24, 0]) sphere(d = 9);
        }
        // ホーン軸
        translate([0, 0, -1]) cylinder(d = 4.9, h = 4);
        translate([0, 0, 1.5]) cylinder(d = 7.4, h = 5);
    }
}

// ============================================================
// 出力: 印刷したいものだけ有効にする
// ============================================================

body();

translate([70, 0, 0]) servo_foot();
