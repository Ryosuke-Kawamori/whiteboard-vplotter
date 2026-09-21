#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iPhone から画像を送って白板に描くローカル専用サーバー。"""

import argparse
import json
import mimetypes
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(_ROOT))

from examples.image_to_svg import (
    AREA_X_MAX,
    AREA_X_MIN,
    AREA_Y_MAX,
    AREA_Y_MIN,
    LgpioIO,
    Plotter,
    draw_image_to_board,
    format_plot_estimate,
    write_board_preview,
    write_svg_from_image,
)
from examples.meiryo_text import check_fit, text_to_strokes

UPLOAD_DIR = Path(__file__).resolve().parent / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
DRAWING_STOP_EVENT = threading.Event()
DRAWING_ACTIVE_LOCK = threading.Lock()
DRAWING_ACTIVE = False
JAPANESE_FONT = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')


def text_machine_strokes(text, size=90.0, x=950.0, y=560.0):
    """複数行テキストを輪郭化し、指定中心へ配置する。"""
    if not JAPANESE_FONT.is_file():
        raise FileNotFoundError(f'日本語フォントが見つかりません: {JAPANESE_FONT}')
    strokes = text_to_strokes(text, JAPANESE_FONT, size, 0.0, 0.0)
    xs = [px for stroke in strokes for px, _ in stroke]
    ys = [py for stroke in strokes for _, py in stroke]
    offset_x = x - (min(xs) + max(xs)) / 2.0
    offset_y = y - (min(ys) + max(ys)) / 2.0
    machine = [[(px + offset_x, py + offset_y) for px, py in stroke]
               for stroke in strokes]
    check_fit(machine)
    return machine


def text_boxes_machine_strokes(serialized_boxes):
    """JSONのテキストボックス群を1つの描画ストローク列へ変換する。"""
    boxes = json.loads(serialized_boxes)
    if not isinstance(boxes, list) or not boxes:
        raise ValueError('テキストボックスを追加してください')
    machine = []
    for box in boxes:
        if not isinstance(box, dict) or not str(box.get('text', '')).strip():
            continue
        machine.extend(text_machine_strokes(
            str(box['text']),
            size=float(box.get('size', 90)),
            x=float(box.get('x', 950)),
            y=float(box.get('y', 560)),
        ))
    if not machine:
        raise ValueError('文字を入力してください')
    return machine


def draw_strokes_to_board(strokes, should_stop=None):
    plotter = Plotter(LgpioIO())
    try:
        stopped = False
        for stroke in strokes:
            if should_stop is not None and should_stop():
                stopped = True
                break
            plotter.jump_to(*stroke[0])
            for point in stroke[1:]:
                if should_stop is not None and should_stop():
                    stopped = True
                    break
                plotter.line_to(*point)
            if stopped:
                break
        plotter.finish()
    except KeyboardInterrupt:
        plotter.pen_up()
        plotter.io.cleanup()


def _legacy_page():
    return """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Whiteboard Image Upload</title>
  <style>
    :root { color-scheme: light; }
    body { margin: 0; padding: 20px; background: #edf2f1; color: #15201d; font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", sans-serif; }
    main { max-width: 600px; margin: 0 auto; }
    h1 { margin: 0 0 20px; font-size: 1.45rem; }
    form, section { margin-top: 14px; padding: 18px; background: #fff; border: 1px solid #d5dfdb; border-radius: 8px; }
    label { display: block; margin: 14px 0 6px; font-weight: 600; }
    input, button { width: 100%; box-sizing: border-box; min-height: 44px; padding: 10px 12px; border: 1px solid #aab9b3; border-radius: 6px; font: inherit; }
    button { margin-top: 12px; background: #126b52; border: 0; color: #fff; font-weight: 700; }
    button.secondary { background: #3d5750; }
    button.danger { background: #a62929; }
    .notice { margin-top: 14px; padding: 12px; background: #e1f5ec; border: 1px solid #99d6bb; border-radius: 6px; }
    .notice[hidden] { display: none; }
    figure { margin: 0; }
    figcaption { margin-bottom: 6px; font-size: .9rem; font-weight: 600; }
    img { display: block; width: 100%; aspect-ratio: 2 / 1; object-fit: contain; border: 1px solid #d5dfdb; background: #fff; }
    #svgPreview.ready { cursor: grab; touch-action: none; }
    #svgPreview.dragging { cursor: grabbing; }
    output { display: block; margin-top: 6px; font-variant-numeric: tabular-nums; }
    .hint { color: #4c5d57; font-size: .85rem; line-height: 1.5; }
  </style>
</head>
<body>
  <main>
    <h1>白板に描く画像を選ぶ</h1>
    <form method="post" enctype="multipart/form-data">
      <label for="image">画像</label>
            <input id="image" name="image" type="file" accept="image/*" />
            <input id="source" name="source" type="hidden" />
            <figure style="margin-top:14px;"><figcaption>白板プレビュー</figcaption><img id="svgPreview" alt="変換後SVG" /></figure>
            <label for="size">描画幅</label>
            <input id="size" name="size" type="range" min="20" max="500" step="5" value="180" />
            <output id="sizeOutput" for="size">180 mm</output>
    <label for="x">中心X位置 (mm)</label>
    <input id="x" name="x" type="number" min="250" max="1650" value="950" />
    <label for="y">下端Y位置 (mm)</label>
    <input id="y" name="y" type="number" min="200" max="920" value="700" />
      <button class="secondary" name="action" value="preview" type="submit">変換プレビューを作る</button>
      <button name="action" value="draw" type="submit">この画像を描画する</button>
      <button id="stopBtn" class="danger" type="button">停止して原点へ戻す</button>
    </form>
    <p class="hint">白板プレビューをドラッグすると描画位置を変更できます。描画中に停止すると、ペンを上げて原点に戻ります。</p>
    <div id="result" class="notice" hidden></div>
  </main>
  <script>
    const input = document.getElementById('image');
    const svgPreview = document.getElementById('svgPreview');
    const source = document.getElementById('source');
        const size = document.getElementById('size');
        const sizeOutput = document.getElementById('sizeOutput');
        const x = document.getElementById('x');
        const y = document.getElementById('y');
    const result = document.getElementById('result');
    const params = new URLSearchParams(location.search);
        let previewTimer;
        let previewController;
        let dragStart;

        <title>Whiteboard Composer</title>
            return Math.min(Number(input.max), Math.max(Number(input.min), value));
        }

        async function updatePreview() {
            if (!source.value) return;
            if (previewController) previewController.abort();
            previewController = new AbortController();
            const query = new URLSearchParams({ source: source.value, size: size.value, x: x.value, y: y.value });
            try {
                const response = await fetch('/preview?' + query, { signal: previewController.signal });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'プレビューを更新できません');
                svgPreview.src = data.preview + '?t=' + Date.now();
                result.hidden = false;
                result.textContent = data.message;
                history.replaceState(null, '', '/?' + new URLSearchParams({
                    source: source.value, preview: data.preview.split('/').pop(),
                    size: size.value, x: x.value, y: y.value,
                }));
            } catch (error) {
            .mode-switch { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; padding: 4px; background: #dbe5e1; border-radius: 8px; }
            .mode-switch button { margin: 0; background: transparent; color: #31443e; }
            .mode-switch button.active { background: #fff; color: #126b52; box-shadow: 0 1px 3px #0002; }
            textarea { width: 100%; box-sizing: border-box; min-height: 110px; padding: 12px; resize: vertical; border: 1px solid #aab9b3; border-radius: 6px; font: 1.15rem/1.5 "Noto Sans CJK JP", "Hiragino Sans", sans-serif; }
            [hidden] { display: none !important; }
                if (error.name !== 'AbortError') {
                    result.hidden = false;
                    result.textContent = error.message;
                }
            }
        }
                <input id="mode" name="mode" type="hidden" value="image" />
                <div class="mode-switch" role="tablist" aria-label="描画内容">
                    <button id="imageMode" class="active" type="button" role="tab">画像</button>
                    <button id="textMode" type="button" role="tab">文字</button>
                </div>
                <div id="imageControls">
                    <label for="image">画像</label>
                    <input id="image" name="image" type="file" accept="image/*" />
                    <input id="source" name="source" type="hidden" />
                </div>
                <div id="textControls" hidden>
                    <label for="text">文章</label>
                    <textarea id="text" name="text" placeholder="今週の目標&#10;安全第一"></textarea>
                </div>
                <figure style="margin-top:14px;"><figcaption>白板プレビュー</figcaption><img id="svgPreview" alt="描画プレビュー" /></figure>
                <label id="sizeLabel" for="size">描画幅</label>
                <input id="size" name="size" type="range" min="20" max="500" step="5" value="180" />
                <output id="sizeOutput" for="size">180 mm</output>
                <label for="x">中心X位置 (mm)</label>
                <input id="x" name="x" type="number" min="250" max="1650" value="950" />
                <label for="y">中心Y位置 (mm)</label>
                <input id="y" name="y" type="number" min="200" max="920" value="560" />

        function schedulePreview() {
            sizeOutput.value = size.value + ' mm';
            clearTimeout(previewTimer);
            <p class="hint">文章を編集するか、白板プレビューをドラッグして位置を調整できます。描画中に停止すると原点へ戻ります。</p>
        }

    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
            const mode = document.getElementById('mode');
            const imageMode = document.getElementById('imageMode');
            const textMode = document.getElementById('textMode');
            const imageControls = document.getElementById('imageControls');
            const textControls = document.getElementById('textControls');
            const text = document.getElementById('text');
            if (file) source.value = '';
    });
        if (params.get('source')) {
            source.value = params.get('source');
            svgPreview.classList.add('ready');
        }
        for (const control of [size, x, y]) {
            if (params.get(control.id)) control.value = params.get(control.id);
            control.addEventListener('input', schedulePreview);
        }
        sizeOutput.value = size.value + ' mm';
        if (params.get('preview')) svgPreview.src = '/uploads/' + encodeURIComponent(params.get('preview'));
    if (params.get('message')) {
      result.hidden = false;
      result.textContent = params.get('message');
    }
        svgPreview.addEventListener('pointerdown', event => {
                            if (mode.value === 'image' && !source.value) return;
                            if (mode.value === 'text' && !text.value.trim()) return;
            svgPreview.setPointerCapture(event.pointerId);
            svgPreview.classList.add('dragging');
            dragStart = { clientX: event.clientX, clientY: event.clientY, x: Number(x.value), y: Number(y.value) };
        });
        svgPreview.addEventListener('pointermove', event => {
            if (!dragStart) return;
            const rect = svgPreview.getBoundingClientRect();
            x.value = Math.round(clamp(dragStart.x + (event.clientX - dragStart.clientX) * 1800 / rect.width, x));
            y.value = Math.round(clamp(dragStart.y + (event.clientY - dragStart.clientY) * 900 / rect.height, y));
            schedulePreview();
        });
                                            mode: mode.value, source: source.value, text: text.value,
                                            preview: data.preview.split('/').pop(), size: size.value,
                                            x: x.value, y: y.value,
            svgPreview.classList.remove('dragging');
        }
        svgPreview.addEventListener('pointerup', endDrag);
        svgPreview.addEventListener('pointercancel', endDrag);
    document.getElementById('stopBtn').addEventListener('click', async () => {
      const response = await fetch('/stop', { method: 'POST' });
      result.hidden = false;
      result.textContent = await response.text();
    });
  </script>
</body>
</html>
"""


from examples.whiteboard_object_page import build_page


def save_uploaded_file(file_name, file_data):
    if not file_data:
        raise ValueError('画像データが空です')
    suffix = Path(file_name).suffix.lower() or '.png'
    path = UPLOAD_DIR / f'upload_{uuid.uuid4().hex}{suffix}'
    path.write_bytes(file_data)
    return path


def set_drawing_active(active):
    global DRAWING_ACTIVE
    with DRAWING_ACTIVE_LOCK:
        DRAWING_ACTIVE = active


def is_drawing_active():
    with DRAWING_ACTIVE_LOCK:
        return DRAWING_ACTIVE


def go_home_once():
    io = LgpioIO()
    plotter = Plotter(io)
    plotter.finish()


def parse_upload(content_type, content_length, stream):
    if 'multipart/form-data' not in content_type or 'boundary=' not in content_type:
        raise ValueError('multipart/form-data が必要です')
    boundary = content_type.split('boundary=', 1)[1].encode()
    fields = {}
    file_name = None
    file_data = None
    for part in stream.read(content_length).split(b'--' + boundary):
        headers, separator, body = part.partition(b'\r\n\r\n')
        if not separator:
            continue
        body = body.rstrip(b'\r\n')
        header_text = headers.decode('latin-1', 'replace')
        if 'filename="' in header_text:
            file_name = header_text.split('filename="', 1)[1].split('"', 1)[0]
            file_data = body
        elif 'name="' in header_text:
            name = header_text.split('name="', 1)[1].split('"', 1)[0]
            fields[name] = body.decode('utf-8', 'replace').strip()
    return fields, file_name or 'upload.png', file_data


def resolve_uploaded_image(fields, file_name, file_data):
    """新規アップロードを保存するか、既存の安全なファイル名を再利用する。"""
    if file_data:
        return save_uploaded_file(file_name, file_data)
    source_name = Path(fields.get('source', '')).name
    source_path = UPLOAD_DIR / source_name
    if source_name and source_path.is_file() and source_path.suffix.lower() != '.svg':
        return source_path
    raise ValueError('画像を選択してください')


class ImageUploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/preview':
            try:
                params = parse_qs(parsed.query)
                mode = params.get('mode', ['image'])[0]
                size = float(params.get('size', ['90' if mode == 'text' else '180'])[0])
                x = float(params.get('x', ['950'])[0])
                y = float(params.get('y', ['560'])[0])
                if mode == 'text':
                    serialized_boxes = params.get('boxes', [''])[0]
                    machine = text_boxes_machine_strokes(serialized_boxes)
                    svg_path = UPLOAD_DIR / 'text_preview.svg'
                    write_board_preview(svg_path, machine)
                else:
                    source_name = Path(params.get('source', [''])[0]).name
                    image_path = UPLOAD_DIR / source_name
                    if (not source_name or not image_path.is_file()
                            or image_path.suffix.lower() == '.svg'):
                        raise ValueError('アップロード済み画像が見つかりません')
                    svg_path = image_path.with_name(f'{image_path.stem}_preview.svg')
                    machine = write_svg_from_image(
                        image_path, svg_path, target_width=220, threshold=200,
                        size=size, x=x, y=y,
                    )
                self.respond_json({
                    'preview': f'/uploads/{svg_path.name}',
                    'message': f'プレビュー更新: {format_plot_estimate(machine)}',
                })
            except Exception as exc:
                self.respond_json({'error': str(exc)}, status=400)
            return
        if parsed.path in ('/', '/index.html'):
            self.respond_html(build_page())
            return
        if parsed.path.startswith('/uploads/'):
            candidate = UPLOAD_DIR / Path(parsed.path).name
            if candidate.is_file():
                self.send_response(200)
                self.send_header('Content-Type', mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream')
                self.end_headers()
                self.wfile.write(candidate.read_bytes())
                return
        self.send_error(404)

    def do_POST(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/stop':
            DRAWING_STOP_EVENT.set()
            if is_drawing_active():
                message = '停止要求を受け付けました。停止後に原点へ戻ります。'
            else:
                go_home_once()
                message = '描画していないため、原点へ戻りました。'
            self.respond_text(message)
            return
        if parsed.path not in ('/', '/upload'):
            self.send_error(404)
            return
        try:
            fields, file_name, file_data = parse_upload(
                self.headers.get('Content-Type', ''),
                int(self.headers.get('Content-Length', '0')),
                self.rfile,
            )
            mode = fields.get('mode', 'image')
            size = float(fields.get('size') or (90 if mode == 'text' else 180))
            x = float(fields.get('x') or 950)
            y = float(fields.get('y') or 560)
            text = fields.get('text', '').strip()
            serialized_boxes = fields.get('boxes', '')
            image_path = None
            if mode == 'text':
                machine = text_boxes_machine_strokes(serialized_boxes)
                svg_path = UPLOAD_DIR / f'text_{uuid.uuid4().hex}.svg'
                write_board_preview(svg_path, machine)
            else:
                image_path = resolve_uploaded_image(fields, file_name, file_data)
                svg_path = image_path.with_suffix('.svg')
                machine = write_svg_from_image(
                    image_path, svg_path, target_width=220, threshold=200,
                    size=size, x=x, y=y,
                )
            estimate = format_plot_estimate(machine)
            action = fields.get('action', 'draw')
            if action == 'draw':
                DRAWING_STOP_EVENT.clear()
                set_drawing_active(True)
                try:
                    if mode == 'text':
                        draw_strokes_to_board(
                            machine, should_stop=DRAWING_STOP_EVENT.is_set
                        )
                    else:
                        draw_image_to_board(
                            image_path, size=size, x=x, y=y, dry=False,
                            threshold=200,
                            should_stop=DRAWING_STOP_EVENT.is_set,
                        )
                finally:
                    set_drawing_active(False)
                message = ('停止して原点へ戻りました。' if DRAWING_STOP_EVENT.is_set()
                           else f'描画が完了しました。見積: {estimate}')
            else:
                message = f'変換プレビューを作成しました。見積: {estimate}'
            source_name = image_path.name if image_path is not None else ''
            location = '/?message={}&mode={}&source={}&boxes={}&preview={}&size={}&x={}&y={}'.format(
                quote(message), quote(mode), quote(source_name), quote(serialized_boxes),
                quote(svg_path.name), quote(str(size)), quote(str(x)), quote(str(y)),
            )
            self.send_response(303)
            self.send_header('Location', location)
            self.end_headers()
        except Exception as exc:
            self.respond_text(f'エラー: {exc}', status=400)

    def respond_html(self, page):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(page.encode('utf-8'))

    def respond_text(self, message, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))

    def respond_json(self, value, status=200):
        payload = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        return


def run_server(host='0.0.0.0', port=8000):
    server = ThreadingHTTPServer((host, port), ImageUploadHandler)
    print(f'Serving on http://{host}:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='iPhoneから使える画像アップロードページ')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
