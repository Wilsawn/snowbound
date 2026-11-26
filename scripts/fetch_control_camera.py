#!/usr/bin/env python3
"""Written with Claude (AI), Nov 21 2026.

Plan (and, with --go, download) the CAMERA for the control drive (Jan 19 2021, no snow falling),
for the part 2 reel. Reuses every safety rule in fetch_boreas.py: official bucket only, allowed
file types only, size and checksum checks, dry run by default, keeps 20 GB free.

Two ways to get the pictures, pick one with the first argument:
  video    the drive's video.mp4 plus applanix/camera_poses.csv. Checked on the storm drive:
           video.mp4 has exactly one frame per camera pose (14,129 frames = 14,129 poses), so it
           is the full 10 Hz camera, played at 30 fps. One file for the whole drive, about 0.75 GB
           on the storm drive. Recommended for video work.
  frames   the camera PNGs (2448x2048, about 5 MB each) for the same stretch of road as the storm
           sample, through fetch_boreas.plan_sample with the control as target, camera on. 10 Hz
           for 12 s is about 120 files.

Run (dry run first, then add --go yourself):
  uv run python scripts/fetch_control_camera.py video  --out ~/snowbound-data
  uv run python scripts/fetch_control_camera.py frames --out ~/snowbound-data --start 3:45 --seconds 60 --cam-hz 10
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_boreas as fb  # the original, unchanged downloader

CONTROL = "boreas-2021-01-19-15-08"


def plan_video(drive):
    jobs = []
    for f in ("video.mp4", "applanix/camera_poses.csv"):
        key = fb.check_key(drive + "/" + f)
        size, etag = fb.head(key)
        jobs.append((key, size, etag))
    return jobs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["video", "frames"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--drive", default=CONTROL)
    ap.add_argument("--start", default="3:45", help="frames: start into the STORM drive's poses (the storm scans we use begin at 3:45)")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--cam-hz", type=float, default=10.0)
    ap.add_argument("--go", action="store_true", help="actually download (default is a dry run)")
    a = ap.parse_args()
    out = os.path.expanduser(a.out)
    if "Mobile Documents" in os.path.realpath(out) or "/Documents/" in os.path.realpath(out) + "/":
        raise SystemExit("refused: keep data out of Documents/iCloud")
    if a.what == "video":
        jobs = plan_video(a.drive)
    else:
        # plan_sample would also fetch the storm's own lidar and camera again; snow_too=False stops that.
        # It fetches lidar too (already on disk: the downloader skips files that exist).
        jobs = fb.plan_sample(out, fb.parse_start(a.start), a.seconds, a.cam_hz, target=a.drive, lidar_only=False, snow_too=False)
        jobs = [j for j in jobs if "/camera/" in j[0]]
    total = sum(s for _, s, _ in jobs)
    free = shutil.disk_usage(out).free
    print("plan %s for %s: %d files, %.2f GB, into %s" % (a.what, a.drive, len(jobs), total / 1e9, out))
    for k, s, _ in jobs[:5]:
        print("  %-60s %6.1f MB" % (k, s / 1e6))
    if len(jobs) > 5:
        print("  ... %d more" % (len(jobs) - 5))
    print("free now %.1f GB, after %.1f GB (minimum kept: %.0f GB)" % (free / 1e9, (free - total) / 1e9, fb.MIN_FREE_GB_AFTER))
    if (free - total) / 1e9 < fb.MIN_FREE_GB_AFTER:
        raise SystemExit("refused: would leave less than %.0f GB free" % fb.MIN_FREE_GB_AFTER)
    if not a.go:
        print("dry run only. Add --go to download.")
        return
    fb.download(out, jobs)


if __name__ == "__main__":
    main()
