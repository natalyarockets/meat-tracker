import subprocess
import time
import threading
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

latest_rssi = None
baseline = None
threshold = 6   # dB drop = HUMAN detected

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


def sampler_loop():
    global latest_rssi
    while True:
        print("DEBUG: calling wdutil...")  # NEW

        rssi, noise = read_rssi_wdutil()

        print("DEBUG: rssi returned =", rssi)  # NEW
        print("DEBUG: noise returned =", noise)  # NEW

        latest_rssi = rssi
        time.sleep(1)


@app.on_event("startup")
def start_sampler():
    thread = threading.Thread(target=sampler_loop, daemon=True)
    thread.start()


@app.post("/calibrate")
def calibrate():
    global baseline
    if latest_rssi is None:
        return {"error": "No RSSI yet"}
    baseline = latest_rssi
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
body { font-family: sans-serif; margin: 40px; font-size: 24px; }
#status { font-size: 48px; font-weight: bold; margin-top: 20px; }
.human { color: red; }
.nohuman { color: green; }
button { font-size: 22px; padding: 10px 20px; margin-top: 20px; }
</style>
</head>
<body>

<h1>Wi-Fi Beam Detector</h1>

<div>Signal Strength (RSSI): <span id="rssi">?</span> dBm</div>
<div>Baseline: <span id="baseline">?</span> dBm</div>

<div id="status" class="nohuman">NO HUMAN</div>

<button onclick="doCalibrate()">Calibrate (no human present)</button>

<script>
async function update() {
    const res = await fetch("/metrics");
    const data = await res.json();

    document.getElementById("rssi").textContent = data.rssi;
    document.getElementById("baseline").textContent =
        data.baseline === null ? "?" : data.baseline;

    const status = document.getElementById("status");

    if (data.detected) {
        status.textContent = "HUMAN";
        status.className = "human";
    } else {
        status.textContent = "NO HUMAN";
        status.className = "nohuman";
    }
}

async function doCalibrate() {
    await fetch("/calibrate", {method: "POST"});
}

setInterval(update, 300);  // poll ~3x/sec
</script>

</body>
</html>
    """
