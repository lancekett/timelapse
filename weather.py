import urllib.request
import urllib.parse
import json
import logging
from datetime import datetime

logger = logging.getLogger("timelapse")


def fetch_daily_weather(lat, lon, date_str, temp_unit="fahrenheit", precip_unit="inch"):
    """
    Fetches daily maximum temperature, minimum temperature, and total precipitation 
    for a given latitude, longitude, and date using the free Open-Meteo API.
    
    :param lat: Latitude (decimal float)
    :param lon: Longitude (decimal float)
    :param date_str: Target date in YYYY-MM-DD format (string)
    :param temp_unit: 'fahrenheit' or 'celsius'
    :param precip_unit: 'inch' or 'mm'
    :return: Dict containing stats or None if query fails.
    """
    logger.info(f"Fetching weather data for date: {date_str} at Lat: {lat}, Lon: {lon}...")
    
    # Construct parameters
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "temperature_unit": temp_unit,
        "precipitation_unit": precip_unit,
        "start_date": date_str,
        "end_date": date_str
    }
    
    query_string = urllib.parse.urlencode(params)
    url = f"https://api.open-meteo.com/v1/forecast?{query_string}"
    
    logger.debug(f"Querying Open-Meteo API: {url}")
    
    req = urllib.request.Request(url, headers={"User-Agent": "TimelapseBot/1.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                
                daily_data = data.get("daily", {})
                daily_units = data.get("daily_units", {})
                
                # Check if data exists for this date
                times = daily_data.get("time", [])
                if date_str in times:
                    idx = times.index(date_str)
                    
                    # Extract variables
                    max_temp = daily_data.get("temperature_2m_max", [None])[idx]
                    min_temp = daily_data.get("temperature_2m_min", [None])[idx]
                    precip = daily_data.get("precipitation_sum", [None])[idx]
                    
                    # Get units
                    t_unit = daily_units.get("temperature_2m_max", "°F" if temp_unit == "fahrenheit" else "°C")
                    p_unit = daily_units.get("precipitation_sum", "in" if precip_unit == "inch" else "mm")
                    
                    result = {
                        "max_temp": max_temp,
                        "min_temp": min_temp,
                        "precipitation": precip,
                        "temp_unit": t_unit,
                        "precip_unit": p_unit
                    }
                    
                    logger.info(
                        f"Weather Stats for {date_str}: Max {max_temp}{t_unit}, Min {min_temp}{t_unit}, Rain: {precip} {p_unit}"
                    )
                    return result
                else:
                    logger.warning(f"Date {date_str} not found in weather response times: {times}")
                    return None
            else:
                logger.error(f"Open-Meteo API returned HTTP status {response.status}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to fetch weather data from Open-Meteo: {e}")
        return None


if __name__ == "__main__":
    import argparse
    import sys
    
    # Standalone CLI execution for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    parser = argparse.ArgumentParser(description="Test Open-Meteo Daily Weather Fetcher")
    parser.add_argument("--lat", type=float, default=46.52811, help="Latitude (default: 46.52811)")
    parser.add_argument("--lon", type=float, default=-123.01069, help="Longitude (default: -123.01069)")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--celsius", action="store_true", help="Use metric temperature units")
    parser.add_argument("--mm", action="store_true", help="Use metric precipitation units")
    
    args = parser.parse_args()
    
    t_unit = "celsius" if args.celsius else "fahrenheit"
    p_unit = "mm" if args.mm else "inch"
    
    res = fetch_daily_weather(args.lat, args.lon, args.date, temp_unit=t_unit, precip_unit=p_unit)
    if res:
        print("\n--- 🌤️ Weather Output ---")
        print(f"Date:          {args.date}")
        print(f"Coordinates:   {args.lat}, {args.lon}")
        print(f"Max Temp:      {res['max_temp']}{res['temp_unit']}")
        print(f"Min Temp:      {res['min_temp']}{res['temp_unit']}")
        print(f"Precipitation: {res['precipitation']} {res['precip_unit']}")
    else:
        print("\n❌ Failed to retrieve weather data.")
