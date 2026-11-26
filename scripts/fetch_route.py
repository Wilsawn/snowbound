#!/usr/bin/env python3
"""Plan and download lidar for the WHOLE shared route, thinned.

Plain words: the storm, the no-snow day and the map drive all drive the same 7.9 km loop, but not
every part in the same direction or lane. This script:
  1. finds the storm segments where the other two drives pass within 12 m going the same way
     (segments shorter than --min-m are dropped),
  2. maps each storm segment to the other drive's own time window (nearest same-direction pose),
  3. lists that drive's scans in those windows, keeps every Nth (--storm-every, --control-every,
     --map-every), and adds up the bytes from the bucket listing,
  4. prints the plan per drive and the free space after. With --go it downloads through
     fetch_boreas.download, which keeps all its safety rules (official bucket only, size and
     checksum checks, 20 GB kept free).
Full lidar would not fit (the storm alone is about 60 GB), so the scans are thinned: the basin sweep
only needs one scan per test point (every 20 m), and the map only needs enough scans to cover the
road a few times over.

Run:
  uv run python scripts/fetch_route.py --out ~/snowbound-data                     # dry run, prints the plan
  uv run python scripts/fetch_route.py --out ~/snowbound-data --go                # download
"""
import argparse
import os
import shutil
import sys

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import fetch_boreas as fb  # noqa: E402
from snowbound import loader  # noqa: E402

STORM, CONTROL, MAP = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08", "boreas-2020-11-26-13-58"


def poses(drive):
    p = loader.load_poses(drive)
    xy = p[["easting", "northing"]].to_numpy()
    v = p[["vel_east", "vel_north"]].to_numpy()
    sp = np.linalg.norm(v, axis=1)
    fw = v / np.maximum(sp[:, None], 1e-6)
    return p.GPSTime.to_numpy(), xy, fw, sp


def same_way(xy, fw, oxy, ofw, r=12.0):
    """For each pose, is there a pose of the other drive within r metres heading the same way?"""
    tree = cKDTree(oxy)
    ok = np.zeros(len(xy), bool)
    for i in range(len(xy)):
        ok[i] = any(ofw[j] @ fw[i] > 0.5 for j in tree.query_ball_point(xy[i], r))
    return ok


def storm_segments(min_m):
    st, sxy, sfw, ssp = poses(STORM)
    _, cxy, cfw, _ = poses(CONTROL)
    _, mxy, mfw, _ = poses(MAP)
    both = same_way(sxy, sfw, cxy, cfw) & same_way(sxy, sfw, mxy, mfw) & (ssp > 0.3)
    segs, start, last = [], None, None
    for i in np.flatnonzero(both):
        if start is None:
            start = i
        elif (st[i] - st[last]) > 5e6:        # a gap over 5 s ends the segment
            segs.append((start, last))
            start = i
        last = i
    segs.append((start, last))
    out = []
    for a, b in segs:
        m = float(np.sum(np.hypot(*np.diff(sxy[a:b + 1], axis=0).T)))
        if m >= min_m:
            out.append((int(st[a]), int(st[b]), m))
    return out, (st, sxy, sfw)


def other_windows(segs, storm, drive):
    """Each storm segment -> (t_from, t_to) on the other drive, via nearest same-direction poses."""
    st, sxy, sfw = storm
    ot, oxy, ofw, _ = poses(drive)
    tree = cKDTree(oxy)
    wins = []
    for a_us, b_us, _ in segs:
        ia, ib = int(np.searchsorted(st, a_us)), int(np.searchsorted(st, b_us)) - 1
        js = []
        for i in (ia, ib):
            cand = [j for j in tree.query_ball_point(sxy[i], 15.0) if ofw[j] @ sfw[i] > 0.5]
            if cand:
                js.append(min(cand, key=lambda j: np.hypot(*(oxy[j] - sxy[i]))))
        if len(js) == 2 and js[1] > js[0]:
            wins.append((int(ot[js[0]]), int(ot[js[1]])))
    return wins


def plan_drive(drive, wins, every, out):
    jobs, kept, have = [], 0, 0
    listing = list(fb.list_prefix(drive + "/lidar/"))   # a list, so every window can scan it
    for a, b in wins:
        n = 0
        for key, size, etag in listing:
            t = fb.ts_of(key)
            if a <= t <= b:
                if n % every == 0:
                    if os.path.exists(fb.local_path(out, key)):
                        have += 1
                    else:
                        jobs.append((fb.check_key(key), size, etag))
                    kept += 1
                n += 1
    return jobs, kept, have


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-m", type=float, default=400.0, help="drop shared segments shorter than this")
    ap.add_argument("--storm-every", type=int, default=15)
    ap.add_argument("--control-every", type=int, default=15)
    ap.add_argument("--map-every", type=int, default=8)
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    out = os.path.expanduser(a.out)
    segs, storm = storm_segments(a.min_m)
    st0 = storm[0][0]
    print("shared same-direction segments (storm drive seconds):")
    for a_us, b_us, m in segs:
        print("  %6.1f to %6.1f s  %5.0f m" % ((a_us - st0) / 1e6, (b_us - st0) / 1e6, m))
    print("  total %.0f m" % sum(m for _, _, m in segs))
    total, all_jobs = 0, []
    for drive, every in ((STORM, a.storm_every), (CONTROL, a.control_every), (MAP, a.map_every)):
        wins = [(x, y) for x, y, _ in segs] if drive == STORM else other_windows(segs, storm, drive)
        jobs, kept, have = plan_drive(drive, wins, every, out)
        gb = sum(s for _, s, _ in jobs) / 1e9
        total += gb
        all_jobs += jobs
        print("%s: every %d scans, %d scans in plan (%d already on disk), %.2f GB to download" % (drive, every, kept, have, gb))
    free = shutil.disk_usage(out).free / 1e9
    print("total %.2f GB; free now %.1f GB, after %.1f GB (minimum kept: %.0f GB)" % (total, free, free - total, fb.MIN_FREE_GB_AFTER))
    if free - total < fb.MIN_FREE_GB_AFTER:
        raise SystemExit("refused: would leave less than %.0f GB free; thin the scans more" % fb.MIN_FREE_GB_AFTER)
    if not a.go:
        print("dry run only. Add --go to download.")
        return
    fb.download(out, all_jobs)


if __name__ == "__main__":
    main()
