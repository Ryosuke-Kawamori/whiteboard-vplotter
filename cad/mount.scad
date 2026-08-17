// ============================================================
// mount.scad   --- V-Plotter モーターマウント (単一部品版)
//
// 設計しなおしの方針:
//   ・継手も分割もやめて 1部品にした(部品点数と失敗要因を削減)
//   ・モーターは軸を手前(盤と反対)に向けて取り付ける
//     → プーリーが最前面に来るので、ベルト2本は
//       何にも当たらずに自然に垂れる。専用の逃げは不要。
//   ・M3ボルトは前から挿す(プーリー側)。手が入る。
//   ・左右対称なので、同じものを2個刷ればよい(mirror不要)
//
// 印刷: PETG / 壁4本 / インフィル40% / ブリム推奨
//       このままの向き(ジョーの先端が下)で立てて刷る
//       20mmのブリッジが1箇所あるがサポート不要
// ============================================================

// ---------- 実測して合わせる ----------
frame_t  = 20.0;   // ★ホワイトボード枠の厚み(出っ張りを含む実測値)
fit      = 0.6;    // 挟み込みのゆとり

// ---------- ベルト面のオフセット D ----------
//   盤面 〜 ベルトが走る面 の距離。
//   大きい → ペン圧は出るがマーカーが寝る
//   小さい → マーカーは立つが線がかすれる
//   30mm でペン圧 33g / 傾き18度。まずこれで試す。
D = 30;

// ---------- クランプ ----------
jaw_t      = 6;
grip_front = 34;
grip_back  = 40;
clamp_w    = 50;

// ---------- モーター ----------
motor_z     = 58;    // 枠上端 〜 モーター軸中心
nema_bolt   = 31.0;
nema_boss_d = 23.0;
m3_d        = 3.4;
plate_t     = 6;
plate_half  = 26;

// ---------- ネジ ----------
m4_d   = 4.3;
nut_af = 7.2;
nut_t  = 3.4;

// ---------- 導出値 ----------
gap       = frame_t + fit;
y_board   = -gap/2;              // 盤の表面
y_fjaw    = y_board - jaw_t;     // 表側ジョーの外面
y_belt    = y_board - D;         // ベルトが走る面
y_plate0  = y_belt + 8;          // プレート前面(ベルトの8mm奥)
y_plate1  = y_plate0 + plate_t;  // プレート後面 = モーターが付く面
z_top     = motor_z + plate_half;

$fn = 64;

echo(str("ベルト面は盤面の ", D, "mm 手前"));
echo(str("モーター後端は y=", y_plate1 + 40, " (枠の裏は y=", gap/2 + jaw_t, ")"));

// ============================================================

module mount() {
    difference() {
        union() {
            // --- 天板(枠の上端に乗り、前へ張り出してプレートにつながる) ---
            translate([-clamp_w/2, y_plate0, 0])
                cube([clamp_w, (gap/2 + jaw_t) - y_plate0, jaw_t]);

            // --- 表側ジョー ---
            translate([-clamp_w/2, y_fjaw, -grip_front])
                cube([clamp_w, jaw_t, grip_front]);

            // --- 裏側ジョー ---
            translate([-clamp_w/2, gap/2, -grip_back])
                cube([clamp_w, jaw_t, grip_back]);

            // --- 縦プレート(モーターが付く) ---
            translate([0, y_plate0, 0]) rotate([90, 0, 0]) mirror([0,0,1])
                linear_extrude(plate_t)
                    hull() {
                        translate([-clamp_w/2 + 5, 5]) circle(r = 5);
                        translate([ clamp_w/2 - 5, 5]) circle(r = 5);
                        for (x = [-1,1], z = [-1,1])
                            translate([x*(plate_half-5), motor_z + z*(plate_half-5)])
                                circle(r = 5);
                    }

            // --- 左右のガセット(天板とプレートをつなぐ) ---
            //     モーター下端(z=motor_z-21)より低い位置だけ。
            //     ベルト面(y_belt)より奥にあるので当たらない。
            for (sx = [-1, 1])
                translate([sx * 20, 0, 0]) rotate([90, 0, 90])
                    linear_extrude(5, center = true)
                        polygon([[y_plate1, jaw_t],
                                 [gap/2,    jaw_t],
                                 [y_plate1, motor_z - 22]]);
        }

        // --- NEMA17 取付穴(前から挿す) ---
        for (sx = [-1,1], sz = [-1,1])
            translate([sx*nema_bolt/2, y_plate0 - 8, motor_z + sz*nema_bolt/2])
                rotate([-90,0,0]) cylinder(d = m3_d, h = plate_t + 16);

        // --- 中央ボス / シャフトの逃げ ---
        translate([0, y_plate0 - 8, motor_z]) rotate([-90,0,0])
            cylinder(d = nema_boss_d, h = plate_t + 16);

        // --- 肉抜き ---
        for (sx = [-1,1])
            translate([sx*15, y_plate0 - 8, 22]) rotate([-90,0,0])
                cylinder(d = 12, h = plate_t + 16);

        // --- クランプ締め付けボルト + ナット座 ---
        for (x = [-14, 14]) {
            translate([x, gap/2 - 1, -grip_back + 13]) rotate([-90,0,0])
                cylinder(d = m4_d, h = jaw_t + 2);
            translate([x, gap/2 + jaw_t - nut_t, -grip_back + 13]) rotate([-90,0,0])
                cylinder(d = nut_af/cos(30), h = nut_t + 0.6, $fn = 6);
        }
    }

    // --- 滑り止めリブ(表側ジョー内面。TPUパッドを使うなら削ってよい) ---
    for (z = [-14, -25])
        translate([-clamp_w/2, y_fjaw + jaw_t, z]) cube([clamp_w, 1.4, 2]);
}

// ============================================================
// 干渉チェック用のダミー  --- 刷る前に必ず F5 で見る
// ============================================================

module chk_motor() {   // NEMA17 42x42x40  プレートの裏に付く
    translate([-21, y_plate1, motor_z - 21]) cube([42, 40, 42]);
}
module chk_pulley() {  // GT2 20T  プレートの手前
    translate([0, y_plate0 - 16, motor_z]) rotate([-90,0,0]) cylinder(d = 16, h = 16);
}
module chk_belt() {    // ベルトが走る面。ここに構造物が無ければOK
    translate([-70, y_belt - 0.8, -80]) cube([140, 1.6, 150]);
}
module chk_board() {   // ホワイトボード
    translate([-70, y_board, -300]) cube([140, gap, 300]);
}

// ============================================================
// 出力
// ============================================================

mount();

// --- 干渉チェック(見るときだけコメントを外す) ---
// % chk_motor();
// % chk_pulley();
// % chk_belt();
// % chk_board();

// --- テストピース: 枠にはまるか(10分) ---
// intersection() { mount(); translate([-25,-60,-45]) cube([50,120,50]); }

// --- テストピース: M3が挿せるか(15分) ---
// intersection() { mount(); translate([-30,-60,motor_z-26]) cube([60,40,52]); }
