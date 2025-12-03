import subprocess
import time
import threading
from collections import deque
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
import datetime
import os

last_photo_path = None
last_detected = False

# Optional microphone support (sounddevice + numpy)
try:
    import numpy as np
    import sounddevice as sd

    MIC_AVAILABLE = True
    MIC_ERROR = None
except Exception as exc:
    MIC_AVAILABLE = False
    MIC_ERROR = str(exc)

app = FastAPI()

latest_rssi = None
baseline = None
threshold = 6
history = deque(maxlen=600)
BASELINE_PATH = Path("baseline.txt")

# Microphone levels (dBFS-ish), tracked separately from RSSI
latest_mic_level = None
mic_baseline = None
mic_threshold = 6  # dB increase = HUMAN detected
mic_history = deque(maxlen=600)
MIC_BASELINE_PATH = Path("mic_baseline.txt")

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


def read_mic_level(duration: float = 0.25, samplerate: int = 16000):
    """
    Sample the default microphone and return RMS level in dBFS-ish.
    Returns None if microphone support is unavailable or sampling fails.
    """
    if not MIC_AVAILABLE:
        return None

    try:
        frames = max(1, int(duration * samplerate))
        audio = sd.rec(frames, samplerate=samplerate, channels=1, dtype="float32")
        sd.wait()
        if audio is None:
            return None
        rms = float(np.sqrt(np.mean(np.square(audio))))
        if rms <= 0:
            return -120.0
        return round(20 * np.log10(rms), 1)
    except Exception as exc:
        global MIC_ERROR
        MIC_ERROR = str(exc)
        print(f"WARNING: mic sample failed: {exc}")
        return None


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


def load_mic_baseline():
    """Load baseline microphone level if available."""
    global mic_baseline
    if not MIC_BASELINE_PATH.exists():
        return
    try:
        mic_baseline = float(MIC_BASELINE_PATH.read_text().strip())
    except Exception as exc:
        print(f"WARNING: failed to load mic baseline: {exc}")
        mic_baseline = None


def persist_mic_baseline(value: float):
    """Persist microphone baseline level to disk."""
    try:
        MIC_BASELINE_PATH.write_text(str(value))
    except Exception as exc:
        print(f"WARNING: failed to persist mic baseline: {exc}")


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

def mic_sampler_loop():
    global latest_mic_level, mic_history
    while True:
        if not MIC_AVAILABLE:
            time.sleep(1)
            continue
        try:
            level = read_mic_level()
            latest_mic_level = level
            if level is not None:
                mic_history.append((time.time(), level))
        except Exception as exc:
            print(f"ERROR: mic sampler loop failed: {exc}")
        time.sleep(1)


def warm_camera():
    try:
        os.makedirs("photos", exist_ok=True)
        subprocess.run(["imagesnap", "-w", "1", "photos/warmup.jpg"], check=False)
    except Exception:
        pass
    try:
        os.remove("photos/warmup.jpg")
    except Exception:
        pass


@app.on_event("startup")
def start_sampler():
    load_baseline()
    load_mic_baseline()
    warm_camera()
    thread = threading.Thread(target=sampler_loop, daemon=True)
    thread.start()
    if MIC_AVAILABLE:
        mic_thread = threading.Thread(target=mic_sampler_loop, daemon=True)
        mic_thread.start()
    else:
        print("INFO: microphone sampling disabled - sounddevice/numpy not available")


@app.post("/calibrate")
def calibrate():
    global baseline, mic_baseline
    resp = {}

    if latest_rssi is None:
        resp["error"] = "No RSSI yet"
    else:
        baseline = latest_rssi
        persist_baseline(baseline)
        resp["baseline"] = baseline

    if MIC_AVAILABLE and latest_mic_level is not None:
        mic_baseline = latest_mic_level
        persist_mic_baseline(mic_baseline)
        resp["mic_baseline"] = mic_baseline
    elif MIC_AVAILABLE:
        resp["mic_error"] = "Microphone not ready yet"

    return resp


@app.get("/metrics")
def metrics():
    global latest_rssi, baseline, threshold, latest_mic_level, mic_baseline, mic_threshold

    rssi_detected = False
    mic_detected = False

    if latest_rssi is not None and baseline is not None:
        rssi_detected = bool(latest_rssi <= baseline - threshold)

    if MIC_AVAILABLE and latest_mic_level is not None and mic_baseline is not None:
        mic_detected = bool(latest_mic_level >= mic_baseline + mic_threshold)

    return {
        "rssi": latest_rssi,
        "baseline": baseline,
        "threshold": threshold,
        "rssi_detected": rssi_detected,
        "mic_level": latest_mic_level,
        "mic_baseline": mic_baseline,
        "mic_threshold": mic_threshold,
        "mic_detected": mic_detected,
        "mic_available": MIC_AVAILABLE,
        "mic_error": MIC_ERROR if not MIC_AVAILABLE else None,
        "detected": rssi_detected or mic_detected,
        "history": [
            {"t": int(ts * 1000), "rssi": val}
            for ts, val in history
        ],
        "mic_history": [
            {"t": int(ts * 1000), "level": val}
            for ts, val in mic_history
        ],
        "last_photo": last_photo_path,
        "last_photo": last_photo_path,
    }


@app.get("/photo")
def photo():
    if last_photo_path and os.path.exists(last_photo_path):
        return FileResponse(last_photo_path)
    return {"error": "no photo yet"}


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
.chart-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.chart-head .title { font-weight: 700; font-size: 18px; }
.chart-head .subtle { color: var(--muted); font-size: 14px; }
.chart-legend { display: flex; gap: 12px; flex-wrap: wrap; color: var(--muted); font-size: 14px; }
.chart-legend .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }
.dot.live { background: var(--accent); box-shadow: 0 0 12px rgba(34,211,238,0.7); }
.dot.base { background: var(--accent-2); }
#chartContainer { position: relative; z-index: 1; height: 260px; }
#chart { width: 100%; height: 100%; border-radius: 12px; background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)); border: 1px solid rgba(255,255,255,0.06); }
#photoContainer { position: relative; z-index: 2; margin-top: 30px; }
#photoBox { width: 100%; height: 320px; display: flex; justify-content: center; align-items: center; overflow: hidden; }
#photoBox img { max-height: 100%; max-width: 100%; object-fit: contain; opacity: 0; transition: opacity 0.4s ease; }
#mic-chart { width: 100%; height: 260px; border-radius: 12px; background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)); border: 1px solid rgba(255,255,255,0.06); }
</style>
</head>
<body>

<div class="frame">
  <h1>Wi‑Fi Presence <span>Live</span></h1>
  <div class="sub">Dual-sensor monitoring: Wi‑Fi RSSI drops and microphone spikes compared to calibrated baselines.</div>

  <div id="status" class="badge ok">Waiting for signal...</div>
  <div id="reason" class="muted">Calibrate while the path is empty and the room is quiet.</div>

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
      <div class="label">Wi‑Fi Threshold</div>
      <div class="value"><span id="threshold">6</span> dB</div>
      <div class="muted">Drop relative to baseline</div>
    </div>
    <div class="card">
      <div class="label">Mic Level</div>
      <div class="value"><span id="mic-level">?</span> dBFS</div>
      <div class="muted" id="mic-state">Sampling ambient audio</div>
    </div>
    <div class="card">
      <div class="label">Mic Baseline</div>
      <div class="value"><span id="mic-baseline">?</span> dBFS</div>
      <div class="muted">Spike threshold: <span id="mic-threshold">6</span> dB</div>
    </div>
  </div>

  <div class="actions">
    <button onclick="doCalibrate()">Calibrate (clear path & quiet)</button>
    <div class="toggles">
      <button class="chip active" data-rate="300" onclick="setRate(this)">300 ms</button>
      <button class="chip" data-rate="500" onclick="setRate(this)">500 ms</button>
      <button class="chip" data-rate="1000" onclick="setRate(this)">1 s</button>
      <button class="chip" data-rate="2000" onclick="setRate(this)">2 s</button>
    </div>
    <div class="muted">Refresh rate: <span id="rate-label">300 ms</span> • Detection via Wi‑Fi drop OR mic spike</div>
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

  <div class="chart-card">
    <div class="chart-head">
      <div>
        <div class="title">Mic Level Over Time</div>
        <div class="subtle">Short RMS snapshots from the default microphone</div>
      </div>
      <div class="chart-legend">
        <span><span class="dot live" style="background:#a855f7; box-shadow: 0 0 12px rgba(168,85,247,0.7);"></span>Mic level</span>
        <span><span class="dot base"></span>Baseline</span>
      </div>
    </div>
    <canvas id="mic-chart"></canvas>
  </div>
</div>

<script>
let threshold = 6;
let micThreshold = 6;
let pollMs = 300;
let pollHandle = null;
let chartPoints = [];
let micChartPoints = [];
let lastBaseline = null;
let lastMicBaseline = null;

const wifiCanvas = document.getElementById("chart");
const micCanvas = document.getElementById("mic-chart");
const wifiCtx = wifiCanvas.getContext("2d");
const micCtx = micCanvas.getContext("2d");
const dpr = window.devicePixelRatio || 1;
let wifiSize = {width: 0, height: 0};
let micSize = {width: 0, height: 0};

const wifiPalette = {
    line: '#22d3ee',
    fillTop: 'rgba(34,211,238,0.3)',
    fillBottom: 'rgba(34,211,238,0.02)',
    baseline: '#f59e0b',
};

const micPalette = {
    line: '#a855f7',
    fillTop: 'rgba(168,85,247,0.28)',
    fillBottom: 'rgba(168,85,247,0.02)',
    baseline: '#f59e0b',
};

function ensureCanvasSize(canvas, ctx, size) {
    const rect = canvas.getBoundingClientRect();
    size.width = rect.width;
    size.height = rect.height;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function renderSeries(canvas, ctx, size, points, baseline, valueKey, palette, emptyLabel) {
    if (!canvas) return;
    if (!size.width || !size.height) {
        ensureCanvasSize(canvas, ctx, size);
    }

    ctx.clearRect(0, 0, size.width, size.height);

    if (!points || !points.length) {
        ctx.fillStyle = 'rgba(229,231,235,0.6)';
        ctx.font = '14px Space Grotesk, sans-serif';
        ctx.fillText(emptyLabel, 16, size.height / 2);
        return;
    }

    const xs = points.map(p => p.t);
    const ys = points.map(p => p[valueKey]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys, baseline ?? ys[0]);
    const maxY = Math.max(...ys, baseline ?? ys[0]);
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const margin = 18;

    const x = t => {
        const n = (t - minX) / spanX;
        return margin + n * (size.width - margin * 2);
    };

    const y = v => {
        const n = (v - minY) / spanY;
        return size.height - margin - n * (size.height - margin * 2);
    };

    if (baseline !== null && baseline !== undefined) {
        ctx.save();
        ctx.setLineDash([6, 6]);
        ctx.strokeStyle = palette.baseline;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(x(minX), y(baseline));
        ctx.lineTo(x(maxX), y(baseline));
        ctx.stroke();
        ctx.restore();
    }

    ctx.beginPath();
    ctx.moveTo(x(points[0].t), y(points[0][valueKey]));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(x(points[i].t), y(points[i][valueKey]));
    }
    ctx.lineTo(x(points[points.length - 1].t), size.height - margin);
    ctx.lineTo(x(points[0].t), size.height - margin);
    ctx.closePath();

    const gradient = ctx.createLinearGradient(0, margin, 0, size.height - margin);
    gradient.addColorStop(0, palette.fillTop);
    gradient.addColorStop(1, palette.fillBottom);
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(x(points[0].t), y(points[0][valueKey]));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(x(points[i].t), y(points[i][valueKey]));
    }
    ctx.strokeStyle = palette.line;
    ctx.lineWidth = 2;
    ctx.stroke();

    const lastPoint = points[points.length - 1];
    ctx.fillStyle = palette.line;
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x(lastPoint.t), y(lastPoint[valueKey]), 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
}

async function update() {
    try {
        const res = await fetch("/metrics");
        const data = await res.json();

        threshold = data.threshold ?? threshold;
        micThreshold = data.mic_threshold ?? micThreshold;

        const fmtNum = (val, digits = 1) => {
            if (val === null || val === undefined) return "?";
            return typeof val === "number" ? val.toFixed(digits) : val;
        };

        document.getElementById("rssi").textContent = data.rssi ?? "?";
        document.getElementById("baseline").textContent =
            data.baseline === null ? "?" : data.baseline;
        document.getElementById("threshold").textContent = threshold;
        document.getElementById("mic-level").textContent = fmtNum(data.mic_level);
        document.getElementById("mic-baseline").textContent =
            data.mic_baseline === null || data.mic_baseline === undefined ? "?" : data.mic_baseline.toFixed(1);
        document.getElementById("mic-threshold").textContent = micThreshold;

        const micState = document.getElementById("mic-state");
        if (!data.mic_available) {
            micState.textContent = data.mic_error ? `Mic disabled (${data.mic_error})` : "Mic unavailable";
        } else if (data.mic_level === null || data.mic_level === undefined) {
            micState.textContent = "Waiting for mic samples…";
        } else {
            micState.textContent = "Ambient level vs baseline";
        }

        chartPoints = data.history || [];
        micChartPoints = data.mic_history || [];
        lastBaseline = data.baseline;
        lastMicBaseline = data.mic_baseline;
        renderSeries(wifiCanvas, wifiCtx, wifiSize, chartPoints, lastBaseline, "rssi", wifiPalette, "Waiting for RSSI samples…");
        renderSeries(micCanvas, micCtx, micSize, micChartPoints, lastMicBaseline, "level", micPalette, data.mic_available ? "Waiting for mic samples…" : "Mic unavailable");

        if (data.last_photo) {
            const box = document.getElementById("photoBox");
            let img = box.querySelector("img");
            if (!img) {
                img = document.createElement("img");
                box.appendChild(img);
            }
            img.style.opacity = 0;
            img.onload = () => { img.style.opacity = 1; };
            img.src = "/photo?cache=" + Math.random();
        }

        const status = document.getElementById("status");
        const reason = document.getElementById("reason");
        const reasons = [];
        if (data.rssi_detected) reasons.push("Wi‑Fi drop");
        if (data.mic_detected) reasons.push("Mic spike");

        if (data.detected) {
            status.textContent = "Presence detected";
            status.className = "badge alert";
            reason.textContent = reasons.length ? `Trigger: ${reasons.join(" + ")}` : "Threshold exceeded";
        } else if (data.rssi === null) {
            status.textContent = "Waiting for RSSI...";
            status.className = "badge ok";
            reason.textContent = "Sampler is warming up.";
        } else {
            status.textContent = "Path is clear";
            status.className = "badge ok";
            if (!data.mic_available) {
                reason.textContent = data.mic_error ? `Mic disabled (${data.mic_error})` : "Mic unavailable";
            } else {
                reason.textContent = "Watching Wi‑Fi drops and mic spikes vs baselines.";
            }
        }
    } catch (e) {
        const status = document.getElementById("status");
        status.textContent = "Connection lost";
        status.className = "badge alert";
        document.getElementById("reason").textContent = "The UI cannot reach /metrics right now.";
    }
}

function setRate(buttonEl) {
    const ms = parseInt(buttonEl.getAttribute("data-rate"), 10);
    pollMs = ms;
    document.getElementById("rate-label").textContent = ms >= 1000 ? `${ms/1000} s` : `${ms} ms`;
    document.querySelectorAll(".chip").forEach(b => b.classList.remove("active"));
    buttonEl.classList.add("active");
    if (pollHandle) clearInterval(pollHandle);
    pollHandle = setInterval(update, pollMs);
}

async function doCalibrate() {
    const status = document.getElementById("status");
    status.textContent = "Calibrating...";
    status.className = "badge ok";
    await fetch("/calibrate", {method: "POST"});
    await update();
}

function resizeAll() {
    ensureCanvasSize(wifiCanvas, wifiCtx, wifiSize);
    ensureCanvasSize(micCanvas, micCtx, micSize);
}

resizeAll();
update();
pollHandle = setInterval(update, pollMs);
window.addEventListener('resize', () => {
    resizeAll();
    renderSeries(wifiCanvas, wifiCtx, wifiSize, chartPoints, lastBaseline, "rssi", wifiPalette, "Waiting for RSSI samples…");
    renderSeries(micCanvas, micCtx, micSize, micChartPoints, lastMicBaseline, "level", micPalette, "Waiting for mic samples…");
});
</script>

</body>
</html>
    """
