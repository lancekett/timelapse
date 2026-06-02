import os
import sys
import logging
import argparse
import subprocess
import shutil
from datetime import datetime

# Add root path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from timelapse import load_config
from compiler import compile_video

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("archive_compiler")

def compile_mega_timelapse(fps=5, output_filename="mega_timelapse.mp4"):
    """
    Scans the archive directory, takes the first image (midday snapshot) 
    from each day chronologically, and compiles them into a single seasonal timelapse video.
    """
    config = load_config()
    if not config:
        logger.error("Could not load config.json")
        return False
        
    archive_dir = config.get("archive_dir", "./archive")
    video_dir = config.get("video_dir", "./videos")
    
    if not os.path.exists(archive_dir):
        logger.error(f"Archive directory {archive_dir} does not exist. Run the daemon first to collect daily frames.")
        return False
        
    # Get all YYYY-MM-DD directories in archive_dir
    day_dirs = []
    for d in os.listdir(archive_dir):
        full_path = os.path.join(archive_dir, d)
        if os.path.isdir(full_path):
            # Check if directory name matches YYYY-MM-DD pattern
            if len(d) == 10 and d[4] == '-' and d[7] == '-':
                day_dirs.append(d)
                
    day_dirs.sort()
    
    if not day_dirs:
        logger.warning("No daily archive folders found inside your archive directory.")
        return False
        
    logger.info(f"Found {len(day_dirs)} archived daily folders. Building file list...")
    
    # Create a temporary directory to copy all seasonal frames into
    temp_dir = "./temp_mega_images"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        compiled_count = 0
        for i, d in enumerate(day_dirs):
            day_path = os.path.join(archive_dir, d)
            # List JPEGs in this day's archive
            images = [f for f in os.listdir(day_path) if f.lower().endswith((".jpg", ".png"))]
            images.sort()
            
            if images:
                first_image = images[0]
                src_path = os.path.join(day_path, first_image)
                # Rename sequentially to keep alphabetical ordering clean for FFmpeg
                dest_filename = f"frame_{compiled_count:05d}.jpg"
                dest_path = os.path.join(temp_dir, dest_filename)
                
                shutil.copy2(src_path, dest_path)
                compiled_count += 1
                
        if compiled_count == 0:
            logger.warning("No images found in any daily archive folders.")
            return False
            
        os.makedirs(video_dir, exist_ok=True)
        final_video_path = os.path.abspath(os.path.join(video_dir, output_filename))
        
        logger.info(f"Staged {compiled_count} frames. Compiling with FFmpeg at {fps} FPS...")
        success = compile_video(temp_dir, final_video_path, fps=fps)
        
        if success and os.path.exists(final_video_path):
            logger.info(f"SUCCESS! Seasonal mega-timelapse video created: {final_video_path} ({os.path.getsize(final_video_path)} bytes)")
            return True
        else:
            logger.error("FFmpeg compilation failed for mega-timelapse.")
            return False
            
    finally:
        # Tidy up temp folder
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile daily midday snapshot archives into a seasonal mega-timelapse")
    parser.add_argument("--fps", type=int, default=5, help="Playback frame rate (frames per second)")
    parser.add_argument("--output", type=str, default="mega_timelapse.mp4", help="Output filename")
    args = parser.parse_args()
    
    compile_mega_timelapse(fps=args.fps, output_filename=args.output)
