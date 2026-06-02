import os
import shutil
import subprocess
import logging
import re

logger = logging.getLogger("timelapse")


def extract_time_from_filename(filename):
    """
    Extract HHMMSS from a filename in the format 'image_YYYYMMDD_HHMMSS.jpg'
    Returns "HHMMSS" as a string or None if not matching.
    """
    match = re.search(r"image_\d{8}_(\d{6})\.(jpg|png)", filename)
    if match:
        return match.group(1)
    return None


def archive_midday_frames(day_dir, archive_dir, target_date_str, num_frames=60):
    """
    Finds frames taken at or after 12:00:00, copies the first `num_frames` 
    to a permanent archive folder, and returns the list of copied filenames.
    """
    if not os.path.exists(day_dir):
        logger.warning(f"Archive source directory {day_dir} does not exist.")
        return []

    # Get all jpg/png files
    files = [f for f in os.listdir(day_dir) if f.lower().endswith((".jpg", ".png"))]
    files.sort()  # Alphabetical sort aligns with chronological order

    # Filter for files captured starting at or after 12:00:00
    midday_files = []
    for f in files:
        time_str = extract_time_from_filename(f)
        if time_str and time_str >= "120000":
            midday_files.append(f)

    # Take the first N frames
    frames_to_archive = midday_files[:num_frames]
    if not frames_to_archive:
        logger.warning(f"No frames found starting at or after 12:00:00 on {target_date_str} to archive.")
        return []

    # Create daily archive path
    day_archive_dir = os.path.join(archive_dir, target_date_str)
    os.makedirs(day_archive_dir, exist_ok=True)

    copied = []
    for f in frames_to_archive:
        src = os.path.join(day_dir, f)
        dest = os.path.join(day_archive_dir, f)
        try:
            shutil.copy2(src, dest)
            copied.append(f)
        except Exception as e:
            logger.error(f"Failed to archive frame {f}: {e}")

    logger.info(f"Successfully archived {len(copied)} midday frames to {day_archive_dir}")
    return copied


def compile_video(day_dir, video_path, fps=30):
    """
    Compiles all images in day_dir into an MP4 video using FFmpeg.
    Returns True if compilation succeeded, False otherwise.
    """
    if not os.path.exists(day_dir):
        logger.error(f"Cannot compile video: directory {day_dir} does not exist.")
        return False

    files = [f for f in os.listdir(day_dir) if f.lower().endswith((".jpg", ".png"))]
    if not files:
        logger.error(f"No images found in {day_dir} to compile.")
        return False

    files.sort()
    
    # Path for temporary FFmpeg file list
    file_list_path = os.path.join(day_dir, "ffmpeg_file_list.txt")
    
    try:
        # Write absolute paths to file list for FFmpeg concat demuxer
        with open(file_list_path, "w", encoding="utf-8") as f:
            for file_name in files:
                abs_path = os.path.abspath(os.path.join(day_dir, file_name))
                # Concat demuxer expects single quotes and escaped single quotes inside paths
                escaped_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        # Compile command
        # -y: overwrite output
        # -r fps: input frame rate (before input causes ffmpeg to treat images at this fps)
        # -f concat: use concat demuxer
        # -safe 0: allow absolute paths
        # -c:v libx264: h264 encoder
        # -pix_fmt yuv420p: wide compatibility color space
        cmd = [
            "ffmpeg", "-y",
            "-r", str(fps),
            "-f", "concat",
            "-safe", "0",
            "-i", file_list_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            video_path
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        
        # Run process
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            logger.info(f"FFmpeg compilation completed successfully: {video_path}")
            return True
        else:
            logger.error(f"FFmpeg failed with return code {result.returncode}")
            logger.error(f"FFmpeg Stderr:\n{result.stderr}")
            return False
            
    except FileNotFoundError:
        logger.critical("FFmpeg executable not found! Please ensure FFmpeg is installed and added to the system PATH.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during video compilation: {e}")
        return False
    finally:
        # Tidy up the temporary file list
        if os.path.exists(file_list_path):
            try:
                os.remove(file_list_path)
            except Exception as e:
                logger.warning(f"Could not remove temporary file list {file_list_path}: {e}")


def process_end_of_day(day_dir, archive_dir, video_dir, target_date_str, fps=30):
    """
    Coordinates end-of-day actions:
    1. Archives midday frames.
    2. Compiles daily video.
    3. Deletes raw folder if compilation succeeded.
    Returns: (success, video_path, first_archive_frame_path, total_frames)
    """
    logger.info(f"Starting end-of-day processing for {target_date_str}...")
    
    # 0. Count raw frames before deletion
    total_frames = 0
    if os.path.exists(day_dir):
        try:
            total_frames = len([f for f in os.listdir(day_dir) if f.lower().endswith((".jpg", ".png"))])
        except Exception as e:
            logger.error(f"Failed to count raw frames in {day_dir}: {e}")
            
    # 1. Archive midday frames first
    archived_frames = archive_midday_frames(day_dir, archive_dir, target_date_str)
    first_archive_frame_path = None
    if archived_frames:
        first_archive_frame_path = os.path.abspath(os.path.join(archive_dir, target_date_str, archived_frames[0]))
    
    # 2. Compile video
    os.makedirs(video_dir, exist_ok=True)
    video_filename = f"timelapse_{target_date_str}.mp4"
    video_path = os.path.abspath(os.path.join(video_dir, video_filename))
    
    success = compile_video(day_dir, video_path, fps=fps)
    
    if success:
        # Double check file exists and is larger than 0 bytes
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            logger.info(f"Video verified! Size: {os.path.getsize(video_path)} bytes. Cleaning up raw frames...")
            try:
                shutil.rmtree(day_dir)
                logger.info(f"Successfully cleaned up raw directory {day_dir}")
            except Exception as e:
                logger.error(f"Failed to delete raw directory {day_dir}: {e}")
        else:
            logger.error(f"Video file {video_path} is empty or missing! Skipping raw frame cleanup.")
            success = False
    else:
        logger.error(f"Compilation failed for {target_date_str}. Keeping raw frames for troubleshooting.")
        
    return success, video_path, first_archive_frame_path, total_frames
