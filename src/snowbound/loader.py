"""Load Boreas drives from disk.

Boreas layout (checked on the real files, Nov 20 2026):
  <drive>/applanix/lidar_poses.csv  one row per lidar scan
      GPSTime   microseconds (16 digits, e.g. 1611678138564575)
      easting, northing, altitude   metres, in Boreas's fixed ENU frame
      vel_east, vel_north, vel_up   m/s
      roll, pitch, heading          radians
      angvel_z, angvel_y, angvel_x  rad/s
  <drive>/lidar/<time_us>.bin   one scan, float32, N points x 6 columns:
      x, y, z (metres, lidar frame), intensity (0..255), ring (0..127),
      t (seconds from the scan timestamp, about -0.05..+0.05 for one 10 Hz sweep)
  <drive>/calib/T_applanix_lidar.txt   4x4 transform, lidar frame -> applanix frame
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(os.environ.get("SNOWBOUND_DATA", Path.home() / "snowbound-data"))

# The three drives we use (see notes/plan.md)
MAP_DRIVE = "boreas-2020-11-26-13-58"      # clear, late fall: builds the map
SNOW_DRIVE = "boreas-2021-01-26-11-22"     # snowstorm
CONTROL_DRIVE = "boreas-2020-12-01-13-26"  # clear control, same route

POINT_COLUMNS = ["x", "y", "z", "intensity", "ring", "t"]


def drive_path(drive: str) -> Path:
    return DATA_DIR / drive


def load_poses(drive: str) -> pd.DataFrame:
    """All lidar poses for a drive, sorted by time. Adds t_s (seconds) next to GPSTime (microseconds)."""
    df = pd.read_csv(drive_path(drive) / "applanix" / "lidar_poses.csv")
    df = df.sort_values("GPSTime").reset_index(drop=True)
    df["t_s"] = df["GPSTime"] / 1e6
    return df


def scan_files(drive: str) -> list[Path]:
    """Scan files sorted by time. The file name is the scan time in microseconds."""
    return sorted((drive_path(drive) / "lidar").glob("*.bin"), key=lambda p: int(p.stem))


def scan_time_us(path: Path) -> int:
    return int(path.stem)


def load_scan(path: Path) -> np.ndarray:
    """One scan as an (N, 6) float32 array with POINT_COLUMNS."""
    a = np.fromfile(path, dtype=np.float32)
    if a.size % 6:
        raise ValueError(f"{path.name}: {a.size} floats is not a multiple of 6")
    return a.reshape(-1, 6)


def load_T_applanix_lidar(drive: str) -> np.ndarray:
    """4x4 transform that takes lidar-frame points into the applanix (vehicle) frame."""
    return np.loadtxt(drive_path(drive) / "calib" / "T_applanix_lidar.txt").reshape(4, 4)


def nearest_pose(poses: pd.DataFrame, t_us: int) -> tuple[pd.Series, int]:
    """Pose row closest in time to t_us, and the gap in microseconds."""
    i = int(np.searchsorted(poses["GPSTime"].to_numpy(), t_us))
    best = min((j for j in (i - 1, i) if 0 <= j < len(poses)),
               key=lambda j: abs(int(poses["GPSTime"].iat[j]) - t_us))
    return poses.iloc[best], abs(int(poses["GPSTime"].iat[best]) - t_us)
