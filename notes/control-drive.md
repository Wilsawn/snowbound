# Which drive is the "no falling snow" control?
Nov 20 2026, checked separately.

## Official weather tags (Boreas download page, checked; "Snow" = snow on the ground, "Snowing" = snow falling)
| Drive | Tags | Notes |
|---|---|---|
| boreas-2020-11-26-13-58 | Overcast, Snow | our map |
| boreas-2020-12-01-13-26 | Overcast, Snow, **Snowing** | NOT a control (matches the dashcam) |
| boreas-2020-12-18-13-44 | Sun, Snow | Gupta et al. (Sensors 2025) used it as a "sunny" map |
| boreas-2021-01-19-15-08 | Clouds, Snow | 7 days before the storm |
| boreas-2021-01-26-11-22 | Overcast, Snow, **Snowing** | our storm (don't mix up with 2021-01-26-10-59) |
| boreas-2021-02-02-14-07 | Overcast, Snow | 7 days after |
| boreas-2021-03-09-14-23 | Sun | no snow on the ground |
Sources: boreas.utias.utoronto.ca/#/download, S3 listing (all names exist), Gupta et al. Sensors 25(24):7436 (2025).

## Recommendation
**First choice: boreas-2021-01-19-15-08.** Same season as the storm (snowbanks, bare trees), tagged not snowing, cloudy like the other two.
**Caveat:** Environment Canada recorded 0.6 cm of light snow at Pearson that day (Toronto City: 0.0 mm). "Not snowing" is read from the tag, not proven. Watch its preview before downloading.
**Backup: boreas-2020-12-18-13-44.** Sunny, used by another paper as a clear map, easy to defend, but 39 days from the storm.

## Before downloading
1. Watch 1 minute of each preview and check: is snow falling? is the road dry?
   - 2021-01-19: https://www.youtube.com/watch?v=_LLDeb7Vo6g
   - 2020-12-18: https://www.youtube.com/watch?v=dxtUnSWLinE
2. Size: a whole drive's lidar is about 50 GB. We only download the same 60 s stretch (about 600 scans, about 3 GB), plus poses and calib (small).
3. scripts/fetch_boreas.py still has CLEAR_DRIVE = Dec 1 hard-coded. Proposed change: add a `--drive` option so the control can be any drive, then:
   ```
   cd ~/snowbound
   uv run python scripts/fetch_boreas.py control-meta   --drive boreas-2021-01-19-15-08 --out ~/snowbound-data        # poses + calib, dry run
   uv run python scripts/fetch_boreas.py control-sample --drive boreas-2021-01-19-15-08 --out ~/snowbound-data --start 3:45 --seconds 60   # dry run, then add --go
   ```
