# Linux Timelapse Program Implementation Plan

This implementation plan outlines the creation of a Python-based timelapse program designed to run on a Linux server. It automatically downloads images from an HTTP camera endpoint at a configurable interval, respects daily start/stop times relative to sunrise and sunset, compiles the captured images into an MP4 video at the end of each day, uploads the video to YouTube, and sends push notifications to your phone.

---

## Technical Specifications & Choices

### 1. Dynamic Scheduling based on Sunrise/Sunset
* **Sunset/Sunrise Math (Offline & Dependency-Free)**: To avoid brittle external APIs, we will integrate a mathematical **Sun Model** based on the standard NOAA solar equations directly into a `scheduler.py` module.
* **Configurable Offsets**: The program will allow specifying offsets in minutes relative to sunrise and sunset:
  * E.g., `sunrise_offset_minutes = -30` (start 30 minutes *before* sunrise).
  * E.g., `sunset_offset_minutes = 30` (end 30 minutes *after* sunset).
* **Location settings**: User configures `latitude` and `longitude` in `config.json`, which the algorithm uses to determine exact times down to the minute for their specific location.

### 2. Camera Fetching
* **No Authentication Needed**: The camera endpoint is accessed via a simple GET request.
* We will use Python's built-in `urllib.request` to avoid third-party dependencies for simple downloading.

### 3. Archival & Cleanup Strategy ("Noon Archive")
* To create a year-long timelapse later, we need a consistent set of daily frames.
* At the end of the day, before deleting the raw daily frames, the program will:
  1. Scan all captured frames in the day's folder `output_dir/YYYY-MM-DD/`.
  2. Sort them by timestamp.
  3. Filter for frames captured at or after **12:00:00** (local time).
  4. Select the first **60 frames** from this set (covering 30 minutes at a 30s interval).
  5. Copy these 60 frames to a long-term directory `archive_dir/YYYY-MM-DD/` (or a flat folder with timestamped names).
  6. Compile the full video, verify its creation, and then **delete** the original day's folder `output_dir/YYYY-MM-DD/` to free up disk space.

### 4. Mobile Push Notifications
* We will integrate **[ntfy.sh](https://ntfy.sh)** and **Discord Webhooks**.
* **ntfy.sh** is a free, open-source push notification service. 
  * *How it works*: You install the `ntfy` app on your Android/iOS phone, subscribe to a custom topic name (e.g., `lance-timelapse-alerts`), and the server sends alerts with a simple HTTP POST request. No accounts or APIs required!
* We will send notifications for:
  * **Success**: When the day's timelapse is generated and successfully uploaded to YouTube.
  * **Failure/Offline**: If the camera is unreachable for more than 5 consecutive attempts, we send a push notification immediately warning you that the camera might be offline.

### 5. Automated YouTube Uploads
* We will create a `youtube_uploader.py` module using the official `google-api-python-client`.
* To handle credentials:
  * We will provide a setup mode: `python youtube_uploader.py --setup`
  * This will generate an OAuth authorization URL. The user opens it in a browser, signs in with their YouTube account, and pastes the code back (or it starts a local server to capture it).
  * It saves a persistent `token.json` which allows the script to refresh access tokens and upload videos fully in the background without user intervention.
  * Upload options (title, description, privacy status like `"private"`, `"unlisted"`, or `"public"`) will be configurable in `config.json`.

---

## Proposed Changes

We will create the following files in the project workspace:

### 1. Configuration & Settings

#### [NEW] [config.json](file:///c:/Users/lance/Documents/antigravity/timelapse/config.json)
Contains settings for camera, schedule, notification, and YouTube.
```json
{
  "camera_url": "http://your-camera-ip/image.jpg",
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
    "ntfy_topic": "lance-timelapse-alerts",
    "discord_webhook_url": ""
  },
  "youtube": {
    "enabled": true,
    "privacy_status": "unlisted",
    "title_template": "Daily Timelapse - {date}",
    "description_template": "Automated timelapse captured on {date} from {start_time} to {end_time}."
  }
}
```

### 2. Implementation Modules

#### [NEW] [scheduler.py](file:///c:/Users/lance/Documents/antigravity/timelapse/scheduler.py)
Houses the mathematical `Sun` calculations.
* Computes local sunrise and sunset for a given date, latitude, and longitude.
* Computes active recording start/stop datetimes based on configured offsets.
* Offers `is_active(current_time)` to check whether the program should capture or wait.

#### [NEW] [youtube_uploader.py](file:///c:/Users/lance/Documents/antigravity/timelapse/youtube_uploader.py)
Handles authenticating and uploading compiled MP4 videos to YouTube.
* Includes `--setup` command to perform initial OAuth flow and save `token.json`.
* Provides an `upload_video(file_path, title, description, privacy)` function.

#### [NEW] [compiler.py](file:///c:/Users/lance/Documents/antigravity/timelapse/compiler.py)
Handles:
1. Finding and sorting all images for a given day.
2. Saving the 60 "noon onwards" frames to `archive_dir`.
3. Generating a text file list of images for FFmpeg's concat demuxer.
4. Calling `ffmpeg` via Python `subprocess` to compile the video.
5. Verifying the video file size, then deleting the temporary files and raw daily frames.

#### [NEW] [timelapse.py](file:///c:/Users/lance/Documents/antigravity/timelapse/timelapse.py)
The core driver.
* Runs the infinite loop.
* Monitors time windows.
* Performs camera GET requests and handles connection failures (notifies if offline).
* Triggers compilation and YouTube upload at the end of the capture window.

#### [NEW] [requirements.txt](file:///c:/Users/lance/Documents/antigravity/timelapse/requirements.txt)
Specifies dependencies for YouTube uploads and notifications:
* `google-api-python-client`
* `google-auth-oauthlib`
* `google-auth-httplib2`

#### [NEW] [README.md](file:///c:/Users/lance/Documents/antigravity/timelapse/README.md)
Comprehensive walkthrough on installation, setting up the Google Cloud Project for YouTube upload, setting up the mobile `ntfy` app, and configuring systemd.

---

## Verification Plan

### Automated Tests
1. **Schedule Logic Test**: Verify time calculation edge cases (e.g., afternoon, morning, midnight) and sunrise/sunset offsets.
2. **Archiver Test**: Verify that given a set of test files with datetime names, it correctly selects and copies exactly the first 60 files starting at or after 12:00:00.

### Manual Verification
1. **Setup Run**: Run `python youtube_uploader.py --setup` to generate the credentials.
2. **End-to-End Simulation**: Run with a short 5-second interval, simulated camera endpoint, and a 1-minute capture window, verifying:
   - Capture of files.
   - Extraction of "noon" files (simulating the time filter).
   - Successful rendering of MP4 video.
   - Mobile notification received.
   - YouTube upload initiated.
