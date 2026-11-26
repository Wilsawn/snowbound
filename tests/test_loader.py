"""Three checks on the Boreas data layout. They skip when the storm drive is not on disk."""
import numpy as np
import pytest

from snowbound import loader

DRIVE = loader.SNOW_DRIVE


def _need_drive():
    if not (loader.drive_path(DRIVE) / "applanix" / "lidar_poses.csv").exists() or not loader.scan_files(DRIVE):
        pytest.skip(f"{DRIVE} is not on disk (set SNOWBOUND_DATA or run scripts/fetch_boreas.py)")


def test_time_units():
    """Pose times and scan times are microseconds (16 digits); point times are seconds within one sweep."""
    _need_drive()
    poses = loader.load_poses(DRIVE)
    assert len(str(int(poses["GPSTime"].iat[0]))) == 16
    first = loader.scan_files(DRIVE)[0]
    assert len(str(loader.scan_time_us(first))) == 16
    pts = loader.load_scan(first)
    t = pts[:, 5]
    assert -0.06 <= float(t.min()) and float(t.max()) <= 0.06


def test_scan_to_pose_timing():
    """Every scan has a pose within 5 ms, checked at the start, middle and end of the drive."""
    _need_drive()
    poses = loader.load_poses(DRIVE)
    files = loader.scan_files(DRIVE)
    for f in (files[0], files[len(files) // 2], files[-1]):
        _, gap_us = loader.nearest_pose(poses, loader.scan_time_us(f))
        assert gap_us <= 5000, f"{f.name}: nearest pose is {gap_us / 1000:.1f} ms away"


def test_heading_sign():
    """Heading in lidar_poses.csv is clockwise from north (atan2(vel_east, vel_north)) minus a fixed
    offset of about 0.77 rad (heading - atan2 is -0.77), the lidar's mount yaw. The offset is constant while driving; the
    counterclockwise-from-east reading is not."""
    _need_drive()
    poses = loader.load_poses(DRIVE)
    moving = poses[np.hypot(poses["vel_east"], poses["vel_north"]) > 5]
    assert len(moving) > 100
    h = moving["heading"].to_numpy()
    e = moving["vel_east"].to_numpy()
    n = moving["vel_north"].to_numpy()

    def spread(d):
        w = np.angle(np.exp(1j * d))
        return np.percentile(w, 90) - np.percentile(w, 10)

    cw_from_north = h - np.arctan2(e, n)
    ccw_from_east = h - np.arctan2(n, e)
    assert spread(cw_from_north) < 0.05
    assert abs(np.median(np.angle(np.exp(1j * cw_from_north))) + 0.77) < 0.05
    assert spread(ccw_from_east) > 1.0
