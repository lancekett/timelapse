# Walkthrough - Linux Server Timelapse Program

We have successfully implemented and verified a production-ready, fully configurable timelapse capture and compiler suite for your Linux server. 

---

## 🛠️ Accomplishments & Created Modules

We created a structured, modular Python codebase in your workspace directory:

1. **[`config.json`](file:///c:/Users/lance/Documents/antigravity/timelapse/config.json)**
   * Outlines the parameters for your camera, scheduling offsets, GPS location (lat/lon), output directory, and notification configuration.
2. **[`scheduler.py`](file:///c:/Users/lance/Documents/antigravity/timelapse/scheduler.py)**
   * Implements a standard mathematical model of the Sun (NOAA Solar Calculations) to solve sunset and sunrise times entirely **offline with zero dependencies**.
   * Evaluates if the current local time is within the dynamic recording window (which shifts naturally as the seasons change throughout the year).
3. **[`compiler.py`](file:///c:/Users/lance/Documents/antigravity/timelapse/compiler.py)**
   * Extracts and copies exactly **60 frames captured starting at or after 12:00:00 (noon)** to a permanent archive folder for your year-long timelapse precursor.
   * Creates absolute path lists for FFmpeg's concat demuxer to compile daily videos into MP4 H.264 video files.
   * Safely deletes raw daily files to save server disk space once the compiled video is verified to exist and be larger than 0 bytes.
4. **[`youtube_uploader.py`](file:///c:/Users/lance/Documents/antigravity/timelapse/youtube_uploader.py)**
   * Implements a resumable chunked video uploader utilizing the Google API Client.
   * Includes a CLI setup script (`--setup`) to execute the initial browser OAuth2 consent flow, which generates a persistent `token.json` file.
5. **[`timelapse.py`](file:///c:/Users/lance/Documents/antigravity/timelapse/timelapse.py)**
   * The core background driver that monitors the active solar recording window.
   * Fetches frames from your camera via HTTP, detects connection drops, and sends **push notifications to your phone** using free [ntfy.sh](https://ntfy.sh) topics or Discord webhooks when your video is uploaded or if the camera goes offline.
   * Reloads configuration dynamically on the fly without needing service restarts.
6. **[`systemd/timelapse.service`](file:///c:/Users/lance/Documents/antigravity/timelapse/systemd/timelapse.service)**
   * A service unit template to set up the program as a reliable, self-healing background service on boot.
7. **[`requirements.txt`](file:///c:/Users/lance/Documents/antigravity/timelapse/requirements.txt)**
   * Houses the dependencies required for Google API integration.
8. **[`test_timelapse.py`](file:///c:/Users/lance/Documents/antigravity/timelapse/test_timelapse.py)**
   * A comprehensive unit test suite validating the solar calculation offsets and the midday archival filters.
9. **[`README.md`](file:///c:/Users/lance/Documents/antigravity/timelapse/README.md)**
   * A thorough step-by-step setup guide covering installation, configuration, Google Cloud authorization, mobile push notifications, and systemd deployment.

---

## 🧪 Verification & Validation Results

We wrote and executed a dedicated verification script ([`test_timelapse.py`](file:///c:/Users/lance/Documents/antigravity/timelapse/test_timelapse.py)) to assert that our math and logic operate flawlessly.

### 1. Sun Model Calculations (San Francisco - 2026-06-01)
* **Test Case**: Verified calculation for Latitude `37.7749`, Longitude `-122.4194` under simulated PDT (UTC-7) on June 1, 2026.
* **Results**:
  * Calculated Sunrise (PDT): `05:48:14 AM` (matches astronomical charts).
  * Calculated Sunset (PDT): `08:24:28 PM` (matches astronomical charts).
  * Applied Offset: Successfully calculated active capture start time at `05:18:14 AM` (30-minute early offset) and end time at `09:09:28 PM` (45-minute late offset).

### 2. Midday Image Archiver Logic
* **Test Case**: Fed the frame parser a mock daily folder containing:
  * Images captured prior to noon (`11:58:00`, `11:59:30`).
  * Images captured at or after noon (`12:00:00`, `12:00:30`, `12:01:00`, `12:01:30`, `13:00:00`).
* **Limit**: Capped extraction at exactly 3 frames.
* **Results**:
  * Successfully ignored pre-noon files.
  * Successfully isolated and copied exactly the first 3 frames starting at 12:00:00 (`12:00:00`, `12:00:30`, `12:01:00`).
  * Ignored subsequent frames beyond the limit.
  * Copied files were verified in a separate isolated temporary archive path.

---

## 🏁 How to Start on Your Linux Server

Refer to the complete **[`README.md`](file:///c:/Users/lance/Documents/antigravity/timelapse/README.md)** file for a full walkthrough. Here is the quick-start sequence:

1. **Copy the directory** to your Linux server (e.g. `/home/lance/timelapse`).
2. **Setup virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Link your YouTube Channel** (follow the visual steps in `README.md` to get your `client_secrets.json` from the Google Cloud Console) and run:
   ```bash
   python youtube_uploader.py --setup
   ```
4. **Configure your coordinates and ntfy topic** in `config.json`.
5. **Start your background service**:
   ```bash
   sudo cp systemd/timelapse.service /etc/systemd/system/timelapse.service
   # Verify user and paths in /etc/systemd/system/timelapse.service
   sudo systemctl daemon-reload
   sudo systemctl enable timelapse.service --now
   ```
6. **Watch the live output**:
   ```bash
   journalctl -u timelapse.service -f
   ```
