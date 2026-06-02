import os
import sys
import time
import json
import logging
import shutil
from datetime import datetime

# Add current path to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from timelapse import download_frame, load_config
from compiler import compile_video
import youtube_uploader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("test_compile")

def main():
    config = load_config()
    if not config:
        logger.error("Could not load config.json")
        sys.exit(1)
        
    camera_url = config.get("camera_url")
    output_dir = "./test_images"
    video_dir = "./videos"
    
    # Clean old test files if they exist
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)
    
    print("=" * 60)
    print("            TIMELAPSE E2E COMPILATION TEST")
    print("=" * 60)
    
    # 1. Capture 20 frames at 2-second intervals
    print("\nStep 1: Capturing 20 frames at 2-second intervals...")
    captured_files = []
    for i in range(20):
        # Mock midday filenames to verify structure compatibility
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_20260601_{120000 + i*10}.jpg"
        save_path = os.path.join(output_dir, filename)
        
        logger.info(f"[{i+1}/20] Downloading frame from {camera_url} -> {save_path}...")
        success = download_frame(camera_url, save_path)
        if success:
            captured_files.append(save_path)
        time.sleep(2)
        
    if not captured_files:
        logger.error("No frames downloaded. Please ensure your camera is online.")
        sys.exit(1)
        
    # 2. Compile video
    print("\nStep 2: Compiling video using FFmpeg...")
    video_path = os.path.abspath(os.path.join(video_dir, "test_timelapse.mp4"))
    
    # Compile at 5 FPS so the 20 frames result in a 4-second video
    success = compile_video(output_dir, video_path, fps=5)
    
    if success and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"SUCCESS! Video compiled to: {video_path} ({os.path.getsize(video_path)} bytes)")
        
        # Try to generate a weather summary using Gemini API
        weather_summary = None
        try:
            from ai_analyzer import analyze_video_weather
            weather_summary = analyze_video_weather(video_path)
        except Exception as ai_err:
            logger.error(f"Failed to generate AI weather summary: {ai_err}")

        # 3. Upload to YouTube if enabled
        youtube_cfg = config.get("youtube", {})
        if youtube_cfg.get("enabled", False):
            print("\nStep 3: Uploading test video to YouTube...")
            
            yt_desc = "Automated end-to-end capture and compilation test."
            if weather_summary:
                yt_desc = f"{weather_summary}\n\n{yt_desc}"
                
            try:
                upload_res = youtube_uploader.upload_video(
                    file_path=video_path,
                    title="Timelapse Integration Test",
                    description=yt_desc,
                    privacy_status="unlisted"
                )
                if upload_res:
                    video_id, video_url = upload_res
                    logger.info(f"SUCCESS! Uploaded to YouTube: {video_url}")
                else:
                    logger.error("YouTube upload failed.")
            except Exception as e:
                logger.error(f"Exception during YouTube upload: {e}")
        else:
            print("\nStep 3: YouTube upload skipped (disabled in config).")
            
        # Clean up temporary test_images folder
        print("\nCleaning up temporary test frames...")
        shutil.rmtree(output_dir)
        print("Cleanup complete.")
    else:
        logger.error("Compilation failed.")

if __name__ == "__main__":
    main()
