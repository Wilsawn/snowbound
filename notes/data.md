# Data notes (Boreas)

Checked on the real files, Nov 20 2026:
- lidar_poses.csv: GPSTime in microseconds; easting/northing/altitude in metres; roll/pitch/heading in radians.
- lidar/<time_us>.bin: float32, 6 columns: x, y, z, intensity (0..255), ring (0..127), t (seconds within the sweep, about -0.05..+0.05).
- Drives: map 2020-11-26 (1653 scans), storm 2021-01-26 (1157 scans), control 2020-12-01 (poses only so far).

Heading convention (settled by test_heading_sign on the storm drive): heading is clockwise from north, atan2(vel_east, vel_north), minus a fixed offset of about 0.77 rad (44 degrees; heading minus atan2 is -0.77) that stays constant while driving. The offset is the lidar mount yaw (T_applanix_lidar has a yaw of about 43 degrees), so the heading column describes the lidar frame, not the car. Counterclockwise from east does not fit.
