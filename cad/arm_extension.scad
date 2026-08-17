// ============================================================
// arm_extension.scad   [案B 専用]
// モーターを上に伸ばして描画エリアを 588mm -> 850mm にする
//
// 印刷済みの frame_clamp / motor_head はそのまま使える。
// この間に arm_segment を2本挟み、ブレースで三角に固める。
//
//   [motor_head]        ← 印刷済み
//       ↕
//   [arm_segment 155]   ← 新規
//       ↕
//   [arm_segment 155]   ← 新規
//       ↕
//   [frame_clamp]       ← 印刷済み
//
//   さらに:
//   [brace_clamp] --- [brace] --- [arm_collar]  で三角形を作る
//
// 材質: すべて PETG / 壁4本 / インフィル40%
// ============================================================

// ---------- 継手(印刷済みの部品と必ず同じ値) ----------
JW = 26; JD = 12; JL = 24;
JWALL = 4; JCL = 0.35;
JOX = JW + JWALL*2;   // 34
JOY = JD + JWALL*2;   // 20

// ---------- 枠クランプ(印刷済みと同じ値) ----------
frame_t   = 20.0;   // ★実測値
frame_fit = 0.6;
grip_front = 34;
grip_back  = 40;
jaw_t      = 6;
clamp_w    = 50;

// ---------- 延長量 ----------
// モーター軸高さ(枠上端から) = seg1 + seg2 + 16
// 目標 326mm -> seg 合計 310mm -> 1本 155mm
seg_len = 155;

// ---------- ブレース ----------
brace_inboard = 150;   // 2個目クランプを内側にずらす距離
brace_up      = 150;   // アーム上の取付点(クランプ天板からの高さ)

// ---------- ネジ ----------
m4_d   = 4.3;
nut_af = 7.2;
nut_t  = 3.4;

$fn = 64;

// ============================================================
// 継手(共通)
// ============================================================

module joint_bolts(z0) {
    for (z = [z0 + 7, z0 + 18])
        translate([-JOX/2 - 1, 0, z]) rotate([0, 90, 0])
            cylinder(d = m4_d, h = JOX + 2);
}

module joint_tongue(z0) {
    difference() {
        translate([-JW/2, -JD/2, z0]) cube([JW, JD, JL]);
        joint_bolts(z0);
    }
}

module joint_socket(z0) {
    difference() {
        translate([-JOX/2, -JOY/2, z0]) cube([JOX, JOY, JL]);
        translate([-(JW+JCL)/2, -(JD+JCL)/2, z0 - 1])
            cube([JW+JCL, JD+JCL, JL + 1.5]);
        joint_bolts(z0);
        for (z = [z0 + 7, z0 + 18])
            translate([JOX/2 - nut_t, 0, z]) rotate([0, 90, 0])
                cylinder(d = nut_af/cos(30), h = nut_t + 0.5, $fn = 6);
    }
}

// ============================================================
// 1. アームセグメント  ★2本必要(左右で計4本)
//    下が凹、上が凸。何本でも継ぎ足せる。
// ============================================================

module arm_segment(len = seg_len) {
    difference() {
        union() {
            joint_socket(0);
            translate([-JOX/2, -JOY/2, JL - 0.1])
                cube([JOX, JOY, len - JL*2 + 0.2]);
            joint_tongue(len - JL);
        }
        // 肉抜き(横穴)
        for (z = [JL + 26 : 34 : len - JL - 20])
            translate([-JOX/2 - 1, 0, z]) rotate([0, 90, 0])
                cylinder(d = 12, h = JOX + 2);
    }
}

// ============================================================
// 2. アームカラー  ★1個必要(左右で計2個)
//    アームの途中に巻き付けてブレースを受ける。
//    2分割して両側からボルトで締める方式。
// ============================================================

collar_h = 26;

module arm_collar_half(with_ear = true) {
    cl = 0.4;   // アームとのすきま
    difference() {
        union() {
            translate([-(JOX+12)/2, -(JOY+10)/2, 0])
                cube([(JOX+12), (JOY+10)/2, collar_h]);
            if (with_ear)
                translate([-(JOX+12)/2 - 14, -(JOY+10)/2, 0])
                    cube([16, (JOY+10)/2, collar_h]);
        }
        // アームが通る溝
        translate([-(JOX+cl)/2, -(JOY+cl)/2, -1])
            cube([JOX+cl, (JOY+cl)/2 + 1, collar_h + 2]);
        // 締め付けボルト(左右)
        for (x = [-1, 1])
            translate([x * (JOX/2 + 5), 0, collar_h/2])
                rotate([90, 0, 0]) cylinder(d = m4_d, h = 40, center = true);
        // ブレース取付穴
        if (with_ear)
            translate([-(JOX+12)/2 - 6, 0, collar_h/2])
                rotate([90, 0, 0]) cylinder(d = m4_d, h = 40, center = true);
    }
}

module arm_collar() {
    arm_collar_half(true);
    translate([0, 0, collar_h + 6]) mirror([0,1,0]) arm_collar_half(false);
}

// ============================================================
// 3. ブレース用クランプ  ★1個必要(左右で計2個)
//    frame_clamp から継手を取り除き、ブレース受けを付けたもの。
// ============================================================

module brace_clamp() {
    gap = frame_t + frame_fit;
    front_y = -(gap/2 + jaw_t);

    difference() {
        union() {
            translate([-clamp_w/2, front_y, 0])
                cube([clamp_w, gap + jaw_t*2, jaw_t]);
            translate([-clamp_w/2, front_y, 0]) cube([clamp_w, jaw_t, grip_front]);
            translate([-clamp_w/2, gap/2, 0])   cube([clamp_w, jaw_t, grip_back]);
            // ブレース受け(上に立つ耳)
            translate([-6, front_y, jaw_t - 0.1])
                cube([12, 16, 30]);
            // 耳の付け根リブ
            translate([-6, front_y, jaw_t - 0.1])
                rotate([0, -90, 0]) mirror([0,0,1])
                    linear_extrude(12) polygon([[0,0],[0,26],[16,0]]);
        }
        // ブレース取付穴
        translate([-20, front_y + 8, jaw_t + 20])
            rotate([0, 90, 0]) cylinder(d = m4_d, h = 40);
        // 締め付けボルト + ナット座
        for (x = [-14, 14]) {
            translate([x, gap/2 - 1, grip_back - 13]) rotate([-90, 0, 0])
                cylinder(d = m4_d, h = jaw_t + 2);
            translate([x, gap/2 + jaw_t - nut_t, grip_back - 13]) rotate([-90, 0, 0])
                cylinder(d = nut_af/cos(30), h = nut_t + 0.6, $fn = 6);
        }
    }
}

// ============================================================
// 4. ブレース  ★1本必要(左右で計2本)
//    斜めの突っ張り棒。盤面内のモーメントを受け持ち、
//    クランプの引き剥がし力を 24N -> 9N に下げる。
// ============================================================

brace_len = sqrt(brace_inboard*brace_inboard + brace_up*brace_up);

module brace(len = brace_len) {
    difference() {
        union() {
            hull() {
                cylinder(d = 17, h = 8);
                translate([len, 0, 0]) cylinder(d = 17, h = 8);
            }
            // 縦リブ(座屈防止)
            translate([10, -3, 0]) cube([len - 20, 6, 20]);
        }
        translate([0, 0, -1])   cylinder(d = m4_d, h = 30);
        translate([len, 0, -1]) cylinder(d = m4_d, h = 30);
    }
    echo(str("ブレース長 = ", len, " mm"));
}

// ============================================================
// 出力: 刷りたいものだけ有効化
//   片側ぶん。左右で2セット必要。
// ============================================================

arm_segment(seg_len);
translate([60, 0, 0]) arm_segment(seg_len);

translate([130, 0, 0]) arm_collar();
translate([200, 0, 0]) brace_clamp();
translate([0, 90, 0]) brace();

// ---- 継手のはめあいだけ確認するテスト(10分) ----
// intersection() {
//     arm_segment(seg_len);
//     translate([-25, -20, 0]) cube([50, 40, 30]);
// }
