#!/usr/bin/env python3
"""Written with Claude (AI), Nov 20 2026.

Download a CONTROL drive (a day with no snow falling) for Snowbound, without editing fetch_boreas.py.
It reuses every safety rule in fetch_boreas.py (official bucket only, allowed file types only,
size + checksum checks, dry run by default, keeps 20 GB free).

Why a new file: fetch_boreas.py has the control drive hard-coded to Dec 1 2020, which turned out
to be snowing. This script lets you pick the control with --drive.

Step 1, poses + calibration (small, a few MB), needed before step 2 can line up the road:
  uv run python scripts/fetch_control.py meta   --drive boreas-2021-01-19-15-08 --out ~/snowbound-data        # dry run
  uv run python scripts/fetch_control.py meta   --drive boreas-2021-01-19-15-08 --out ~/snowbound-data --go
Step 2, lidar for the SAME stretch of road as the storm sample (about 600 scans, about 3 GB):
  uv run python scripts/fetch_control.py sample --drive boreas-2021-01-19-15-08 --out ~/snowbound-data --start 3:45 --seconds 60
  (check the "map drive match" line says gaps under 10 m, then add --go)
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_boreas as fb  # the original, unchanged downloader

# Only the small files: calibration + poses. No video (hundreds of MB), no camera.
CONTROL_META = [f for f in fb.META_FILES if not f.endswith(".mp4") and "camera_poses" not in f]


def plan_meta(drive):
    jobs = []
    for f in CONTROL_META:
        key = fb.check_key(drive + "/" + f)
        size, etag = fb.head(key)
        jobs.append((key, size, etag))
    return jobs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", choices=["meta", "sample"])
    ap.add_argument("--drive", required=True, help="control drive, e.g. boreas-2021-01-19-15-08")
    ap.add_argument("--out", required=True, help="data folder outside iCloud, e.g. ~/snowbound-data")
    ap.add_argument("--start", default="0:00", help="sample: start time into the SNOW drive, m:ss")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--go", action="store_true", help="actually download (default is a dry run)")
    a = ap.parse_args()

    if not fb.DRIVE_RE.match(a.drive):
        raise SystemExit("refused: --drive must look like boreas-YYYY-MM-DD-HH-MM")
    if a.drive in (fb.SNOW_DRIVE, fb.MAP_DRIVE):
        raise SystemExit("refused: the control must be a different drive from the map and the storm")
    out = os.path.expanduser(a.out)
    if "Mobile Documents" in os.path.realpath(out) or "/Documents/" in os.path.realpath(out) + "/":
        raise SystemExit("refused: keep data out of Documents/iCloud. Use something like ~/snowbound-data")
    os.makedirs(out, exist_ok=True)

    if a.plan == "meta":
        jobs = plan_meta(a.drive)
    else:
        poses = fb.local_path(out, a.drive + "/applanix/lidar_poses.csv")
        if not os.path.exists(poses):
            raise SystemExit("run the meta step first (needs %s)" % poses)
        # Same stretch of road as the storm sample, same direction, lidar only.
        jobs = fb.plan_sample(out, fb.parse_start(a.start), a.seconds, 1.0,
                              target=a.drive, lidar_only=True, snow_too=False)

    total = sum(s for _, s, _ in jobs)
    free = shutil.disk_usage(out).free
    print("plan %s for %s: %d files, %.2f GB, into %s" % (a.plan, a.drive, len(jobs), total / 1e9, out))
    print("free now %.1f GB, after %.1f GB (minimum kept: %.0f GB)" % (free / 1e9, (free - total) / 1e9, fb.MIN_FREE_GB_AFTER))
    if (free - total) / 1e9 < fb.MIN_FREE_GB_AFTER:
        raise SystemExit("refused: would leave less than %.0f GB free" % fb.MIN_FREE_GB_AFTER)
    if not a.go:
        print("dry run only. Add --go to download.")
        return
    fb.download(out, jobs)


if __name__ == "__main__":
    main()
