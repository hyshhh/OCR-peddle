/**
 * 实时演示页面逻辑 — WebSocket 视频流
 */

let ws = null;
let streaming = false;
let sourceType = 'camera';
let frameCount = 0;
let lastFrameTime = 0;

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', loadSources);

async function loadSources() {
  try {
    const resp = await fetch('/api/demo/sources');
    const data = await resp.json();

    // 摄像头列表
    const cameraSelect = document.getElementById('cameraSelect');
    cameraSelect.innerHTML = '';
    if (data.cameras.length === 0) {
      cameraSelect.innerHTML = '<option value="">未检测到摄像头</option>';
    } else {
      data.cameras.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.index;
        opt.textContent = c.name;
        cameraSelect.appendChild(opt);
      });
    }

    // 视频文件列表
    const fileSelect = document.getElementById('fileSelect');
    fileSelect.innerHTML = '';
    if (data.videos.length === 0) {
      fileSelect.innerHTML = '<option value="">data/ 目录下无视频文件</option>';
    } else {
      data.videos.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.path;
        opt.textContent = v.name;
        fileSelect.appendChild(opt);
      });
    }

    // 默认帧率
    if (data.default_fps) {
      document.getElementById('fpsSlider').value = data.default_fps;
      document.getElementById('fpsValue').textContent = data.default_fps;
    }

    addLog('info', `探测完成：${data.cameras.length} 个摄像头，${data.videos.length} 个视频文件`);
  } catch (e) {
    addLog('error', '视频源加载失败: ' + e.message);
  }
}

// ── 切换视频源类型 ──
function switchSource(type) {
  sourceType = type;
  document.querySelectorAll('.source-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.type === type);
  });
  document.getElementById('cameraGroup').style.display = type === 'camera' ? '' : 'none';
  document.getElementById('fileGroup').style.display = type === 'file' ? '' : 'none';
}

// ── 开始推流 ──
function startStream() {
  if (streaming) return;

  let sourceValue;
  if (sourceType === 'camera') {
    sourceValue = parseInt(document.getElementById('cameraSelect').value);
    if (isNaN(sourceValue)) {
      addLog('error', '请选择摄像头');
      return;
    }
  } else {
    sourceValue = document.getElementById('fileSelect').value;
    if (!sourceValue) {
      addLog('error', '请选择视频文件');
      return;
    }
  }

  const fps = parseInt(document.getElementById('fpsSlider').value);
  frameCount = 0;

  // 建立 WebSocket
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/api/demo/ws/stream`);

  ws.onopen = () => {
    streaming = true;
    updateUI(true);
    addLog('info', `连接建立，正在启动 ${sourceType === 'camera' ? '摄像头' : '视频文件'}…`);
    ws.send(JSON.stringify({
      source_type: sourceType,
      source_value: sourceValue,
      fps: fps,
    }));
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleServerMessage(msg);
  };

  ws.onerror = (e) => {
    addLog('error', 'WebSocket 错误');
    stopStream();
  };

  ws.onclose = () => {
    if (streaming) {
      addLog('warn', '连接被关闭');
      stopStream();
    }
  };
}

// ── 停止推流 ──
function stopStream() {
  if (ws) {
    ws.close();
    ws = null;
  }
  streaming = false;
  updateUI(false);
  addLog('info', `已停止，共接收 ${frameCount} 帧`);
}

// ── 处理服务端消息 ──
function handleServerMessage(msg) {
  switch (msg.type) {
    case 'meta':
      document.getElementById('resolution').textContent = `${msg.width}×${msg.height}`;
      addLog('info', `视频源就绪：${msg.width}×${msg.height}，原始 ${Math.round(msg.fps)} FPS`);
      break;

    case 'frame':
      frameCount = msg.index;
      document.getElementById('frameCount').textContent = frameCount;

      // 延迟计算
      const now = performance.now();
      if (lastFrameTime > 0) {
        const delta = now - lastFrameTime;
        document.getElementById('latency').textContent = `${Math.round(delta)}ms`;
      }
      lastFrameTime = now;

      // 渲染帧
      renderFrame(msg.frame);
      break;

    case 'ended':
      addLog('info', `视频播放完毕，共 ${msg.frames} 帧`);
      stopStream();
      break;

    case 'error':
      addLog('error', msg.message);
      stopStream();
      break;
  }
}

// ── 渲染帧 ──
function renderFrame(base64Frame) {
  const placeholder = document.getElementById('viewportPlaceholder');
  const img = document.getElementById('videoImg');
  placeholder.style.display = 'none';
  img.style.display = 'block';
  img.src = 'data:image/jpeg;base64,' + base64Frame;
}

// ── UI 状态更新 ──
function updateUI(isStreaming) {
  document.getElementById('btnStart').disabled = isStreaming;
  document.getElementById('btnStop').disabled = !isStreaming;
  document.getElementById('statusText').textContent = isStreaming ? '推流中' : '待机';
  document.getElementById('statusText').style.color = isStreaming ? 'var(--success)' : '';

  if (!isStreaming) {
    document.getElementById('frameCount').textContent = '0';
    document.getElementById('latency').textContent = '-';
    lastFrameTime = 0;
  }
}

// ── 日志 ──
function addLog(level, text) {
  const logBody = document.getElementById('logBody');
  const time = new Date().toLocaleTimeString();
  const entry = document.createElement('div');
  entry.className = 'log-entry log-' + level;
  entry.textContent = `[${time}] ${text}`;
  logBody.appendChild(entry);
  logBody.scrollTop = logBody.scrollHeight;
}

function clearLog() {
  document.getElementById('logBody').innerHTML = '';
}

// ── 页面关闭时清理 ──
window.addEventListener('beforeunload', () => {
  if (ws) ws.close();
});
