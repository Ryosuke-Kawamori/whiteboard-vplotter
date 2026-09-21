"""Whiteboard Composer のHTMLページ。"""


def build_page():
    return """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Whiteboard Composer</title>
  <style>
    :root { color-scheme: light; --ink:#15201d; --green:#126b52; --line:#aab9b3; }
    body { margin:0; padding:20px; background:#edf2f1; color:var(--ink); font-family:"Noto Sans CJK JP","Hiragino Sans",sans-serif; }
    main { max-width:680px; margin:0 auto; }
    h1 { margin:0 0 16px; font-size:1.45rem; }
    form { padding:18px; background:#fff; border:1px solid #d5dfdb; border-radius:8px; }
    label { display:block; margin:14px 0 6px; font-weight:600; }
    input, textarea, button { box-sizing:border-box; width:100%; min-height:44px; padding:10px 12px; border:1px solid var(--line); border-radius:6px; font:inherit; }
    textarea { min-height:120px; resize:vertical; font-size:1.1rem; line-height:1.5; }
    button { margin-top:12px; border:0; background:var(--green); color:#fff; font-weight:700; }
    button.secondary { background:#3d5750; }
    button.danger { background:#a62929; }
    .mode-switch { display:grid; grid-template-columns:1fr 1fr; gap:4px; padding:4px; background:#dbe5e1; border-radius:8px; }
    .mode-switch button { margin:0; background:transparent; color:#31443e; }
    .mode-switch button.active { background:#fff; color:var(--green); box-shadow:0 1px 3px #0002; }
    figure { margin:16px 0 0; }
    figcaption { margin-bottom:6px; font-size:.9rem; font-weight:600; }
    img { display:block; width:100%; aspect-ratio:2/1; object-fit:contain; border:1px solid #d5dfdb; background:#fff; }
    #svgPreview.ready { cursor:grab; touch-action:none; }
    #svgPreview.dragging { cursor:grabbing; }
    output { display:block; margin-top:6px; font-variant-numeric:tabular-nums; }
    .hint { color:#4c5d57; font-size:.85rem; line-height:1.5; }
    .notice { margin-top:14px; padding:12px; background:#e1f5ec; border:1px solid #99d6bb; border-radius:6px; }
    [hidden] { display:none !important; }
  </style>
</head>
<body>
  <main>
    <h1>Whiteboard Composer</h1>
    <form method="post" enctype="multipart/form-data">
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
      <figure>
        <figcaption>白板プレビュー</figcaption>
        <img id="svgPreview" alt="描画プレビュー" />
      </figure>
      <label id="sizeLabel" for="size">描画幅</label>
      <input id="size" name="size" type="range" min="20" max="500" step="5" value="180" />
      <output id="sizeOutput" for="size">180 mm</output>
      <label for="x">中心X位置 (mm)</label>
      <input id="x" name="x" type="number" min="250" max="1650" value="950" />
      <label for="y">中心Y位置 (mm)</label>
      <input id="y" name="y" type="number" min="200" max="920" value="560" />
      <button class="secondary" name="action" value="preview" type="submit">プレビューを作る</button>
      <button name="action" value="draw" type="submit">白板に描画する</button>
      <button id="stopBtn" class="danger" type="button">停止して原点へ戻す</button>
    </form>
    <p class="hint">文章を編集するか、白板プレビューをドラッグして位置を調整できます。</p>
    <div id="result" class="notice" hidden></div>
  </main>
  <script>
    const byId = id => document.getElementById(id);
    const mode = byId('mode');
    const imageMode = byId('imageMode');
    const textMode = byId('textMode');
    const imageControls = byId('imageControls');
    const textControls = byId('textControls');
    const image = byId('image');
    const source = byId('source');
    const text = byId('text');
    const preview = byId('svgPreview');
    const size = byId('size');
    const sizeLabel = byId('sizeLabel');
    const sizeOutput = byId('sizeOutput');
    const x = byId('x');
    const y = byId('y');
    const result = byId('result');
    const params = new URLSearchParams(location.search);
    let previewTimer;
    let previewController;
    let dragStart;

    function clamp(value, control) {
      return Math.min(Number(control.max), Math.max(Number(control.min), value));
    }

    function setMode(nextMode, refresh=true) {
      mode.value = nextMode;
      const isText = nextMode === 'text';
      imageControls.hidden = isText;
      textControls.hidden = !isText;
      imageMode.classList.toggle('active', !isText);
      textMode.classList.toggle('active', isText);
      sizeLabel.textContent = isText ? '文字の高さ' : '描画幅';
      size.max = isText ? '300' : '500';
      if (Number(size.value) > Number(size.max)) size.value = size.max;
      sizeOutput.value = size.value + ' mm';
      if (refresh) schedulePreview();
    }

    async function updatePreview() {
      if (mode.value === 'image' && !source.value) return;
      if (mode.value === 'text' && !text.value.trim()) return;
      if (previewController) previewController.abort();
      previewController = new AbortController();
      const query = new URLSearchParams({
        mode:mode.value, source:source.value, text:text.value,
        size:size.value, x:x.value, y:y.value,
      });
      try {
        const response = await fetch('/preview?' + query, { signal:previewController.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'プレビューを更新できません');
        preview.src = data.preview + '?t=' + Date.now();
        preview.classList.add('ready');
        result.hidden = false;
        result.textContent = data.message;
        history.replaceState(null, '', '/?' + new URLSearchParams({
          mode:mode.value, source:source.value, text:text.value,
          preview:data.preview.split('/').pop(), size:size.value,
          x:x.value, y:y.value,
        }));
      } catch (error) {
        if (error.name !== 'AbortError') {
          result.hidden = false;
          result.textContent = error.message;
        }
      }
    }

    function schedulePreview() {
      sizeOutput.value = size.value + ' mm';
      clearTimeout(previewTimer);
      previewTimer = setTimeout(updatePreview, 180);
    }

    image.addEventListener('change', () => { if (image.files.length) source.value = ''; });
    imageMode.addEventListener('click', () => setMode('image'));
    textMode.addEventListener('click', () => setMode('text'));
    text.addEventListener('input', schedulePreview);
    for (const control of [size, x, y]) control.addEventListener('input', schedulePreview);

    if (params.get('source')) source.value = params.get('source');
    if (params.get('text')) text.value = params.get('text');
    for (const control of [size, x, y]) if (params.get(control.id)) control.value = params.get(control.id);
    setMode(params.get('mode') === 'text' ? 'text' : 'image', false);
    if (params.get('preview')) {
      preview.src = '/uploads/' + encodeURIComponent(params.get('preview'));
      preview.classList.add('ready');
    }
    if (params.get('message')) {
      result.hidden = false;
      result.textContent = params.get('message');
    }

    preview.addEventListener('pointerdown', event => {
      if (mode.value === 'image' && !source.value) return;
      if (mode.value === 'text' && !text.value.trim()) return;
      preview.setPointerCapture(event.pointerId);
      preview.classList.add('dragging');
      dragStart = { clientX:event.clientX, clientY:event.clientY, x:Number(x.value), y:Number(y.value) };
    });
    preview.addEventListener('pointermove', event => {
      if (!dragStart) return;
      const rect = preview.getBoundingClientRect();
      x.value = Math.round(clamp(dragStart.x + (event.clientX - dragStart.clientX) * 1800 / rect.width, x));
      y.value = Math.round(clamp(dragStart.y + (event.clientY - dragStart.clientY) * 900 / rect.height, y));
      schedulePreview();
    });
    function endDrag() { dragStart = null; preview.classList.remove('dragging'); }
    preview.addEventListener('pointerup', endDrag);
    preview.addEventListener('pointercancel', endDrag);

    byId('stopBtn').addEventListener('click', async () => {
      const response = await fetch('/stop', { method:'POST' });
      result.hidden = false;
      result.textContent = await response.text();
    });
  </script>
</body>
</html>
"""
