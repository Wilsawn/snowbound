"""The 3 Step 1 tests. Delo writes these (so he knows the data cold).

Run with:  make test
Each test is skipped until you write it: delete the pytest.skip line and fill it in.
Use the functions in src/snowbound/loader.py.
"""
import pytest

from snowbound import loader


def test_time_units():
    """Pose times and scan times are both microseconds, and point times are seconds.

    Ideas to check:
      - a GPSTime value has 16 digits
      - a scan file name (scan_time_us) has 16 digits too
      - the point column "t" in one scan stays inside about -0.06..+0.06 seconds
        (one 10 Hz sweep), so it is seconds relative to the scan, not microseconds
    """
    pytest.skip("Delo writes this")


def test_scan_to_pose_timing():
    """Every scan has a pose close in time.

    Ideas to check:
      - pick a few scans across the drive (start, middle, end)
      - nearest_pose(...) gap is under 5 ms (5000 us)
      - bonus: the median gap between scans is about 100 ms (10 Hz)
    """
    pytest.skip("Delo writes this")


def test_heading_sign():
    """Find out which way 'heading' points, and lock it in.

    Ideas to check:
      - take rows where the car is driving (speed > 5 m/s)
      - compare heading with the direction of travel from the velocities:
        atan2(vel_north, vel_east) and atan2(vel_east, vel_north)
      - which one matches (mod 2*pi)? That tells you if heading is measured
        from east (counterclockwise) or from north (clockwise).
      - assert the match, and write the answer in notes/data.md
    """
    pytest.skip("Delo writes this")
