import os
import time
import logging
import google.generativeai as genai

logger = logging.getLogger("timelapse")

GEMINI_KEY_FILE = "gemini_key.txt"

def load_gemini_api_key():
    """
    Load the Gemini API key.
    Checks 'gemini_key.txt' first, then falls back to the environment variable.
    """
    if os.path.exists(GEMINI_KEY_FILE):
        try:
            with open(GEMINI_KEY_FILE, "r", encoding="utf-8") as f:
                key = f.read().strip()
                if key:
                    return key
        except Exception as e:
            logger.error(f"Error reading {GEMINI_KEY_FILE}: {e}")
            
    return os.environ.get("GEMINI_API_KEY")


def analyze_video_weather(video_path):
    """
    Uploads the compiled timelapse video to Google Generative AI File API,
    polls until processed, and uses Gemini to summarize the weather.
    """
    api_key = load_gemini_api_key()
    if not api_key:
        logger.warning(
            "Gemini API key not found in gemini_key.txt or GEMINI_API_KEY environment variable. "
            "Skipping AI weather summary."
        )
        return None

    try:
        logger.info("Configuring Gemini API key...")
        genai.configure(api_key=api_key)

        logger.info(f"Uploading video {video_path} to Gemini API for analysis...")
        video_file = genai.upload_file(path=video_path)
        logger.info(f"Uploaded file name on Gemini API: {video_file.name}")

        # Wait for the file to process (required for video files)
        logger.info("Waiting for video file processing on Gemini...")
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            logger.error(f"Gemini video file processing failed: {video_file.name}")
            return None

        logger.info("Video processing complete. Requesting weather summary...")
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = (
            "Analyze this timelapse video of a farm and write a single, brief sentence "
            "describing the weather progression throughout the day (e.g. 'Cloudy with morning fog, "
            "clearing up to sunny conditions in the afternoon'). Do not include any other commentary."
        )
        
        response = model.generate_content([video_file, prompt])
        summary = response.text.strip()
        
        # Strip potential markdown or wrapping quotes
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1].strip()
            
        logger.info(f"Successfully generated weather summary: '{summary}'")
        
        # Cleanup uploaded file from Gemini storage
        try:
            logger.info(f"Deleting video file {video_file.name} from Gemini API...")
            genai.delete_file(video_file.name)
        except Exception as cleanup_err:
            logger.warning(f"Could not delete Gemini video file {video_file.name}: {cleanup_err}")
            
        return summary

    except Exception as e:
        logger.error(f"Error performing Gemini weather analysis: {e}")
        return None
