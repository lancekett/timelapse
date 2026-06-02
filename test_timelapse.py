import os
import shutil
import unittest
from datetime import datetime, time, timezone, timedelta

# Import modules to test
from scheduler import Sun, TimelapseScheduler
from compiler import archive_midday_frames, extract_time_from_filename


class TestTimelapseScheduler(unittest.TestCase):
    def test_sun_model_sf(self):
        """
        Verify that the astronomical Sun model works for San Francisco coordinates
        on 2026-06-01. (Approximate solar sunrise is 5:48 AM PDT, sunset is 8:25 PM PDT)
        """
        lat = 37.7749
        lon = -122.4194
        
        # Test Date: June 1, 2026
        test_date = datetime(2026, 6, 1).date()
        
        # Simulated Pacific Daylight Time (UTC -7)
        tz_pdt = timezone(timedelta(hours=-7), name="PDT")
        
        sun = Sun(lat, lon)
        sunrise, sunset = sun.get_sunrise_sunset(test_date, tz_pdt)
        
        self.assertIsNotNone(sunrise, "Sunrise calculation returned None")
        self.assertIsNotNone(sunset, "Sunset calculation returned None")
        
        print("\n--- SUN MODEL TEST (San Francisco, June 1, 2026) ---")
        print(f"Calculated Sunrise (PDT): {sunrise.strftime('%I:%M:%S %p')}")
        print(f"Calculated Sunset  (PDT): {sunset.strftime('%I:%M:%S %p')}")
        
        # Assert reasonable values (Sunrise between 5 AM and 7 AM, Sunset between 7 PM and 9 PM)
        self.assertEqual(sunrise.hour, 5)
        self.assertEqual(sunset.hour, 20)  # 8 PM

    def test_scheduler_offsets(self):
        """
        Verify that offsets are applied correctly to the capture window.
        """
        lat = 37.7749
        lon = -122.4194
        
        scheduler = TimelapseScheduler(
            lat=lat,
            lon=lon,
            sunrise_offset_mins=-30,  # 30 mins before
            sunset_offset_mins=45     # 45 mins after
        )
        test_date = datetime(2026, 6, 1).date()
        # Simulated Pacific Daylight Time (UTC -7)
        tz_pdt = timezone(timedelta(hours=-7), name="PDT")
        
        start_dt, end_dt = scheduler.get_capture_window(test_date, tz_pdt)
        
        # Standard sunrise/sunset
        sun = Sun(lat, lon)
        sunrise, sunset = sun.get_sunrise_sunset(test_date, tz_pdt)
        
        # Check start_dt is 30 mins before sunrise
        self.assertEqual(start_dt, sunrise - timedelta(minutes=30))
        # Check end_dt is 45 mins after sunset
        self.assertEqual(end_dt, sunset + timedelta(minutes=45))
        
        print("\n--- SCHEDULER OFFSET TEST ---")
        print(f"Astronomic Sunrise: {sunrise.strftime('%H:%M:%S')}")
        print(f"Recording Starts:   {start_dt.strftime('%H:%M:%S')} (30 mins early)")
        print(f"Astronomic Sunset : {sunset.strftime('%H:%M:%S')}")
        print(f"Recording Ends  :   {end_dt.strftime('%H:%M:%S')} (45 mins late)")


class TestArchiver(unittest.TestCase):
    def setUp(self):
        # Create temp folder for test files
        self.test_dir = "./temp_test_images"
        self.archive_dir = "./temp_test_archive"
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

    def tearDown(self):
        # Clean up files
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.archive_dir):
            shutil.rmtree(self.archive_dir)

    def test_extract_time(self):
        self.assertEqual(extract_time_from_filename("image_20260601_123456.jpg"), "123456")
        self.assertEqual(extract_time_from_filename("image_20260601_080000.png"), "080000")
        self.assertIsNone(extract_time_from_filename("random_filename.jpg"))

    def test_archiving_logic(self):
        """
        Verify that exactly the first N frames from noon (12:00:00) onwards are copied,
        and earlier frames or late-exceeding frames are ignored.
        """
        # Create dummy image files
        test_files = [
            "image_20260601_115800.jpg",  # before noon (ignore)
            "image_20260601_115930.jpg",  # before noon (ignore)
            "image_20260601_120000.jpg",  # exactly noon (keep 1)
            "image_20260601_120030.jpg",  # noon + 30s   (keep 2)
            "image_20260601_120100.jpg",  # noon + 60s   (keep 3)
            "image_20260601_120130.jpg",  # ignore because we cap at 3 frames!
            "image_20260601_130000.jpg",  # ignore
        ]
        
        for name in test_files:
            with open(os.path.join(self.test_dir, name), "w") as f:
                f.write("dummy_image_data")

        # Run archiving with a limit of 3 frames
        copied = archive_midday_frames(
            day_dir=self.test_dir,
            archive_dir=self.archive_dir,
            target_date_str="2026-06-01",
            num_frames=3
        )
        
        # Verify 3 files were copied
        self.assertEqual(len(copied), 3)
        self.assertIn("image_20260601_120000.jpg", copied)
        self.assertIn("image_20260601_120030.jpg", copied)
        self.assertIn("image_20260601_120100.jpg", copied)
        self.assertNotIn("image_20260601_115800.jpg", copied)
        self.assertNotIn("image_20260601_120130.jpg", copied)
        
        # Verify files actually exist in the archive directory
        day_archive_path = os.path.join(self.archive_dir, "2026-06-01")
        self.assertTrue(os.path.exists(os.path.join(day_archive_path, "image_20260601_120000.jpg")))
        self.assertTrue(os.path.exists(os.path.join(day_archive_path, "image_20260601_120030.jpg")))
        self.assertTrue(os.path.exists(os.path.join(day_archive_path, "image_20260601_120100.jpg")))
        self.assertFalse(os.path.exists(os.path.join(day_archive_path, "image_20260601_115800.jpg")))
        self.assertFalse(os.path.exists(os.path.join(day_archive_path, "image_20260601_120130.jpg")))
        
        print("\n--- ARCHIVER TEST ---")
        print(f"Successfully filtered and archived midday frames: {copied}")


if __name__ == "__main__":
    unittest.main()
