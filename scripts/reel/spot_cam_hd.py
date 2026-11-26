#!/usr/bin/env python3
"""Re-extract the spot dashcam photos for the site at 960 px, straight to WebP.

Plain words: the first export (build_site.py) wrote 480 px JPEGs at quality 5 and then WebP copies
of those, so on a 2x screen the photos were upscaled and compressed twice and looked processed.
This script takes the same video frame (the camera pose row nearest the scan time, hood cropped)
and writes one 960 x 694 WebP at quality 82 per spot and day, overwriting the 480 px copy.
Nothing else in docs/data/route.json changes (same file names).

Run: uv run python scripts/reel/spot_cam_hd.py [--only 003_005]
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_site import DOCS, STORM, CONTROL, Drive  # noqa: E402


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    route = json.load(open(DOCS / "data" / "route.json"))
    drives = {"storm": Drive(STORM), "clear": Drive(CONTROL)}
    tmp = Path("/tmp/spot_cam_hd.png")
    n = 0
    for sp in route["spots"]:
        if only and sp["id"] != only:
            continue
        for day, d in drives.items():
            key = f"{day}_cam"
            if key not in sp:
                continue
            out = DOCS / sp[key]
            i, _ = d.nearest_scan(*spot_en(sp, d))
            k = int(np.argmin(np.abs(d.cam_t - d.t[i])))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{k / 30:.3f}", "-i", str(d.video),
                            "-vf", "crop=2160:1560:144:0,scale=960:694", "-frames:v", "1", str(tmp)], check=True)
            Image.open(tmp).save(out, "WEBP", quality=82, method=5)   # this Mac's ffmpeg has no libwebp
            n += 1
            if n % 50 == 0:
                print(n, "written", flush=True)
    print("done", n, "photos")


def spot_en(sp, d):
    """The spot's easting/northing, from results/route_pairs.csv (the same columns build_site.py used)."""
    global _PAIRS
    if "_PAIRS" not in globals():
        import pandas as pd
        t = pd.read_csv("results/route_pairs.csv")
        _PAIRS = {str(r["pair"]): (float(r.east), float(r.north)) for _, r in t.iterrows()}
    return _PAIRS[sp["id"]]


if __name__ == "__main__":
    main()
