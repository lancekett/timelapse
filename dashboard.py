import os
import sys
import json
import logging
import urllib.request
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingTCPServer

# Setup logger for dashboard
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (dashboard) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dashboard")

PORT = 8000
CONFIG_FILE = "config.json"
STATUS_FILE = "status.json"
LOG_FILE = "timelapse.log"


def get_disk_space():
    """Returns free, total, used disk space in GB for the storage partition."""
    path = "/data" if os.path.exists("/data") else "."
    try:
        total, used, free = shutil.disk_usage(path)
        return {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "percent_used": round((used / total) * 100, 1)
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent_used": 0}


def is_process_running(pid):
    """Checks if a process with a given PID is currently active."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def check_camera_online(url):
    """Sends a quick lightweight check to the camera to see if it responds."""
    if not url:
        return False
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def load_logs():
    """Reads the last 100 lines of timelapse.log."""
    if not os.path.exists(LOG_FILE):
        return "Log file not found."
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            return "".join(lines[-100:])
    except Exception as e:
        return f"Error reading logs: {e}"


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Prevent default stdout logs cluttering the terminal for API polling
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self.serve_index()
        elif path == "/api/status":
            self.serve_status()
        elif path == "/api/logs":
            self.serve_text(load_logs())
        elif path == "/api/preview":
            self.serve_preview()
        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/config":
            self.save_config()
        else:
            self.send_error(404, "Endpoint Not Found")

    def serve_index(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        
        # Dashboard UI
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Timelapse Server Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0b0f19;
            --bg-surface: rgba(17, 24, 39, 0.7);
            --bg-card: rgba(31, 41, 55, 0.4);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-glow: rgba(139, 92, 246, 0.15);
            
            --color-primary: #8b5cf6; /* violet */
            --color-success: #10b981; /* emerald */
            --color-danger: #ef4444;  /* red */
            --color-warning: #f59e0b; /* amber */
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
        }
        
        body {
            background-color: var(--bg-base);
            background-image: radial-gradient(circle at top right, rgba(139, 92, 246, 0.08), transparent 400px),
                              radial-gradient(circle at bottom left, rgba(16, 185, 129, 0.05), transparent 400px);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
            display: flex;
            justify-content: center;
        }
        
        .container {
            width: 100%;
            max-width: 1200px;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }
        
        .logo-section h1 {
            font-size: 1.75rem;
            font-weight: 700;
            background: linear-gradient(135deg, #a78bfa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }
        
        .logo-section p {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }
        
        .system-badges {
            display: flex;
            gap: 1rem;
        }
        
        .badge {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .badge-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .bg-success { background-color: var(--color-success); box-shadow: 0 0 8px var(--color-success); }
        .bg-danger { background-color: var(--color-danger); box-shadow: 0 0 8px var(--color-danger); }
        
        /* Grid Layout */
        .grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
        }
        
        @media (max-width: 900px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
        
        .left-col, .right-col {
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }
        
        .card {
            background: var(--bg-surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover {
            box-shadow: 0 4px 30px var(--accent-glow);
        }
        
        .card-title {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            border-left: 3px solid var(--color-primary);
            padding-left: 0.75rem;
            color: #ffffff;
        }
        
        /* Camera Preview Frame */
        .preview-container {
            width: 100%;
            aspect-ratio: 16/9;
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
            border: 1px solid var(--border-color);
        }
        
        .preview-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .preview-overlay {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(transparent, rgba(0,0,0,0.8));
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            font-size: 0.875rem;
            color: #fff;
        }
        
        /* Stats Widget */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
        }
        
        .stat-box {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1rem;
            text-align: center;
        }
        
        .stat-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
        }
        
        /* Log terminal */
        .terminal {
            background: #05070f;
            border-radius: 10px;
            padding: 1rem;
            font-family: monospace;
            font-size: 0.825rem;
            height: 250px;
            overflow-y: auto;
            white-space: pre-wrap;
            color: #34d399; /* emerald-400 */
            border: 1px solid var(--border-color);
        }
        
        /* Form controls */
        .form-group {
            margin-bottom: 1rem;
        }
        
        .form-group label {
            display: block;
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }
        
        .form-group input, .form-group select {
            width: 100%;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.75rem;
            border-radius: 8px;
            font-size: 0.875rem;
            outline: none;
            transition: border-color 0.2s;
        }
        
        .form-group input:focus, .form-group select:focus {
            border-color: var(--color-primary);
        }
        
        .btn {
            background: linear-gradient(135deg, var(--color-primary), #6d28d9);
            color: #fff;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: opacity 0.2s;
        }
        
        .btn:hover {
            opacity: 0.9;
        }
        
        .btn-secondary {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            margin-top: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section">
                <h1>Timelapse Control Center</h1>
                <p>Solar Scheduling & Video Pipeline Monitor</p>
            </div>
            <div class="system-badges">
                <div class="badge">
                    <span id="daemon-badge-dot" class="badge-dot bg-danger"></span>
                    Daemon: <span id="daemon-status-text">Checking...</span>
                </div>
                <div class="badge">
                    <span id="camera-badge-dot" class="badge-dot bg-danger"></span>
                    Camera: <span id="camera-status-text">Checking...</span>
                </div>
            </div>
        </header>
        
        <div class="grid">
            <div class="left-col">
                <div class="card">
                    <div class="card-title">Live Camera View</div>
                    <div class="preview-container">
                        <img id="camera-preview" src="/api/preview" alt="Camera Feed Preview" class="preview-img">
                        <div class="preview-overlay">
                            <span id="preview-timestamp">Updated just now</span>
                            <span>Live Fetch</span>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Active Loop Status</div>
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-label">Capture State</div>
                            <div id="stat-capture-state" class="stat-value" style="color: var(--color-warning);">Idle</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Today's Start</div>
                            <div id="stat-sunrise" class="stat-value">--:--</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Today's End</div>
                            <div id="stat-sunset" class="stat-value">--:--</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Disk Storage</div>
                            <div id="stat-storage" class="stat-value">-- GB free</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Daemon Logs</div>
                    <div id="log-terminal" class="terminal">Loading logs...</div>
                    <button class="btn btn-secondary" onclick="fetchLogs()" style="margin-top: 1rem; width: auto;">Refresh Logs</button>
                </div>
            </div>
            
            <div class="right-col">
                <div class="card">
                    <div class="card-title">Configuration Settings</div>
                    <form id="config-form" onsubmit="saveConfig(event)">
                        <div class="form-group">
                            <label for="camera_url">Camera HTTP URL</label>
                            <input type="text" id="camera_url" required>
                        </div>
                        <div class="form-group">
                            <label for="interval_seconds">Interval (Seconds)</label>
                            <input type="number" id="interval_seconds" required min="1">
                        </div>
                        <div class="form-group">
                            <label for="latitude">Latitude (GPS)</label>
                            <input type="number" step="any" id="latitude" required>
                        </div>
                        <div class="form-group">
                            <label for="longitude">Longitude (GPS)</label>
                            <input type="number" step="any" id="longitude" required>
                        </div>
                        <div class="form-group">
                            <label for="sunrise_offset_minutes">Sunrise Offset (Mins)</label>
                            <input type="number" id="sunrise_offset_minutes" required>
                        </div>
                        <div class="form-group">
                            <label for="sunset_offset_minutes">Sunset Offset (Mins)</label>
                            <input type="number" id="sunset_offset_minutes" required>
                        </div>
                        <div class="form-group">
                            <label for="fps">Timelapse Video FPS</label>
                            <input type="number" id="fps" required min="1">
                        </div>
                        <button type="submit" class="btn">Apply Changes</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function updateBadge(dotId, textId, active, labelActive, labelInactive) {
            const dot = document.getElementById(dotId);
            const txt = document.getElementById(textId);
            if (active) {
                dot.className = "badge-dot bg-success";
                txt.textContent = labelActive;
                txt.style.color = "var(--color-success)";
            } else {
                dot.className = "badge-dot bg-danger";
                txt.textContent = labelInactive;
                txt.style.color = "var(--color-danger)";
            }
        }

        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update Badges
                updateBadge("daemon-badge-dot", "daemon-status-text", data.daemon_running, "Running", "Offline");
                updateBadge("camera-badge-dot", "camera-status-text", data.camera_online, "Online", "Offline");
                
                // Update stats
                const captureState = document.getElementById("stat-capture-state");
                if (data.status_details && data.status_details.active_window) {
                    captureState.textContent = "Capturing";
                    captureState.style.color = "var(--color-success)";
                } else {
                    captureState.textContent = "Sleeping";
                    captureState.style.color = "var(--color-warning)";
                }
                
                if (data.status_details) {
                    const startStr = data.status_details.start_time ? data.status_details.start_time.split(" ")[1] : "--:--";
                    const endStr = data.status_details.end_time ? data.status_details.end_time.split(" ")[1] : "--:--";
                    document.getElementById("stat-sunrise").textContent = startStr;
                    document.getElementById("stat-sunset").textContent = endStr;
                }
                
                if (data.disk_space) {
                    document.getElementById("stat-storage").textContent = data.disk_space.free_gb + " GB";
                }
                
                // Pop form values if not focused
                if (data.config && document.activeElement.tagName !== "INPUT") {
                    document.getElementById("camera_url").value = data.config.camera_url || "";
                    document.getElementById("interval_seconds").value = data.config.interval_seconds || 30;
                    document.getElementById("latitude").value = data.config.latitude || "";
                    document.getElementById("longitude").value = data.config.longitude || "";
                    document.getElementById("sunrise_offset_minutes").value = data.config.sunrise_offset_minutes || 0;
                    document.getElementById("sunset_offset_minutes").value = data.config.sunset_offset_minutes || 0;
                    document.getElementById("fps").value = data.config.fps || 30;
                }
            } catch (err) {
                console.error("Error fetching status:", err);
            }
        }

        async function fetchLogs() {
            try {
                const response = await fetch('/api/logs');
                const logText = await response.text();
                const term = document.getElementById("log-terminal");
                term.textContent = logText;
                term.scrollTop = term.scrollHeight; // Auto scroll to bottom
            } catch (err) {
                console.error("Error loading logs:", err);
            }
        }

        async function saveConfig(event) {
            event.preventDefault();
            const updated = {
                camera_url: document.getElementById("camera_url").value,
                interval_seconds: parseInt(document.getElementById("interval_seconds").value),
                latitude: parseFloat(document.getElementById("latitude").value),
                longitude: parseFloat(document.getElementById("longitude").value),
                sunrise_offset_minutes: parseInt(document.getElementById("sunrise_offset_minutes").value),
                sunset_offset_minutes: parseInt(document.getElementById("sunset_offset_minutes").value),
                fps: parseInt(document.getElementById("fps").value)
            };
            
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updated)
                });
                
                if (response.ok) {
                    alert("Configuration saved successfully!");
                    fetchStatus();
                } else {
                    alert("Error saving config.");
                }
            } catch (err) {
                console.error("Error saving config:", err);
            }
        }

        function refreshPreview() {
            const img = document.getElementById("camera-preview");
            // Add a cache-busting timestamp query to bypass browser cache
            img.src = "/api/preview?t=" + new Date().getTime();
            document.getElementById("preview-timestamp").textContent = "Updated " + new Date().toLocaleTimeString();
        }

        // Loop runs
        fetchStatus();
        fetchLogs();
        
        setInterval(fetchStatus, 3000);   // Poll status every 3s
        setInterval(fetchLogs, 10000);    // Poll logs every 10s
        setInterval(refreshPreview, 7000); // Reload camera image preview every 7s
    </script>
</body>
</html>
"""
        self.wfile.write(html.encode("utf-8"))

    def serve_status(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        
        # Load config
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
            except Exception:
                pass
                
        # Load status
        status_details = {}
        daemon_running = False
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r") as f:
                    status_details = json.load(f)
                    pid = status_details.get("pid", 0)
                    daemon_running = is_process_running(pid)
            except Exception:
                pass
                
        # Check camera status
        camera_online = check_camera_online(config.get("camera_url"))
        
        # Compile payload
        payload = {
            "daemon_running": daemon_running,
            "camera_online": camera_online,
            "disk_space": get_disk_space(),
            "status_details": status_details,
            "config": config
        }
        
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def serve_text(self, text):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def serve_preview(self):
        # Fetch current frame from camera and proxy it to the browser
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
            except Exception:
                pass
                
        camera_url = config.get("camera_url")
        if not camera_url:
            self.send_error(400, "Camera URL not configured.")
            return
            
        try:
            req = urllib.request.Request(camera_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                    self.end_headers()
                    self.wfile.write(response.read())
                else:
                    self.send_error(502, "Camera returned non-200 code.")
        except Exception as e:
            self.send_error(502, f"Failed to retrieve frame from camera: {e}")

    def save_config(self):
        # Read payload
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            new_config = json.loads(post_data.decode("utf-8"))
            
            # Read existing config to preserve keys like notifications/youtube/archive paths
            existing_config = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    existing_config = json.load(f)
            
            # Update values
            for k, v in new_config.items():
                existing_config[k] = v
                
            # Write back
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing_config, f, indent=2)
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            logger.info("Configuration updated successfully via Web Dashboard.")
            
        except Exception as e:
            self.send_error(500, f"Error saving configuration: {e}")


def run_server():
    # Threading server allows concurrent requests (e.g. streaming log text while previewing image)
    server_address = ('', PORT)
    httpd = ThreadingTCPServer(server_address, DashboardHandler)
    logger.info(f"Dashboard Web Interface started successfully!")
    logger.info(f"Access it locally at: http://localhost:{PORT}")
    logger.info(f"Access it on your local network at: http://<your_server_ip>:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Dashboard server...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
