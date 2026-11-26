# Data notes (Boreas)

Checked on the real files, Nov 20 2026:
- lidar_poses.csv: GPSTime in microseconds; easting/northing/altitude in metres; roll/pitch/heading in radians.
- lidar/<time_us>.bin: float32, 6 columns: x, y, z, intensity (0..255), ring (0..127), t (seconds within the sweep, about -0.05..+0.05).
- Drives: map 2020-11-26 (1653 scans), storm 2021-01-26 (1157 scans), control 2020-12-01 (poses only so far).

Heading convention: not yet confirmed; test_heading_sign in tests/test_loader.py is meant to settle it.
