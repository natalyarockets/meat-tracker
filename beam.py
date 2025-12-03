import subprocess
import time
import threading
import asyncio
from collections import deque
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import datetime

app = FastAPI()

latest_rssi = None
baseline = None
threshold = 6   # dB drop = HUMAN detected
mode = "air"
thresholds = {"air": 6, "wall": 10}
history = deque(maxlen=600)  # keep ~10 minutes of 1s samples
BASELINE_PATH = Path("baseline.txt")
last_photo_path = None
last_detected = False


def read_rssi_wdutil():
    try:
        out = subprocess.check_output(
            ["sudo", "wdutil", "info"],
            text=True,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        return None, None

    rssi = None
    noise = None

    for line in out.splitlines():
        line = line.strip()

        if line.startswith("RSSI"):
            try:
                rssi = int(line.split(":")[1].replace("dBm", "").strip())
            except:
                pass

        if line.startswith("Noise"):
            try:
                noise = int(line.split(":")[1].replace("dBm", "").strip())
            except:
                pass

    return rssi, noise


def load_baseline():
    global baseline
    if not BASELINE_PATH.exists():
        return
    try:
        baseline = int(BASELINE_PATH.read_text().strip())
    except Exception:
        baseline = None


def persist_baseline(value: int):
    try:
        BASELINE_PATH.write_text(str(value))
    except Exception:
        pass


def take_photo():
    global last_photo_path

    os.makedirs("photos", exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"photos/capture_{ts}.jpg"

    try:
        subprocess.run(["imagesnap", "-w", "0.8", filename], check=True)
        last_photo_path = filename
    except Exception as exc:
        print(f"ERROR capturing photo: {exc}")


def sampler_loop():
    global latest_rssi, history, last_detected
    while True:
        try:
            rssi, noise = read_rssi_wdutil()
            latest_rssi = rssi

            if rssi is not None:
                history.append((time.time(), rssi))

            if baseline is not None and rssi is not None:
                detected_now = (rssi <= baseline - threshold)

                if detected_now and not last_detected:
                    take_photo()

                last_detected = detected_now

        except Exception as exc:
            print(f"ERROR: sampler loop failed: {exc}")
        time.sleep(1)


def warm_camera():
    try:
        os.makedirs("photos", exist_ok=True)
        subprocess.run(["imagesnap", "-w", "1", "photos/warmup.jpg"], check=False)
    except Exception:
        pass
    try:
        os.remove("photos/warmup.jpg")
    except:
        pass


@app.on_event("startup")
def start_sampler():
    load_baseline()
    warm_camera()
    thread = threading.Thread(target=sampler_loop, daemon=True)
    thread.start()


app.mount("/photos", StaticFiles(directory="photos"), name="photos")


@app.post("/calibrate")
def calibrate():
    global baseline
    if latest_rssi is None:
        return {"error": "No RSSI yet"}
    baseline = latest_rssi
    persist_baseline(baseline)
    return {"baseline": baseline}


@app.post("/threshold")
def set_threshold(value: int):
    global threshold, mode, thresholds
    if value < 1:
        value = 1
    if value > 40:
        value = 40
    threshold = value
    thresholds[mode] = value
    return {"threshold": threshold}


@app.post("/mode")
def set_mode(new_mode: str):
    global mode, threshold, thresholds
    if new_mode not in ("air", "wall"):
        return {"error": "invalid mode"}
    mode = new_mode
    if mode in thresholds:
        threshold = thresholds[mode]
    else:
        thresholds[mode] = threshold
    return {"mode": mode, "threshold": threshold}


def build_metrics_payload():
    global latest_rssi, baseline, threshold, mode, thresholds, history, last_photo_path

    detected = False
    if latest_rssi is not None and baseline is not None:
        detected = (latest_rssi <= baseline - threshold)

    photo_url = None
    if last_photo_path:
        # Serve via /photos/<filename>
        photo_url = f"/photos/{os.path.basename(last_photo_path)}"

    return {
        "rssi": latest_rssi,
        "baseline": baseline,
        "mode": mode,
        "threshold": threshold,
        "detected": detected,
        "photo_url": photo_url,
        "history": [
            {"t": int(ts * 1000), "rssi": val}
            for ts, val in history
        ],
    }


@app.get("/metrics")
def metrics():
    return build_metrics_payload()


@app.websocket("/ws")
async def websocket_metrics(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = build_metrics_payload()
            await ws.send_json(payload)
            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        pass


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Beam Detector</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
:root {
    --bg: #0f172a;
    --card: #111827;
    --accent: #22d3ee;
    --accent-2: #f59e0b;
    --text: #e5e7eb;
    --muted: #9ca3af;
    --ok: #10b981;
    --alert: #ef4444;
}
* { box-sizing: border-box; }
body {
    margin: 0; padding: 0;
    font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
    background: radial-gradient(circle at 20% 20%, #1f2937 0, #0f172a 40%, #0b1224 100%);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
}
.frame {
    width: min(900px, 92vw);
    background: linear-gradient(145deg, rgba(17,24,39,0.9), rgba(24,24,27,0.9));
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 20px;
    padding: 32px;
    box-shadow: 0 25px 50px rgba(0,0,0,0.45);
}
h1 {
    margin: 0 0 12px;
    font-size: 34px;
    letter-spacing: -0.02em;
    display: flex;
    gap: 12px;
    align-items: center;
}
h1 span {
    display: inline-flex;
    padding: 6px 12px;
    border-radius: 12px;
    background: rgba(34,211,238,0.12);
    border: 1px solid rgba(34,211,238,0.3);
    color: var(--accent);
    font-size: 16px;
}
.sub {
    color: var(--muted);
    margin-bottom: 24px;
    font-size: 16px;
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
}
.card {
    background: var(--card);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 14px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.label { color: var(--muted); font-size: 14px; }
.value { font-size: 32px; font-weight: 700; letter-spacing: -0.01em; }
.badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 18px;
    border: 1px solid rgba(255,255,255,0.08);
    margin-top: 10px;
}
.ok { color: var(--ok); background: rgba(16,185,129,0.12); border-color: rgba(16,185,129,0.35); }
.alert { color: var(--alert); background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.35); }
.actions { margin-top: 22px; display: flex; gap: 12px; flex-wrap: wrap; }
.toggles { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
button.chip {
    background: rgba(255,255,255,0.06);
    color: var(--text);
    border: 1px solid rgba(255,255,255,0.12);
    box-shadow: none;
}
button.chip.active {
    background: rgba(34,211,238,0.16);
    border-color: rgba(34,211,238,0.45);
    color: var(--accent);
}
.mode-toggle-row {
    display: inline-flex;
    gap: 6px;
    margin-left: 6px;
}
button {
    font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
    font-size: 16px;
    padding: 12px 18px;
    border-radius: 12px;
    border: none;
    cursor: pointer;
    color: #0b1224;
    background: linear-gradient(135deg, var(--accent), #1db2c8);
    font-weight: 700;
    transition: transform 0.08s ease, box-shadow 0.12s ease;
}
button:hover { transform: translateY(-1px); box-shadow: 0 12px 24px rgba(34,211,238,0.25); }
button:active { transform: translateY(0); box-shadow: none; }
.muted { color: var(--muted); font-size: 14px; margin-top: 6px; }

.chart-card {
    margin-top: 24px;
    background: var(--card);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 16px;
    padding: 16px;
}

/* Fixed layout for chart + photo, to prevent vertical jumping */
#chartContainer {
    position: relative;
    z-index: 1;
    height: 260px; /* matches chart logical height */
}

#photoContainer {
    position: relative;
    z-index: 2;
    margin-top: 30px;
}

#chart {
    width: 100%;
    height: 100%;  /* fill the fixed container height */
    border-radius: 12px;
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0));
    border: 1px solid rgba(255,255,255,0.06);
}

#photoBox {
    width: 100%;
    height: 320px;   /* fixed, so adding an image never changes layout */
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
}

#photoBox img {
    max-height: 100%;
    max-width: 100%;
    object-fit: contain;
    opacity: 0;
    transition: opacity 0.4s ease;
}
</style>
</head>
<body>

<div class="frame">
  <h1>Wi-Fi Presence <span>Live</span></h1>
  <div class="sub">Monitors RSSI drops against a calibrated baseline. Run calibration when no one is in the path.</div>

  <div id="status" class="badge ok">Waiting for signal...</div>

  <div class="grid">
    <div class="card">
      <div class="label">Current RSSI</div>
      <div class="value"><span id="rssi">?</span> dBm</div>
      <div class="muted">Updates every second</div>
    </div>
    <div class="card">
      <div class="label">Baseline</div>
      <div class="value"><span id="baseline">?</span> dBm</div>
      <div class="muted">Persisted across restarts</div>
    </div>
    <div class="card">
      <div class="label">Threshold</div>
      <div class="value"><span id="threshold">6</span> dB</div>
      <div class="muted">Drop relative to baseline</div>
      <div class="muted">
        <label for="threshold-input">Set threshold:</label>
        <input id="threshold-input" type="number" value="6" min="1" max="40" onchange="updateThreshold()" style="width: 80px; margin-left: 6px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.12); background: rgba(15,23,42,0.9); color: #e5e7eb; padding: 4px 8px;" />
      </div>
      <div class="muted" style="margin-top: 8px;">
        Mode:
        <div class="mode-toggle-row">
          <button class="chip mode-chip active" data-mode="air" onclick="setModeClick(this)">Air</button>
          <button class="chip mode-chip" data-mode="wall" onclick="setModeClick(this)">Wall</button>
        </div>
      </div>
    </div>
  </div>

  <div class="actions">
    <button onclick="doCalibrate()">Calibrate (no human present)</button>
    <div class="toggles">
      <button class="chip active" data-rate="300" onclick="setRate(this)">300 ms</button>
      <button class="chip" data-rate="500" onclick="setRate(this)">500 ms</button>
      <button class="chip" data-rate="1000" onclick="setRate(this)">1 s</button>
      <button class="chip" data-rate="2000" onclick="setRate(this)">2 s</button>
    </div>
    <div class="muted">Refresh rate: <span id="rate-label">300 ms</span></div>
  </div>

  <div class="chart-card">
    <div class="chart-head">
      <div>
        <div class="title">RSSI Over Time</div>
        <div class="subtle">Latest samples from the sampler loop</div>
      </div>
      <div class="chart-legend">
        <span><span class="dot live"></span>Live RSSI</span>
        <span><span class="dot base"></span>Baseline</span>
      </div>
    </div>

    <div id="chartContainer">
        <canvas id="chart"></canvas>
    </div>

    <div id="photoContainer">
        <div id="photoBox"></div>
    </div>

  </div>
</div>

<script>
let threshold = 6;
let mode = "air";
let pollMs = 300;
let chartPoints = [];
let lastBaseline = null;
let socket = null;
let lastPhotoUrl = null;

const canvas = document.getElementById("chart");
const ctx = canvas.getContext("2d");
const dpr = window.devicePixelRatio || 1;
let chartSize = {width: 0, height: 0};

const chartContainer = document.getElementById("chartContainer");

function resizeCanvas() {
    const rect = chartContainer.getBoundingClientRect();
    chartSize = {width: rect.width, height: rect.height};
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function renderChart(points, baseline) {
    if (!canvas) return;
    if (!chartSize.width || !chartSize.height) {
        resizeCanvas();
    }

    ctx.clearRect(0, 0, chartSize.width, chartSize.height);

    if (!points || !points.length) {
        ctx.fillStyle = 'rgba(229,231,235,0.6)';
        ctx.font = '14px Space Grotesk, sans-serif';
        ctx.fillText('Waiting for samples…', 16, chartSize.height / 2);
        return;
    }

    const xs = points.map(p => p.t);
    const ys = points.map(p => p.rssi);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys, baseline ?? ys[0]);
    const maxY = Math.max(...ys, baseline ?? ys[0]);
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const margin = 18;

    const x = t => {
        const n = (t - minX) / spanX;
        return margin + n * (chartSize.width - margin * 2);
    };

    const y = v => {
        const n = (v - minY) / spanY;
        return chartSize.height - margin - n * (chartSize.height - margin * 2);
    };

    if (baseline !== null && baseline !== undefined) {
        ctx.save();
        ctx.setLineDash([6, 6]);
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(x(minX), y(baseline));
        ctx.lineTo(x(maxX), y(baseline));
        ctx.stroke();
        ctx.restore();
    }

    ctx.beginPath();
    ctx.moveTo(x(points[0].t), y(points[0].rssi));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(x(points[i].t), y(points[i].rssi));
    }
    ctx.lineTo(x(points[points.length - 1].t), chartSize.height - margin);
    ctx.lineTo(x(points[0].t), chartSize.height - margin);
    ctx.closePath();

    const gradient = ctx.createLinearGradient(0, margin, 0, chartSize.height - margin);
    gradient.addColorStop(0, 'rgba(34,211,238,0.3)');
    gradient.addColorStop(1, 'rgba(34,211,238,0.02)');
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(x(points[0].t), y(points[0].rssi));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(x(points[i].t), y(points[i].rssi));
    }
    ctx.strokeStyle = '#22d3ee';
    ctx.lineWidth = 2;
    ctx.stroke();

    const lastPoint = points[points.length - 1];
    ctx.fillStyle = '#22d3ee';
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x(lastPoint.t), y(lastPoint.rssi), 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
}
function handleMetricsData(data) {
    document.getElementById("rssi").textContent = data.rssi ?? "?";
    document.getElementById("baseline").textContent =
        data.baseline === null ? "?" : data.baseline;

    if (typeof data.mode === "string") {
        mode = data.mode;
        const buttons = document.querySelectorAll(".mode-chip");
        buttons.forEach(b => {
            if (b.getAttribute("data-mode") === mode) {
                b.classList.add("active");
            } else {
                b.classList.remove("active");
            }
        });
    }
    if (typeof data.threshold === "number") {
        threshold = data.threshold;
    }
    document.getElementById("threshold").textContent = threshold;
    const thresholdInput = document.getElementById("threshold-input");
    if (thresholdInput && document.activeElement !== thresholdInput) {
        thresholdInput.value = threshold;
    }

    chartPoints = data.history || [];
    lastBaseline = data.baseline;
    renderChart(chartPoints, lastBaseline);

    const photoBox = document.getElementById("photoBox");
    if (photoBox) {
        const url = data.photo_url;
        // Only update the DOM if the photo URL actually changed
        if (url && url !== lastPhotoUrl) {
            lastPhotoUrl = url;
            photoBox.innerHTML = "";
            const img = document.createElement("img");
            img.src = url + `?t=${Date.now()}`; // cache-bust so latest photo loads
            img.onload = () => {
                img.style.opacity = "1";
            };
            photoBox.appendChild(img);
        }
    }

    const status = document.getElementById("status");
    if (data.detected) {
        status.textContent = "Presence detected";
        status.className = "badge alert";
    } else if (data.rssi === null) {
        status.textContent = "Waiting for RSSI...";
        status.className = "badge ok";
    } else {
        status.textContent = "Path is clear";
        status.className = "badge ok";
    }
}

function connectWebSocket() {
    const wsProtocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${wsProtocol}://${location.host}/ws`);

    socket.onopen = () => {
        console.log("WebSocket connected");
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMetricsData(data);
        } catch (e) {
            console.error("Failed to parse WS message", e);
        }
    };

    socket.onclose = () => {
        console.log("WebSocket closed, retrying in 2s...");
        setTimeout(connectWebSocket, 2000);
        const status = document.getElementById("status");
        status.textContent = "Connection lost";
        status.className = "badge alert";
    };

    socket.onerror = (err) => {
        console.error("WebSocket error", err);
    };
}

async function setMode(newMode) {
    if (!newMode) return;
    try {
        const res = await fetch(`/mode?new_mode=${encodeURIComponent(newMode)}`, { method: "POST" });
        const data = await res.json();
        if (data.error) return;
        if (typeof data.mode === "string") {
            mode = data.mode;
        }
        if (typeof data.threshold === "number") {
            threshold = data.threshold;
            document.getElementById("threshold").textContent = threshold;
            const input = document.getElementById("threshold-input");
            if (input) {
                input.value = threshold;
            }
        }
        const buttons = document.querySelectorAll(".mode-chip");
        buttons.forEach(b => {
            if (b.getAttribute("data-mode") === mode) {
                b.classList.add("active");
            } else {
                b.classList.remove("active");
            }
        });
    } catch (e) {
        // ignore; UI will resync on next poll
    }
}

function setModeClick(buttonEl) {
    const newMode = buttonEl.getAttribute("data-mode");
    if (!newMode) return;
    setMode(newMode);
}

async function updateThreshold() {
    const input = document.getElementById("threshold-input");
    if (!input) return;
    const value = parseInt(input.value, 10);
    if (Number.isNaN(value)) return;
    try {
        await fetch(`/threshold?value=${encodeURIComponent(value)}`, { method: "POST" });
        threshold = value;
        document.getElementById("threshold").textContent = threshold;
    } catch (e) {
        // ignore errors; UI will reflect correct value on next poll
    }
}

function setRate(buttonEl) {
    const ms = parseInt(buttonEl.getAttribute("data-rate"), 10);
    pollMs = ms;
    document.getElementById("rate-label").textContent = ms >= 1000 ? `${ms/1000} s` : `${ms} ms`;
    document.querySelectorAll(".chip").forEach(b => b.classList.remove("active"));
    buttonEl.classList.add("active");
}

async function doCalibrate() {
    const status = document.getElementById("status");
    status.textContent = "Calibrating...";
    status.className = "badge ok";
    await fetch("/calibrate", {method: "POST"});
}

resizeCanvas();
connectWebSocket();
window.addEventListener('resize', () => {
    resizeCanvas();
    renderChart(chartPoints, lastBaseline);
});
</script>

</body>
</html>
    """
