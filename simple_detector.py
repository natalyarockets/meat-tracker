"""
Simple RSSI Voice Detector with ElevenLabs
Speaks "Object detected" or "Clear" based on WiFi signal
"""

import subprocess
import time
import requests
import os

# ============================================
# YOUR ELEVENLABS API KEY - PASTE IT HERE
# ============================================
API_KEY = "sk_b1c748d1b35c4e30d1a0eadedeed65e4c490ffd0a4e5ec96"

# Settings
THRESHOLD = 6  # dB drop to trigger detection
CHECK_INTERVAL = 1  # seconds between checks

# ElevenLabs settings
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
API_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"


def speak(text):
    """Generate and play speech using ElevenLabs"""
    print(f"🔊 Speaking: {text}")
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
    
    try:
        response = requests.post(API_URL, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Save and play audio
            with open("/tmp/voice.mp3", "wb") as f:
                f.write(response.content)
            os.system("afplay /tmp/voice.mp3")
        else:
            print(f"API Error: {response.status_code}")
    except Exception as e:
        print(f"Speech error: {e}")


def get_rssi():
    """Read RSSI using wdutil (Mac)"""
    try:
        out = subprocess.check_output(
            ["sudo", "wdutil", "info"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        
        for line in out.splitlines():
            if line.strip().startswith("RSSI"):
                return int(line.split(":")[1].replace("dBm", "").strip())
    except Exception as e:
        print(f"Error reading RSSI: {e}")
    
    return None


def main():
    print("=" * 50)
    print("  RSSI Voice Detector")
    print("=" * 50)
    print()
    
    # Calibration
    print("Step 1: CLEAR THE AREA (no objects between devices)")
    input("Press Enter when ready to calibrate...")
    
    print("Calibrating...")
    baseline = get_rssi()
    
    if baseline is None:
        print("ERROR: Could not read RSSI. Make sure WiFi is connected.")
        print("You may need to run: sudo python3 simple_detector.py")
        return
    
    print(f"✓ Baseline RSSI: {baseline} dBm")
    print(f"✓ Detection threshold: {THRESHOLD} dB drop")
    print()
    
    speak("Calibration complete. Monitoring for objects.")
    
    print("Step 2: MONITORING (Ctrl+C to stop)")
    print("-" * 50)
    
    last_state = "clear"  # Track state to avoid repeating
    
    try:
        while True:
            rssi = get_rssi()
            
            if rssi is None:
                print("? Could not read RSSI")
                time.sleep(CHECK_INTERVAL)
                continue
            
            drop = baseline - rssi
            detected = drop >= THRESHOLD
            
            # Determine current state
            current_state = "detected" if detected else "clear"
            
            # Print status
            status = "🚨 DETECTED" if detected else "✓ Clear"
            print(f"RSSI: {rssi} dBm | Drop: {drop} dB | {status}")
            
            # Only speak when state CHANGES
            if current_state != last_state:
                if detected:
                    speak("Object detected")
                else:
                    speak("Clear")
                last_state = current_state
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nStopped.")
        speak("Detector stopped.")


if __name__ == "__main__":
    main()
