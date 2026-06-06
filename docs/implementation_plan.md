# Weather Stats Integration Implementation Plan

This plan outlines the integration of daily weather statistics (maximum temperature, minimum temperature, and total daily precipitation) from the free, API-key-free **Open-Meteo API** into the daily timelapse compiler pipeline. The stats will be:
1. Compiled into the terminal and push notification stats blocks.
2. Injected into the Gemini AI video analysis prompt to provide ground-truth meteorological numbers, resulting in a more accurate daily description.
3. Automatically appended to the YouTube description metadata.

---

## User Review Required

> [!NOTE]
> **API Dependency**: We will use the public Open-Meteo API (`api.open-meteo.com`). It is free, requires no API key, and is highly reliable.
>
> **Units**: Since your location is in Washington, USA (`46.52811, -123.01069`), we will default to Imperial units (Fahrenheit for temperature, inches for precipitation). We can make this configurable in `config.json` (e.g., metric vs imperial) for future-proofing.

---

## Open Questions

> [!NOTE]
> 1. **Configurable Units**: Should we add a `"units": "imperial"` or `"units": "metric"` field to `config.json`, or are you happy with us hardcoding imperial/metric based on standard US conventions?
> 2. **Precipitation formatting**: If there is no rain (0.00 inches), would you like the notification to say "Rain: None" or show "Rain: 0.0 in"?

---

## Proposed Changes

We will introduce a new helper module and modify the main driver and AI analyzer:

### 1. New Weather Fetcher Module

#### [NEW] [weather.py](file:///c:/Users/lance/Documents/antigravity/timelapse/weather.py)
* Contains `fetch_daily_weather(lat, lon, date_str, temp_unit="fahrenheit", precip_unit="inch")`.
* Makes a standard HTTP GET request using python's built-in `urllib.request` to `api.open-meteo.com/v1/forecast`.
* Extracts the daily maximum temperature, minimum temperature, and sum of precipitation for the specified date.
* Returns a dictionary: `{"max_temp": float, "min_temp": float, "precipitation": float, "temp_unit": str, "precip_unit": str}`.

---

### 2. Main Daemon Loop Integration

#### [MODIFY] [timelapse.py](file:///c:/Users/lance/Documents/antigravity/timelapse/timelapse.py)
* At the end of the day, before initiating the video compiler, call `weather.fetch_daily_weather(lat, lon, today_str, ...)` to grab the day's stats.
* Pass the weather dictionary to the `analyze_video_weather(video_path, weather_stats)` function.
* Include the weather statistics in the local notifications (Discord / ntfy) under the capture statistics block.
* Include the weather statistics in the YouTube description template.

---

### 3. AI Analysis Prompt Enhancement

#### [MODIFY] [ai_analyzer.py](file:///c:/Users/lance/Documents/antigravity/timelapse/ai_analyzer.py)
* Update `analyze_video_weather(video_path, weather_stats=None)` to accept the weather stats dictionary.
* If weather stats are available, inject them directly into the Gemini prompt:
  * *Example Prompt*:
    ```text
    Analyze this timelapse video of a farm and write a single, brief sentence describing the weather progression throughout the day.
    
    For context, the actual recorded meteorological stats for this day were:
    - High Temperature: 65°F
    - Low Temperature: 48°F
    - Total Precipitation: 0.12 inches
    
    Use these stats to ensure your visual description is highly accurate (e.g. mentioning rainfall if precipitation was recorded). Do not mention the raw numbers in the sentence itself.
    ```
* This ground-truth context will enable the Gemini model to write summaries that match both the visuals and the absolute weather numbers.

---

### 4. Configuration

#### [MODIFY] [config.json](file:///c:/Users/lance/Documents/antigravity/timelapse/config.json)
* Add optional `"weather_units": "imperial"` or `"metric"` key.

---

## Verification Plan

### Automated Tests
1. **Mock Weather API test**: In `test_timelapse.py`, add a test case to mock the Open-Meteo API response and verify that `weather.py` parses the JSON structure correctly.
2. **Uploader/Stats string verification**: Test that the formatting of the stats block handles missing or `None` weather data gracefully.

### Manual Verification
1. Run `python weather.py` standalone to output today's weather for your coordinates to the console.
