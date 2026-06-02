import os
import sys
import time
import json
import logging
import urllib.request
from datetime import datetime, timezone

# Import our custom modules
from scheduler import TimelapseScheduler
from compiler import process_end_of_day
import youtube_uploader

# Setup root logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("timelapse")


def setup_logging():
    """
    Configure logging to write to both stdout and a log file.
    """
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return
        
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    
    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File Handler
    try:
        fh = logging.FileHandler("timelapse.log", encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        logger.info("Logging configured. Writing to 'timelapse.log'")
    except Exception as e:
        logger.warning(f"Could not configure file logger: {e}")


def load_config():
    """
    Load the config.json file.
    If parsing fails, returns None.
    """
    config_path = "config.json"
    if not os.path.exists(config_path):
        logger.error(f"Configuration file {config_path} not found!")
        return None
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse config.json! Please check syntax: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading config.json: {e}")
        return None


def update_status_file(status_dict):
    """
    Write current daemon state to a status.json file for the dashboard.
    """
    try:
        with open("status.json", "w", encoding="utf-8") as f:
            json.dump(status_dict, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write status.json: {e}")


def send_notification(config, message, title=None, tags=None, attachment_path=None):
    """
    Send push notification using the configured provider (ntfy or Discord).
    Optionally attaches a local file.
    """
    notif_cfg = config.get("notifications", {})
    provider = notif_cfg.get("provider", "ntfy").lower()
    
    if provider == "ntfy":
        topic = notif_cfg.get("ntfy_topic", "")
        if not topic:
            logger.warning("ntfy provider selected but ntfy_topic is empty.")
            return False
            
        url = f"https://ntfy.sh/{topic}"
        
        # If we have a local attachment path, we upload it as the payload body
        if attachment_path and os.path.exists(attachment_path):
            try:
                with open(attachment_path, "rb") as f:
                    image_bytes = f.read()
                
                req = urllib.request.Request(url, data=image_bytes)
                req.add_header("X-Filename", os.path.basename(attachment_path))
                
                # In ntfy, when sending attachment via POST body, title/message/tags
                # should be sent as headers
                if title:
                    req.add_header("X-Title", title.encode("utf-8"))
                if message:
                    req.add_header("X-Message", message.encode("utf-8"))
                if tags:
                    req.add_header("X-Tags", tags.encode("utf-8"))
            except Exception as e:
                logger.error(f"Failed to prepare ntfy attachment: {e}")
                # Fall back to standard request
                req = urllib.request.Request(url, data=message.encode("utf-8"))
                if title:
                    req.add_header("Title", title.encode("utf-8"))
                if tags:
                    req.add_header("Tags", tags.encode("utf-8"))
        else:
            req = urllib.request.Request(url, data=message.encode("utf-8"))
            if title:
                req.add_header("Title", title.encode("utf-8"))
            if tags:
                req.add_header("Tags", tags.encode("utf-8"))
            
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Failed to send ntfy notification to topic '{topic}': {e}")
            return False
            
    elif provider == "discord":
        webhook_url = notif_cfg.get("discord_webhook_url", "")
        if not webhook_url:
            logger.warning("Discord provider selected but discord_webhook_url is empty.")
            return False
            
        payload = {
            "content": f"**{title}**\n{message}" if title else message
        }
        
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status in [200, 204]
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
            
    else:
        logger.warning(f"Unknown notification provider: {provider}")
        return False


def download_frame(camera_url, save_path):
    """
    Downloads an image from camera_url and saves it to save_path.
    Returns True if successful, False otherwise.
    """
    req = urllib.request.Request(camera_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                with open(save_path, "wb") as f:
                    f.write(response.read())
                return True
            else:
                logger.error(f"Camera returned HTTP code {response.status}")
                return False
    except Exception as e:
        logger.error(f"Failed to download frame from camera: {e}")
        return False


def main():
    setup_logging()
    logger.info("=" * 60)
    logger.info("                 STARTING TIMELAPSE DAEMON")
    logger.info("=" * 60)
    
    # Load initial configuration
    config = load_config()
    if not config:
        logger.critical("Cannot start daemon without valid configuration. Exiting.")
        sys.exit(1)
        
    # State tracking
    compilation_done_for_date = None
    camera_is_offline = False
    consecutive_failures = 0
    failure_threshold = 5  # Alert after 5 consecutive failed downloads (approx. 2.5 mins at 30s intervals)
    
    logger.info("Timelapse daemon is running. Enter Ctrl+C to terminate.")
    
    try:
        while True:
            # Reload configuration dynamically at the beginning of each loop
            new_config = load_config()
            if new_config:
                config = new_config
            else:
                logger.warning("Using last known good configuration.")

            # Extract configuration variables
            camera_url = config.get("camera_url")
            interval_seconds = config.get("interval_seconds", 30)
            lat = config.get("latitude")
            lon = config.get("longitude")
            sunrise_offset = config.get("sunrise_offset_minutes", -30)
            sunset_offset = config.get("sunset_offset_minutes", 30)
            output_dir = config.get("output_dir", "./images")
            archive_dir = config.get("archive_dir", "./archive")
            video_dir = config.get("video_dir", "./videos")
            fps = config.get("fps", 30)
            
            # Setup scheduler
            scheduler = TimelapseScheduler(
                lat=lat,
                lon=lon,
                sunrise_offset_mins=sunrise_offset,
                sunset_offset_mins=sunset_offset
            )
            
            # Check schedule
            now = datetime.now().astimezone()
            today_str = now.strftime("%Y-%m-%d")
            active, start_dt, end_dt = scheduler.is_active(now)
            
            # Write daemon status for dashboard
            update_status_file({
                "pid": os.getpid(),
                "last_check": now.strftime("%Y-%m-%d %H:%M:%S"),
                "active_window": active,
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "camera_is_offline": camera_is_offline,
                "consecutive_failures": consecutive_failures,
                "compilation_done_for_date": compilation_done_for_date
            })
            
            if active:
                # We are in the capture window!
                # 1. Create daily folder
                day_dir = os.path.join(output_dir, today_str)
                os.makedirs(day_dir, exist_ok=True)
                
                # 2. Capture frame
                timestamp_str = now.strftime("%Y%m%d_%H%M%S")
                filename = f"image_{timestamp_str}.jpg"
                save_path = os.path.join(day_dir, filename)
                
                logger.debug(f"Attempting to capture frame at {now.strftime('%H:%M:%S')}...")
                success = download_frame(camera_url, save_path)
                
                if success:
                    consecutive_failures = 0
                    if camera_is_offline:
                        # Camera came back online!
                        camera_is_offline = False
                        logger.info("Camera is back online.")
                        send_notification(
                            config,
                            message=f"The camera is back online at {now.strftime('%H:%M:%S')}.",
                            title="Camera Online",
                            tags="green_circle,camera"
                        )
                else:
                    consecutive_failures += 1
                    logger.warning(f"Download failure {consecutive_failures}/{failure_threshold}")
                    
                    if consecutive_failures >= failure_threshold and not camera_is_offline:
                        # Transition to offline
                        camera_is_offline = True
                        logger.error("Camera detected offline! Sending alert...")
                        send_notification(
                            config,
                            message=f"Alert: Camera at {camera_url} has failed {consecutive_failures} consecutive connection attempts.",
                            title="Camera Offline 🚨",
                            tags="red_circle,warning"
                        )
                
                # Sleep for configured interval (minus computation time)
                elapsed = (datetime.now().astimezone() - now).total_seconds()
                sleep_time = max(0.1, interval_seconds - elapsed)
                time.sleep(sleep_time)
                
            else:
                # Outside capture window (Night/Inactive)
                logger.debug("Outside active recording window.")
                
                # Check if we need to compile the video for today
                # This runs if we are past today's end time, and haven't compiled today's video yet.
                if now > end_dt and compilation_done_for_date != today_str:
                    day_dir = os.path.join(output_dir, today_str)
                    
                    if os.path.exists(day_dir) and len(os.listdir(day_dir)) > 0:
                        logger.info(f"Capture window ended. Starting compilation for {today_str}...")
                        
                        # Trigger compilation & archival
                        comp_success, video_path, first_archive_frame_path, total_frames = process_end_of_day(
                            day_dir=day_dir,
                            archive_dir=archive_dir,
                            video_dir=video_dir,
                            target_date_str=today_str,
                            fps=fps
                        )
                        
                        if comp_success:
                            compilation_done_for_date = today_str
                            
                            # Generate AI weather summary
                            weather_summary = None
                            try:
                                from ai_analyzer import analyze_video_weather
                                weather_summary = analyze_video_weather(video_path)
                            except Exception as ai_err:
                                logger.error(f"Failed to generate AI weather summary: {ai_err}")
                                
                            youtube_cfg = config.get("youtube", {})
                            
                            # Standard notification fields
                            notif_title = "Timelapse Completed 🎥"
                            notif_msg = f"Your daily timelapse for {today_str} has been successfully rendered."
                            if weather_summary:
                                notif_msg += f"\n\nWeather: {weather_summary}"
                            
                            # Compile Rich stats
                            start_time_str = start_dt.strftime("%I:%M %p")
                            end_time_str = end_dt.strftime("%I:%M %p")
                            duration_seconds = int(total_frames / fps) if fps > 0 else 0
                            duration_str = f"{duration_seconds // 60}m {duration_seconds % 60}s" if duration_seconds >= 60 else f"{duration_seconds}s"
                            
                            stats_block = (
                                f"\n\n--- 📊 Capture Statistics ---\n"
                                f"• Date: {today_str}\n"
                                f"• Capture Window: {start_time_str} to {end_time_str}\n"
                                f"• Capture Interval: {interval_seconds}s\n"
                                f"• Total Frames: {total_frames}\n"
                                f"• Playback Speed: {fps} FPS\n"
                                f"• Video Length: {duration_str}"
                            )
                            
                            # Add stats to notification message
                            notif_msg += stats_block
                            
                            # YouTube Upload
                            if youtube_cfg.get("enabled", False):
                                logger.info("YouTube upload is enabled. Starting upload...")
                                
                                yt_title = youtube_cfg.get("title_template", "Timelapse {date}").format(date=today_str)
                                yt_desc = youtube_cfg.get("description_template", "Timelapse").format(
                                    date=today_str,
                                    start_time=start_time_str,
                                    end_time=end_time_str
                                )
                                
                                # Format rich description for YouTube
                                full_yt_desc = ""
                                if weather_summary:
                                    full_yt_desc += f"{weather_summary}\n\n"
                                full_yt_desc += f"{yt_desc}\n"
                                full_yt_desc += stats_block
                                
                                privacy = youtube_cfg.get("privacy_status", "unlisted")
                                
                                try:
                                    upload_res = youtube_uploader.upload_video(
                                        file_path=video_path,
                                        title=yt_title,
                                        description=full_yt_desc,
                                        privacy_status=privacy
                                    )
                                    
                                    if upload_res:
                                        video_id, video_url = upload_res
                                        notif_msg += f"\n\n🔗 Watch on YouTube: {video_url}"
                                    else:
                                        notif_msg += "\n\n⚠️ Failed to upload to YouTube. Video saved on server."
                                except Exception as e:
                                    logger.error(f"YouTube upload error: {e}")
                                    notif_msg += f"\n\n⚠️ Error uploading to YouTube: {e}. Video saved on server."
                            else:
                                notif_msg += f"\n\n💾 YouTube upload disabled. Video saved locally at: {video_path}"
                                
                            # Send final push notification with embedded first archived frame image
                            send_notification(
                                config,
                                message=notif_msg,
                                title=notif_title,
                                tags="clapper,video_camera",
                                attachment_path=first_archive_frame_path
                            )
                        else:
                            # Compilation failed
                            logger.error(f"Failed to process end-of-day for {today_str}.")
                            send_notification(
                                config,
                                message=f"Failed to compile daily timelapse video for {today_str}. Please check server logs.",
                                title="Timelapse Failed ❌",
                                tags="x,warning"
                            )
                            # Mark compiled to avoid infinite retry loops on failure
                            compilation_done_for_date = today_str
                    else:
                        # No frames captured today (e.g. server was off or camera was offline all day)
                        logger.debug("No frames to compile for today.")
                        compilation_done_for_date = today_str
                
                # Sleep in 60s increments during inactive periods to conserve resources
                # and allow the script to respond to config updates or timezone changes
                time.sleep(60)
                
    except KeyboardInterrupt:
        logger.info("Daemon termination requested by user. Shutting down gracefully...")
    except Exception as e:
        logger.critical(f"Fatal exception in timelapse daemon: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
