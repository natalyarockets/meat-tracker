import subprocess
import time
import threading
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

latest_rssi = None
baseline = None
threshold = 6   # dB drop = HUMAN detected
BASELINE_PATH = Path("baseline.txt")

def read_rssi_wdutil():
    """
    Runs: sudo wdutil info
    Parses RSSI and Noise values.
    Returns (rssi, noise) or (None, None)
    """
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
    """Load baseline RSSI from disk if available."""
    global baseline
    if not BASELINE_PATH.exists():
        return
    try:
        baseline = int(BASELINE_PATH.read_text().strip())
    except Exception as exc:
        print(f"WARNING: failed to load baseline: {exc}")
        baseline = None


def persist_baseline(value: int):
    """Persist baseline RSSI to disk."""
    try:
        BASELINE_PATH.write_text(str(value))
    except Exception as exc:
        print(f"WARNING: failed to persist baseline: {exc}")


def sampler_loop():
    global latest_rssi
    while True:
        try:
            print("DEBUG: calling wdutil...")
            rssi, noise = read_rssi_wdutil()
            print("DEBUG: rssi returned =", rssi)
            print("DEBUG: noise returned =", noise)
            latest_rssi = rssi
        except Exception as exc:
            print(f"ERROR: sampler loop failed: {exc}")
        time.sleep(1)


@app.on_event("startup")
def start_sampler():
    load_baseline()
    thread = threading.Thread(target=sampler_loop, daemon=True)
    thread.start()


@app.post("/calibrate")
def calibrate():
    global baseline
    if latest_rssi is None:
        return {"error": "No RSSI yet"}
    baseline = latest_rssi
    persist_baseline(baseline)
    return {"baseline": baseline}


@app.get("/metrics")
def metrics():
    global latest_rssi, baseline, threshold

    detected = False
    if latest_rssi is not None and baseline is not None:
        detected = (latest_rssi <= baseline - threshold)

    return {
        "rssi": latest_rssi,
        "baseline": baseline,
        "detected": detected
    }


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
</style>
</head>
<body>

<div class="frame">
  <h1>Wi‑Fi Presence <span>Live</span></h1>
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
</div>

<script>
let threshold = 6;
let pollMs = 300;
let pollHandle = null;

async function update() {
    try {
        const res = await fetch("/metrics");
        const data = await res.json();

        document.getElementById("rssi").textContent = data.rssi ?? "?";
        document.getElementById("baseline").textContent =
            data.baseline === null ? "?" : data.baseline;
        document.getElementById("threshold").textContent = threshold;

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
    } catch (e) {
        const status = document.getElementById("status");
        status.textContent = "Connection lost";
        status.className = "badge alert";
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

update();
pollHandle = setInterval(update, pollMs);
</script>

</body>
</html>
    """
