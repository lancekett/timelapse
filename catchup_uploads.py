import os
import sys
import json
import logging
import re
from datetime import datetime
import youtube_uploader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("catchup")

CONFIG_FILE = "config.json"

def run_catchup():
    # Load config
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            sys.exit(1)
    else:
        logger.error(f"config.json not found in the current working directory.")
        sys.exit(1)
            
    video_dir = config.get("video_dir", "./videos")
    youtube_cfg = config.get("youtube", {})
    
    if not os.path.exists(video_dir):
        logger.error(f"Video directory {video_dir} does not exist.")
        sys.exit(1)
        
    logger.info(f"Scanning {video_dir} for videos that need YouTube uploading...")
    
    mp4_files = [f for f in os.listdir(video_dir) if f.lower().endswith(".mp4")]
    mp4_files.sort()  # Process in chronological order (oldest first)
    
    uploaded_count = 0
    
    for file_name in mp4_files:
        video_path = os.path.join(video_dir, file_name)
        meta_path = os.path.splitext(video_path)[0] + ".json"
        
        # Extract date from name: timelapse_YYYY-MM-DD.mp4
        date_str = "Unknown"
        match = re.search(r"timelapse_(\d{4}-\d{2}-\d{2})\.mp4", file_name)
        if match:
            date_str = match.group(1)
            
        meta_data = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
            except Exception:
                pass
                
        # Check if already uploaded (has both url and id)
        if meta_data.get("youtube_url") and meta_data.get("youtube_id"):
            logger.info(f"Skipping {file_name} (already uploaded: {meta_data['youtube_url']})")
            continue
            
        logger.info(f"Found video needing upload: {file_name}")
        
        # Prepare title and description
        title = youtube_cfg.get("title_template", "Farm time-lapse {date}").format(date=date_str)
        desc_template = youtube_cfg.get("description_template", "Automated timelapse captured on {date}.")
        
        # Set template placeholders
        start_time_str = "morning"
        end_time_str = "evening"
        desc = desc_template.format(
            date=date_str,
            start_time=start_time_str,
            end_time=end_time_str
        )
        
        # Build full description containing weather summary if available
        full_desc = ""
        weather_summary = meta_data.get("weather_summary")
        if weather_summary:
            full_desc += f"{weather_summary}\n\n"
        full_desc += desc
        
        # Check if total_frames / duration is in metadata to append to description
        stats_parts = []
        if meta_data.get("total_frames"):
            stats_parts.append(f"• Total Frames: {meta_data['total_frames']}")
        if meta_data.get("duration"):
            stats_parts.append(f"• Video Length: {meta_data['duration']}")
        if stats_parts:
            full_desc += "\n\n--- 📊 Statistics ---\n" + "\n".join(stats_parts)
            
        privacy = youtube_cfg.get("privacy_status", "public")
        
        logger.info(f"Uploading {file_name} with title: '{title}'...")
        try:
            upload_res = youtube_uploader.upload_video(
                file_path=video_path,
                title=title,
                description=full_desc,
                privacy_status=privacy
            )
            
            if upload_res:
                video_id, video_url = upload_res
                logger.info(f"Successfully uploaded {file_name} -> {video_url}")
                
                # Update/Create JSON metadata
                meta_data["date"] = date_str
                meta_data["youtube_id"] = video_id
                meta_data["youtube_url"] = video_url
                if "created_at" not in meta_data:
                    meta_data["created_at"] = datetime.now().isoformat()
                    
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)
                logger.info(f"Updated metadata file: {meta_path}")
                uploaded_count += 1
            else:
                logger.error(f"Failed to upload {file_name}")
        except Exception as e:
            logger.error(f"Exception occurred while uploading {file_name}: {e}")
            
    logger.info(f"Catch-up run complete. Uploaded {uploaded_count} videos.")

if __name__ == "__main__":
    run_catchup()
