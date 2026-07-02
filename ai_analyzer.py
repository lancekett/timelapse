import os
import time
import logging
from google import genai

logger = logging.getLogger("timelapse")

GEMINI_KEY_FILE = "/config/gemini_key.txt" if os.path.exists("/config") else "gemini_key.txt"

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


def analyze_video_weather(video_path, weather_stats=None):
    """
    Uploads the compiled timelapse video to Google GenAI Files API,
    and uses the new google-genai SDK to summarize the weather.
    Optionally enriches the prompt with ground-truth weather statistics.
    """
    api_key = load_gemini_api_key()
    if not api_key:
        logger.warning(
            "Gemini API key not found in gemini_key.txt or GEMINI_API_KEY environment variable. "
            "Skipping AI weather summary."
        )
        return None

    try:
        logger.info("Configuring Gemini Client with API key...")
        client = genai.Client(api_key=api_key)

        logger.info(f"Uploading video {video_path} to Gemini Files API...")
        video_file = client.files.upload(file=video_path)
        logger.info(f"Uploaded file name: {video_file.name}")

        # Wait for the file to process (required for videos)
        logger.info("Waiting for video file processing on Gemini...")
        current_file = client.files.get(name=video_file.name)
        while current_file.state.name == "PROCESSING":
            time.sleep(2)
            current_file = client.files.get(name=video_file.name)

        if current_file.state.name == "FAILED":
            logger.error(f"Gemini video file processing failed: {current_file.name}")
            return None

        logger.info("Video processing complete. Requesting weather summary...")
        prompt = (
            "Analyze this timelapse video of a farm and write a single, brief sentence "
            "describing the weather progression throughout the day (e.g. 'Cloudy with morning fog, "
            "clearing up to sunny conditions in the afternoon'). Do not include any other commentary."
        )
        
        if weather_stats:
            max_temp = weather_stats.get("max_temp")
            min_temp = weather_stats.get("min_temp")
            precip = weather_stats.get("precipitation")
            t_unit = weather_stats.get("temp_unit", "°F")
            p_unit = weather_stats.get("precip_unit", "in")
            
            rain_str = f"{precip:.2f} {p_unit}" if isinstance(precip, (int, float)) else f"{precip} {p_unit}"
            max_temp_str = f"{max_temp}{t_unit}" if max_temp is not None else "N/A"
            min_temp_str = f"{min_temp}{t_unit}" if min_temp is not None else "N/A"
            
            prompt = (
                "Analyze this timelapse video of a farm and write a weather summary. "
                "You must output a single descriptive sentence about the weather progression (matching visual signs "
                "in the video), followed by a 3-line stats block. Do not include any markdown formatting "
                "or additional commentary.\n\n"
                "Desired Output Format:\n"
                "<Descriptive sentence about weather progression>\n"
                f"High Temperature: {max_temp_str}\n"
                f"Low Temperature: {min_temp_str}\n"
                f"Total Precipitation: {rain_str}\n\n"
                "Ground-truth weather stats to use:\n"
                f"- High: {max_temp_str}\n"
                f"- Low: {min_temp_str}\n"
                f"- Rain: {rain_str}"
            )
            
        logger.debug(f"Gemini Prompt:\n{prompt}")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[current_file, prompt]
        )
        summary = response.text.strip()
        
        # Strip potential markdown or wrapping quotes
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1].strip()
            
        logger.info(f"Successfully generated weather summary: '{summary}'")
        
        # Cleanup uploaded file from Gemini storage
        try:
            logger.info(f"Deleting video file {current_file.name} from Gemini API...")
            client.files.delete(name=current_file.name)
        except Exception as cleanup_err:
            logger.warning(f"Could not delete Gemini video file {current_file.name}: {cleanup_err}")
            
        return summary

    except Exception as e:
        logger.error(f"Error performing Gemini weather analysis: {e}")
        return None
