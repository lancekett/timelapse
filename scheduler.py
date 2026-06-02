import math
import logging
from datetime import datetime, timedelta, time, timezone

logger = logging.getLogger("timelapse")

# Constant to convert degrees to radians
TO_RAD = math.pi / 180.0


class Sun:
    """
    Approximated calculation of sunrise and sunset times based on GPS coordinates.
    Adapted from the NOAA Solar Calculator algorithms.
    """
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon
        self.lngHour = lon / 15.0

    def _force_range(self, v, max_val):
        # Force value to be >= 0 and < max_val
        if v < 0:
            return v + max_val
        elif v >= max_val:
            return v - max_val
        return v

    def get_sun_timedelta(self, at_date, is_rise_time=True, zenith=90.833):
        """
        Calculate sunrise or sunset offset from midnight in UTC hours.
        :param at_date: Reference date (datetime)
        :param is_rise_time: True for sunrise, False for sunset
        :param zenith: Sun reference zenith (90.833° accounts for refraction and solar disc size)
        :return: timedelta showing hour, minute, and second of sunrise or sunset, or None if none occurs.
        """
        # 1. Get the day of the year
        N = at_date.timetuple().tm_yday

        # 2. Convert longitude to hour value and calculate approximate time
        if is_rise_time:
            t = N + ((6 - self.lngHour) / 24.0)
        else:
            t = N + ((18 - self.lngHour) / 24.0)

        # 3a. Calculate the Sun's mean anomaly
        M = (0.9856 * t) - 3.289

        # 3b. Calculate the Sun's true longitude
        L = M + (1.916 * math.sin(TO_RAD * M)) + (0.020 * math.sin(TO_RAD * 2 * M)) + 282.634
        L = self._force_range(L, 360)

        # 4a. Calculate the Sun's declination
        sinDec = 0.39782 * math.sin(TO_RAD * L)
        cosDec = math.cos(math.asin(sinDec))

        # 4b. Calculate the Sun's local hour angle
        cosH = (math.cos(TO_RAD * zenith) - (sinDec * math.sin(TO_RAD * self.lat))) / (cosDec * math.cos(TO_RAD * self.lat))

        if cosH > 1:
            return None  # The sun never rises (Polar Night)
        if cosH < -1:
            return None  # The sun never sets (Polar Day)

        # 4c. Finish calculating H and convert into hours
        if is_rise_time:
            H = 360.0 - (1.0 / TO_RAD) * math.acos(cosH)
        else:
            H = (1.0 / TO_RAD) * math.acos(cosH)
        H = H / 15.0

        # 5a. Calculate the Sun's right ascension
        RA = (1.0 / TO_RAD) * math.atan(0.91764 * math.tan(TO_RAD * L))
        RA = self._force_range(RA, 360)

        # 5b. Right ascension value needs to be in the same quadrant as L
        Lquadrant = (math.floor(L / 90.0)) * 90
        RAquadrant = (math.floor(RA / 90.0)) * 90
        RA = RA + (Lquadrant - RAquadrant)

        # 5c. Right ascension value needs to be converted into hours
        RA = RA / 15.0

        # 6. Calculate local mean time of rising/setting
        T = H + RA - (0.06571 * t) - 6.622

        # 7. Adjust back to UTC
        UT = T - self.lngHour
        UT = self._force_range(UT, 24)

        return timedelta(hours=UT)

    def get_sunrise_sunset(self, at_date, tz):
        """
        Calculate local sunrise and sunset datetimes for a given date and timezone.
        :param at_date: Reference date (date or datetime)
        :param tz: Local timezone info (tzinfo)
        :return: (sunrise_datetime, sunset_datetime) in local time, or (None, None)
        """
        # Strip time to get midnight
        midnight = datetime.combine(at_date, time(0, 0, 0, tzinfo=timezone.utc))
        
        rise_delta = self.get_sun_timedelta(midnight, is_rise_time=True)
        set_delta = self.get_sun_timedelta(midnight, is_rise_time=False)
        
        if rise_delta is None or set_delta is None:
            return None, None
            
        # Combine midnight UTC with delta to get UTC datetime
        sunrise_utc = midnight + rise_delta
        sunset_utc = midnight + set_delta
        
        # Convert UTC datetimes to the observer's target timezone
        sunrise_local = sunrise_utc.astimezone(tz)
        sunset_local = sunset_utc.astimezone(tz)
        
        # Adjust for calendar day rollover due to timezone differences
        if sunrise_local.date() < at_date:
            sunrise_local += timedelta(days=1)
        elif sunrise_local.date() > at_date:
            sunrise_local -= timedelta(days=1)

        if sunset_local.date() < at_date:
            sunset_local += timedelta(days=1)
        elif sunset_local.date() > at_date:
            sunset_local -= timedelta(days=1)
        
        return sunrise_local, sunset_local


class TimelapseScheduler:
    def __init__(self, lat, lon, sunrise_offset_mins=-30, sunset_offset_mins=30, fallback_start="06:00", fallback_end="20:00"):
        self.sun = Sun(lat, lon)
        self.sunrise_offset = timedelta(minutes=sunrise_offset_mins)
        self.sunset_offset = timedelta(minutes=sunset_offset_mins)
        
        # Parse fallbacks
        try:
            sh, sm = map(int, fallback_start.split(":"))
            self.fallback_start = time(sh, sm)
            eh, em = map(int, fallback_end.split(":"))
            self.fallback_end = time(eh, em)
        except Exception as e:
            logger.error(f"Failed to parse fallback times {fallback_start}/{fallback_end}: {e}. Defaulting to 06:00-20:00")
            self.fallback_start = time(6, 0)
            self.fallback_end = time(20, 0)

    def get_capture_window(self, target_date=None, tz=None):
        """
        Calculate the absolute start and end datetimes for capturing on the target date.
        """
        if target_date is None:
            target_date = datetime.now().date()
        if tz is None:
            tz = datetime.now().astimezone().tzinfo

        try:
            sunrise, sunset = self.sun.get_sunrise_sunset(target_date, tz)
            if sunrise is not None and sunset is not None:
                start_dt = sunrise + self.sunrise_offset
                end_dt = sunset + self.sunset_offset
                logger.debug(f"Calculated solar window for {target_date}: Sunrise {sunrise.strftime('%H:%M:%S')} (offset -> {start_dt.strftime('%H:%M:%S')}), Sunset {sunset.strftime('%H:%M:%S')} (offset -> {end_dt.strftime('%H:%M:%S')})")
                return start_dt, end_dt
        except Exception as e:
            logger.warning(f"Error calculating sunrise/sunset: {e}. Falling back to default hours.")
        
        # Fallback to hardcoded start/stop times
        start_dt = datetime.combine(target_date, self.fallback_start, tzinfo=tz)
        end_dt = datetime.combine(target_date, self.fallback_end, tzinfo=tz)
        logger.debug(f"Calculated fallback window for {target_date}: Start {start_dt.strftime('%H:%M:%S')}, End {end_dt.strftime('%H:%M:%S')}")
        return start_dt, end_dt

    def is_active(self, current_time=None):
        """
        Check if the current_time is within the active recording window.
        Returns: (is_active, start_datetime, end_datetime)
        """
        if current_time is None:
            current_time = datetime.now().astimezone()
            
        tz = current_time.tzinfo
        date = current_time.date()
        
        start_dt, end_dt = self.get_capture_window(date, tz)
        
        # Check if current_time is within the window
        active = start_dt <= current_time <= end_dt
        return active, start_dt, end_dt
