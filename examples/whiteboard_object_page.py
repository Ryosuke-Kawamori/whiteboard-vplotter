"""複数オブジェクト対応のWhiteboard Composerページ。"""


def build_page():
    return r'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Whiteboard Composer</title>
  <style>
    :root { color-scheme:light; --ink:#17211e; --green:#126b52; --line:#aab9b3; --paper:#fff; }
    * { box-sizing:border-box; }
    body { margin:0; padding:20px; background:#eaf0ee; color:var(--ink); font-family:"Noto Sans CJK JP","Hiragino Sans",sans-serif; }
    main { max-width:760px; margin:auto; }
    h1 { margin:0 0 16px; font-size:1.45rem; }
    form { padding:18px; background:var(--paper); border:1px solid #d5dfdb; border-radius:8px; }
    label { display:block; margin:12px 0 6px; font-weight:600; }
    input, textarea, button { width:100%; min-height:44px; padding:10px 12px; border:1px solid var(--line); border-radius:6px; font:inherit; }
    .single-line-toggle { display:flex; align-items:center; gap:10px; margin-top:10px; }
    .single-line-toggle input[type="checkbox"] { width:18px; min-width:18px; max-width:18px; height:18px; min-height:18px; margin:0; padding:0; }
    .single-line-toggle span { font-weight:600; }
    textarea { min-height:96px; resize:vertical; line-height:1.5; }
    button { margin-top:10px; border:0; background:var(--green); color:#fff; font-weight:700; cursor:pointer; }
    button.secondary { background:#3d5750; }
    button.danger { background:#a62929; }
    button.remove { background:#fff; color:#a62929; border:1px solid #c96a6a; }
    .mode-switch { display:grid; grid-template-columns:1fr 1fr; gap:4px; padding:4px; background:#dbe5e1; border-radius:8px; }
    .mode-switch button { margin:0; background:transparent; color:#31443e; }
    .mode-switch button.active { background:#fff; color:var(--green); box-shadow:0 1px 3px #0002; }
    .stage-label { margin:16px 0 6px; font-size:.9rem; font-weight:600; }
    #stage { position:relative; width:100%; aspect-ratio:2/1; overflow:hidden; border:1px solid #9eaca7; background:#fff; }
    #svgPreview { display:block; width:100%; height:100%; object-fit:contain; pointer-events:none; }
    #objectLayer { position:absolute; inset:0; }
    .text-box { position:absolute; min-width:72px; max-width:48%; padding:5px 8px; border:1px dashed #14765b; background:#e8fff6d9; color:#18352c; white-space:pre-wrap; overflow-wrap:anywhere; cursor:grab; touch-action:none; transform:translate(-50%,-50%); line-height:1.25; }
    .text-box.selected { border:2px solid #0b6048; box-shadow:0 0 0 3px #75c8aa66; z-index:2; }
    .text-box.dragging { cursor:grabbing; }
    .toolbar { display:grid; grid-template-columns:1fr auto; gap:8px; align-items:end; }
    .toolbar button { width:auto; min-width:48px; }
    .coordinates { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .size-controls { display:grid; grid-template-columns:1fr 96px; gap:10px; align-items:center; }
    output { display:block; margin-top:5px; font-variant-numeric:tabular-nums; }
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
    <input id="boxes" name="boxes" type="hidden" value="[]" />
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
      <div class="toolbar">
        <label for="text">選択中の文字ボックス</label>
        <button id="addText" type="button" title="文字ボックスを追加">＋ 追加</button>
      </div>
      <textarea id="text" placeholder="今週の目標&#10;安全第一"></textarea>
      <label class="single-line-toggle" for="singleLineToggle">
        <input id="singleLineToggle" type="checkbox" />
        <span>single-line</span>
      </label>
      <button id="removeText" class="remove" type="button">選択中のボックスを削除</button>
    </div>
    <div class="stage-label">白板プレビュー</div>
    <div id="stage">
      <img id="svgPreview" alt="描画プレビュー" />
      <div id="objectLayer"></div>
    </div>
    <label id="sizeLabel" for="size">描画幅</label>
    <div class="size-controls">
      <input id="size" name="size" type="range" min="20" max="500" step="5" value="180" />
      <input id="sizeNumber" type="number" min="20" max="500" step="5" value="180" aria-label="サイズ (mm)" />
    </div>
    <output id="sizeOutput" for="size">180 mm</output>
    <div class="coordinates">
      <div><label for="x">中心X位置 (mm)</label><input id="x" name="x" type="number" min="250" max="1650" value="950" /></div>
      <div><label for="y">中心Y位置 (mm)</label><input id="y" name="y" type="number" min="200" max="920" value="560" /></div>
    </div>
    <button class="secondary" name="action" value="preview" type="submit">プレビューを作る</button>
    <button name="action" value="draw" type="submit">白板に描画する</button>
    <button id="stopBtn" class="danger" type="button">停止して原点へ戻す</button>
  </form>
  <p class="hint">文字ボックスを選択して編集します。白板上の枠をドラッグすると個別に移動できます。</p>
  <div id="result" class="notice" hidden></div>
</main>
<script>
  const byId = id => document.getElementById(id);
  const mode = byId('mode'), imageMode = byId('imageMode'), textMode = byId('textMode');
  const imageControls = byId('imageControls'), textControls = byId('textControls');
  const image = byId('image'), source = byId('source'), text = byId('text');
  const singleLineToggle = byId('singleLineToggle');
  const boxesInput = byId('boxes'), layer = byId('objectLayer'), preview = byId('svgPreview');
  const size = byId('size'), sizeNumber = byId('sizeNumber'), sizeLabel = byId('sizeLabel'), sizeOutput = byId('sizeOutput');
  const x = byId('x'), y = byId('y'), result = byId('result');
  const params = new URLSearchParams(location.search);
  let textBoxes = [], selectedId = null, nextId = 1, previewTimer, previewRunning = false, previewPending = false, dragStart;

  function clamp(value, control) { return Math.min(Number(control.max), Math.max(Number(control.min), value)); }
  function selectedBox() { return textBoxes.find(box => box.id === selectedId); }
  function serializeBoxes() { boxesInput.value = JSON.stringify(textBoxes.map(({id, ...box}) => box)); }

  function renderBoxes() {
    layer.replaceChildren();
    if (mode.value !== 'text') return;
    for (const box of textBoxes) {
      const item = document.createElement('div');
      item.className = 'text-box' + (box.id === selectedId ? ' selected' : '');
      item.dataset.id = box.id;
      item.textContent = box.text || '文字を入力';
      item.style.left = `${box.x / 18}%`;
      item.style.top = `${(box.y - 100) / 9}%`;
      item.style.fontSize = `${Math.max(11, box.size / 7)}px`;
      item.addEventListener('pointerdown', startBoxDrag);
      layer.append(item);
    }
    serializeBoxes();
  }

  function selectBox(id) {
    selectedId = id;
    const box = selectedBox();
    if (box) { text.value = box.text; size.value = box.size; sizeNumber.value = box.size; x.value = box.x; y.value = box.y; singleLineToggle.checked = !!box.singleLine; }
    text.disabled = !box; size.disabled = !box; sizeNumber.disabled = !box; x.disabled = !box; y.disabled = !box; singleLineToggle.disabled = !box;
    sizeOutput.value = box ? `${box.size} mm` : '-';
    renderBoxes();
  }

  function addTextBox(initial={}) {
    const offset = textBoxes.length * 35;
    const box = {
      id:nextId++,
      text:initial.text || '新しい文字',
      size:Number(initial.size || 90),
      x:Number(initial.x ?? 950 + offset),
      y:Number(initial.y ?? 560 + offset),
      singleLine:Boolean(initial.singleLine || initial['single-line']),
    };
    textBoxes.push(box);
    selectBox(box.id);
    schedulePreview();
  }

  function setMode(nextMode, refresh=true) {
    mode.value = nextMode;
    const isText = nextMode === 'text';
    imageControls.hidden = isText; textControls.hidden = !isText;
    imageMode.classList.toggle('active', !isText); textMode.classList.toggle('active', isText);
    sizeLabel.textContent = isText ? '選択中の文字の高さ' : '描画幅';
    size.max = sizeNumber.max = isText ? '300' : '500';
    layer.hidden = !isText;
    if (isText && !textBoxes.length) addTextBox();
    if (isText) selectBox(selectedId || textBoxes[0].id);
    else { size.disabled = false; sizeNumber.disabled = false; sizeNumber.value = size.value; x.disabled = false; y.disabled = false; renderBoxes(); }
    if (refresh) schedulePreview();
  }

  function syncSelected() {
    const box = selectedBox();
    if (!box) return;
    box.text = text.value; box.size = Number(size.value); box.x = Number(x.value); box.y = Number(y.value); box.singleLine = singleLineToggle.checked;
    sizeOutput.value = `${box.size} mm`; renderBoxes(); schedulePreview();
  }

  async function updatePreview() {
    if (mode.value === 'image' && !source.value) return;
    if (mode.value === 'text' && !textBoxes.some(box => box.text.trim())) return;
    if (previewRunning) { previewPending = true; return; }
    previewRunning = true;
    previewPending = false;
    serializeBoxes();
    const query = new URLSearchParams({
      mode: mode.value,
      source: source.value,
      boxes: boxesInput.value,
      singleLine: String(Boolean(mode.value === 'text' && selectedBox()?.singleLine)),
      size: size.value,
      x: x.value,
      y: y.value,
    });
    try {
      result.hidden = false;
      result.textContent = 'プレビューを生成中...';
      const response = await fetch('/preview?' + query);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'プレビューを更新できません');
      preview.src = data.preview + '?t=' + Date.now(); result.hidden = false; result.textContent = data.message;
      history.replaceState(null, '', '/?' + new URLSearchParams({
        mode: mode.value,
        source: source.value,
        boxes: boxesInput.value,
        singleLine: String(Boolean(mode.value === 'text' && selectedBox()?.singleLine)),
        preview: data.preview.split('/').pop(),
        size: size.value,
        x: x.value,
        y: y.value,
      }));
    } catch (error) {
      result.hidden = false;
      result.textContent = error.message;
    } finally {
      previewRunning = false;
      if (previewPending) schedulePreview();
    }
  }
  function schedulePreview() { clearTimeout(previewTimer); previewTimer = setTimeout(updatePreview, 500); }

  function startBoxDrag(event) {
    selectedId = Number(event.currentTarget.dataset.id);
    const box = selectedBox();
    text.value = box.text; size.value = box.size; sizeNumber.value = box.size; x.value = box.x; y.value = box.y;
    sizeOutput.value = `${box.size} mm`;
    for (const item of layer.children) item.classList.toggle('selected', item === event.currentTarget);
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.classList.add('dragging');
    dragStart = {node:event.currentTarget, clientX:event.clientX, clientY:event.clientY, x:box.x, y:box.y};
  }
  layer.addEventListener('pointermove', event => {
    if (!dragStart) return;
    const rect = layer.getBoundingClientRect(), box = selectedBox();
    box.x = Math.round(clamp(dragStart.x + (event.clientX - dragStart.clientX) * 1800 / rect.width, x));
    box.y = Math.round(clamp(dragStart.y + (event.clientY - dragStart.clientY) * 900 / rect.height, y));
    x.value = box.x; y.value = box.y;
    dragStart.node.style.left = `${box.x / 18}%`;
    dragStart.node.style.top = `${(box.y - 100) / 9}%`;
    serializeBoxes(); schedulePreview();
  });
  function endDrag() { if (dragStart) dragStart.node.classList.remove('dragging'); dragStart = null; }
  layer.addEventListener('pointerup', endDrag); layer.addEventListener('pointercancel', endDrag);

  const previewButton = document.querySelector('button[name="action"][value="preview"]');
  previewButton.addEventListener('click', event => {
    if (mode.value === 'text' || mode.value === 'image') {
      event.preventDefault();
      serializeBoxes();
      schedulePreview();
    }
  });
  byId('addText').addEventListener('click', () => addTextBox());
  byId('removeText').addEventListener('click', () => { textBoxes = textBoxes.filter(box => box.id !== selectedId); selectedId = textBoxes[0]?.id || null; if (!textBoxes.length) addTextBox(); else { selectBox(selectedId); schedulePreview(); } });
  imageMode.addEventListener('click', () => setMode('image')); textMode.addEventListener('click', () => setMode('text'));
  image.addEventListener('change', () => { if (image.files.length) source.value = ''; });
  text.addEventListener('input', syncSelected);
  singleLineToggle.addEventListener('change', syncSelected);
  size.addEventListener('input', () => { sizeNumber.value = size.value; mode.value === 'text' ? syncSelected() : schedulePreview(); });
  sizeNumber.addEventListener('input', () => {
    size.value = clamp(Number(sizeNumber.value), size);
    sizeNumber.value = size.value;
    mode.value === 'text' ? syncSelected() : schedulePreview();
  });
  for (const control of [x, y]) control.addEventListener('input', () => mode.value === 'text' ? syncSelected() : schedulePreview());

  if (params.get('source')) source.value = params.get('source');
  try { const saved = JSON.parse(params.get('boxes') || '[]'); for (const box of saved) addTextBox(box); } catch (_) {}
  for (const control of [size, x, y]) if (params.get(control.id)) control.value = params.get(control.id);
  sizeNumber.value = size.value;
  setMode(params.get('mode') === 'text' ? 'text' : 'image', false);
  if (params.get('preview')) preview.src = '/uploads/' + encodeURIComponent(params.get('preview'));
  if (params.get('message')) { result.hidden = false; result.textContent = params.get('message'); }
  byId('stopBtn').addEventListener('click', async () => { const response = await fetch('/stop', {method:'POST'}); result.hidden = false; result.textContent = await response.text(); });
</script>
</body>
</html>'''
