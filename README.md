# Automated Linux Timelapse Program with Solar Scheduling, YouTube Uploads & Push Notifications

A production-grade Python daemon designed to run on a Linux server. It automatically fetches frames from an HTTP camera at a configurable interval, operates dynamically within a daily window centered around sunrise and sunset, compiles the frames into a daily MP4 video using FFmpeg, uploads it automatically to YouTube, and sends push notifications directly to your phone.

To pave the way for a year-long timelapse, the daemon automatically preserves exactly **60 frames captured starting at 12:00:00 (noon)** daily, while clearing out the rest of the raw frames to save storage space.

---

## 🌟 Key Features

* ☀️ **Solar-Based Scheduling (100% Offline)**: Uses a built-in mathematical model of the Sun (no external API keys or pings needed) to dynamically calculate local sunrise and sunset based on your Latitude and Longitude. Configurable offsets allow starting/stopping recording (e.g. 30 mins before sunrise and 30 mins after sunset) to cover daylight perfectly throughout the year.
* 📦 **Zero Core Runtime Dependencies**: The core capture loop, astronomical scheduler, image archiver, and push notifications utilize standard Python 3 libraries.
* 🎥 **Robust FFmpeg Concat Compilation**: Generates an absolute path list file and feeds it to FFmpeg's concat demuxer, ensuring seamless compilation and avoiding command-line argument limits or filename expansions.
* 📂 **Noon Snapshot Archiving**: Automatically copies the first 60 frames captured at or after 12:00:00 local time to `/archive/YYYY-MM-DD/` and deletes the remaining raw frames once the video compiles successfully.
* 📲 **Push Notifications (ntfy.sh & Discord)**: Sends push notifications to your phone using [ntfy.sh](https://ntfy.sh) (100% free, open-source, no signup/accounts needed) or a Discord webhook. Alerts you when the daily video is compiled, when it uploads to YouTube, or if the camera goes offline.
* 🚀 **Automated Resumable YouTube Uploads**: Integrates with the official YouTube Data API v3 to upload your completed videos in chunks. Includes a CLI setup helper (`--setup`) to execute the initial OAuth browser login.
* ⚙️ **Dynamic Config Reloading**: Automatically reloads `config.json` on-the-fly. You can change intervals, notification topics, or sunset offsets without restarting the daemon.
* 🛡️ **Systemd Integration**: Provided systemd service unit template to run as a reliable, self-healing background daemon on system startup.

---

## 🏗️ Folder Structure

```text
timelapse/
├── config.json               # Main configuration file (intervals, paths, GPS coords)
├── scheduler.py              # Astronomical Sun model & recording window calculations
├── compiler.py               # Frame sorting, midday archiver, and FFmpeg video compiler
├── youtube_uploader.py       # OAuth2 consent flow setup CLI & chunked YouTube uploader
├── timelapse.py              # Main daemon capture loop & notification dispatcher
├── requirements.txt          # Python dependencies (for YouTube upload)
├── systemd/
│   └── timelapse.service     # Systemd service unit template file
└── README.md                 # This documentation
```

---

## ⚙️ Installation & Setup

### 1. System Prerequisites
Ensure your Linux server has **Python 3.7+** and **FFmpeg** installed.

On Debian/Ubuntu:
```bash
sudo apt update
sudo apt install python3 python3-venv ffmpeg -y
```

On Fedora/CentOS/RHEL:
```bash
sudo dnf install python3 ffmpeg -y
```

### 2. Clone and Initialize Environment
Copy the `timelapse` directory to your server (e.g., `/home/your_username/timelapse`), then initialize the virtual environment:

```bash
cd /home/your_username/timelapse
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 📝 Configuration (`config.json`)

Configure your camera, coordinates, offsets, and notifications inside `config.json`:

```json
{
  "camera_url": "http://192.168.1.100/jpg/image.jpg",
  "interval_seconds": 30,
  "latitude": 37.7749,
  "longitude": -122.4194,
  "sunrise_offset_minutes": -30,
  "sunset_offset_minutes": 30,
  "output_dir": "./images",
  "archive_dir": "./archive",
  "video_dir": "./videos",
  "fps": 30,
  "notifications": {
    "provider": "ntfy",
    "ntfy_topic": "your-unique-alerts-topic-name",
    "discord_webhook_url": ""
  },
  "youtube": {
    "enabled": false,
    "privacy_status": "unlisted",
    "title_template": "Daily Timelapse - {date}",
    "description_template": "Automated timelapse captured on {date} from {start_time} to {end_time}."
  }
}
```

### Configuration Fields
* `camera_url`: The HTTP endpoint of your camera that yields a JPEG image on a GET request.
* `interval_seconds`: Seconds between shots (e.g., `30`).
* `latitude` / `longitude`: Your local decimal GPS coordinates (crucial for exact sunset/sunrise calculations).
* `sunrise_offset_minutes`: Offset relative to sunrise. `-30` starts capture 30 minutes *before* sunrise.
* `sunset_offset_minutes`: Offset relative to sunset. `30` stops capture 30 minutes *after* sunset.
* `output_dir`: Path to temporarily store raw daily frames.
* `archive_dir`: Path to permanently save the daily 60 midday frames (for a year-long timelapse).
* `video_dir`: Path where final compiled daily videos are saved.
* `fps`: Frame rate for the compiled video (e.g., 30 FPS means 30 frames equal 1 second of video).

---

## 📲 Setting up Mobile Notifications (`ntfy.sh`)

We highly recommend **ntfy.sh** for effortless phone alerts with no code configuration:
1. Download the **ntfy** app from the Google Play Store or iOS App Store.
2. In the app, tap **Subscribe to topic**.
3. Choose a highly unique topic name (e.g. `lance-secret-timelapse-2983`) to prevent other people from seeing your alerts.
4. Set this topic name under `"ntfy_topic"` in `config.json` and keep `"provider"` as `"ntfy"`.
5. You will now receive instant push notifications with sound directly on your phone when a video is ready or if your camera goes offline!

---

## 🎥 Setting up YouTube Uploads

To automatically upload compiled videos at the end of each day, you must link your YouTube account:

### 1. Create a Google Cloud Project & Get Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., "Home Timelapse").
3. Search for **YouTube Data API v3** in the API library and click **Enable**.
4. Configure the **OAuth Consent Screen**:
   * Choose **External**.
   * Fill out the app name and your developer email.
   * **IMPORTANT**: Under **Test Users**, add your own Google Account email address (the one associated with your YouTube channel).
5. Go to the **Credentials** tab:
   * Click **Create Credentials** -> **OAuth client ID**.
   * Select Application Type: **Desktop App** and name it (e.g. "Timelapse Uploader").
   * Click Create, then download the credential JSON using the download icon.
6. Rename this file to **`client_secrets.json`** and place it in the same directory as the script.

### 2. Run the OAuth Setup CLI
Since your Linux server might be headless, you can authorize it in one of two ways:

#### Option A (Recommended): Setup on your local PC
1. Put `client_secrets.json`, `youtube_uploader.py`, and `requirements.txt` into a folder on your Windows/macOS PC.
2. Install requirements (`pip install -r requirements.txt`).
3. Run:
   ```bash
   python youtube_uploader.py --setup
   ```
4. A local browser window will open. Sign in with your Google account, bypass the "Google hasn't verified this app" warning (click *Advanced* -> *Go to... (unsafe)*), and grant the upload permission.
5. Once successful, a **`token.json`** file will appear in your folder.
6. Copy both `client_secrets.json` and **`token.json`** onto your Linux server in the `/home/your_username/timelapse` folder!

#### Option B: Setup directly on your headless server
1. Activate your virtual environment and run standard setup:
   ```bash
   python youtube_uploader.py --setup
   ```
2. The script will notice it is headless and print a URL:
   ```text
   Open this URL in a browser on any machine: 
   https://accounts.google.com/o/oauth2/auth?...
   ```
3. Open that link in a browser on your local computer, select your Google account, and grant permission.
4. You will be redirected to a page that fails to load (typically `http://localhost:XXXX/?code=...`).
5. Copy the **full redirect URL** from the browser's address bar.
6. Paste that full URL back into the terminal prompt on your server. It will parse the code, authenticate, and write `token.json`!

### 3. Enable in Configuration
Once `token.json` is created and placed in the project directory, open `config.json` and flip `"enabled"` under `"youtube"` to `true`:
```json
  "youtube": {
    "enabled": true,
    ...
  }
```

---

## 🚀 Deploying as a Background Linux Service

To ensure the script starts automatically when your server boots and recovers from errors:

1. Open `/home/your_username/timelapse/systemd/timelapse.service` and replace `your_username` with your actual Linux user account name.
2. Copy the modified service file into systemd's directory:
   ```bash
   sudo cp systemd/timelapse.service /etc/systemd/system/timelapse.service
   ```
3. Reload systemd configurations:
   ```bash
   sudo systemctl daemon-reload
   ```
4. Enable the service to start automatically at boot:
   ```bash
   sudo systemctl enable timelapse.service
   ```
5. Start the service immediately:
   ```bash
   sudo systemctl start timelapse.service
   ```

### 📊 Managing and Monitoring the Service

Check current status:
```bash
sudo systemctl status timelapse.service
```

View real-time logs (very useful for debugging):
```bash
journalctl -u timelapse.service -f
```

Restart the service:
```bash
sudo systemctl restart timelapse.service
```

Stop the service:
```bash
sudo systemctl stop timelapse.service
```

---

## 📁 Storage Archiving Details

The program operates with storage conservation in mind:
* **Temporary Storage**: Raw frames captured every 30s are saved in `./images/YYYY-MM-DD/`.
* **Permanent Midday Snapshots**: Before compilation, the script selects the first **60 frames** beginning at or after **12:00:00 (noon)** and copies them to `./archive/YYYY-MM-DD/`. If you record at a 30s interval, this provides a highly detailed 30-minute block from 12:00 to 12:30.
* **Cleanup**: Once FFmpeg finishes compiling the daily video to `./videos/timelapse_YYYY-MM-DD.mp4` and verifies the file exists and is greater than 0 bytes, the script automatically deletes the entire temporary raw folder `./images/YYYY-MM-DD/` to free up disk space. The `/archive` folder is kept permanently!
