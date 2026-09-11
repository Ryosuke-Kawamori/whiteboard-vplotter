#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iPhone から画像を送って白板に描くローカル専用サーバー。"""

import argparse
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

from examples.image_to_svg import LgpioIO, Plotter, draw_image_to_board, write_svg_from_image

UPLOAD_DIR = Path(__file__).resolve().parent / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
DRAWING_STOP_EVENT = threading.Event()
DRAWING_ACTIVE_LOCK = threading.Lock()
DRAWING_ACTIVE = False


def build_page():
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
    .preview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    figure { margin: 0; }
    figcaption { margin-bottom: 6px; font-size: .9rem; font-weight: 600; }
    img { display: block; width: 100%; height: 170px; object-fit: contain; border: 1px solid #d5dfdb; background: #fff; }
    .hint { color: #4c5d57; font-size: .85rem; line-height: 1.5; }
    @media (max-width: 480px) { .preview-grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <h1>白板に描く画像を選ぶ</h1>
    <form method="post" enctype="multipart/form-data">
      <label for="image">画像</label>
      <input id="image" name="image" type="file" accept="image/*" required />
      <div class="preview-grid" style="margin-top:14px;">
        <figure><figcaption>選択した画像</figcaption><img id="inputPreview" alt="選択した画像" /></figure>
        <figure><figcaption>変換後の線画</figcaption><img id="svgPreview" alt="変換後SVG" /></figure>
      </div>
      <label for="size">描画サイズ (mm)</label>
      <input id="size" name="size" type="number" min="20" max="500" value="180" />
      <label for="x">X位置 (mm)</label>
      <input id="x" name="x" type="number" min="150" max="1150" value="650" />
      <label for="y">Y位置 (mm)</label>
      <input id="y" name="y" type="number" min="200" max="950" value="700" />
      <button class="secondary" name="action" value="preview" type="submit">変換プレビューを作る</button>
      <button name="action" value="draw" type="submit">この画像を描画する</button>
      <button id="stopBtn" class="danger" type="button">停止して原点へ戻す</button>
    </form>
    <p class="hint">プレビューは SVG への変換結果です。描画中に停止すると、ペンを上げて原点に戻ります。</p>
    <div id="result" class="notice" hidden></div>
  </main>
  <script>
    const input = document.getElementById('image');
    const inputPreview = document.getElementById('inputPreview');
    const svgPreview = document.getElementById('svgPreview');
    const result = document.getElementById('result');
    const params = new URLSearchParams(location.search);
    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      if (file) inputPreview.src = URL.createObjectURL(file);
    });
    if (params.get('source')) inputPreview.src = '/uploads/' + encodeURIComponent(params.get('source'));
    if (params.get('preview')) svgPreview.src = '/uploads/' + encodeURIComponent(params.get('preview'));
    if (params.get('message')) {
      result.hidden = false;
      result.textContent = params.get('message');
    }
    document.getElementById('stopBtn').addEventListener('click', async () => {
      const response = await fetch('/stop', { method: 'POST' });
      result.hidden = false;
      result.textContent = await response.text();
    });
  </script>
</body>
</html>
"""


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
    if file_data is None:
        raise ValueError('画像ファイルが見つかりません')
    return fields, file_name or 'upload.png', file_data


class ImageUploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
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
            image_path = save_uploaded_file(file_name, file_data)
            svg_path = image_path.with_suffix('.svg')
            write_svg_from_image(image_path, svg_path, target_width=220, threshold=200)
            action = fields.get('action', 'draw')
            if action == 'draw':
                DRAWING_STOP_EVENT.clear()
                set_drawing_active(True)
                try:
                    draw_image_to_board(
                        image_path,
                        size=float(fields.get('size') or 180),
                        x=float(fields.get('x') or 650),
                        y=float(fields.get('y') or 700),
                        dry=False,
                        threshold=200,
                        should_stop=DRAWING_STOP_EVENT.is_set,
                    )
                finally:
                    set_drawing_active(False)
                message = '停止して原点へ戻りました。' if DRAWING_STOP_EVENT.is_set() else '描画が完了しました。'
            else:
                message = '変換プレビューを作成しました。'
            location = '/?message={}&source={}&preview={}'.format(
                quote(message), quote(image_path.name), quote(svg_path.name)
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
