#!/usr/bin/env python3
"""Written with Claude (AI), Nov 21 2026. Pairs storm and control basin test points by location and
prints the storm-minus-control difference. Plain words: for every storm test point, find the
control test point closest to it on the road (within --max-gap metres). Then compare the two
basin radii. A negative difference means the storm day had a smaller margin at that spot.

Also prints recovery rates per offset size (all directions, all points) for both drives, and a
sign test: if snow made no difference, storm-worse and control-worse spots would be about equally
common.

Run: uv run python scripts/compare_basins.py --storm results/basin_storm.csv --control results/basin_control.csv
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_basin_map import read_sweep  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--storm", default="results/basin_storm.csv")
    ap.add_argument("--control", default="results/basin_control.csv")
    ap.add_argument("--storm-drive", default="boreas-2021-01-26-11-22")
    ap.add_argument("--control-drive", default="boreas-2021-01-19-15-08")
    ap.add_argument("--max-gap", type=float, default=5.0)
    ap.add_argument("--save", help="optional CSV of the paired points")
    a = ap.parse_args()

    storm, settings = read_sweep(a.storm, a.storm_drive)
    control, _ = read_sweep(a.control, a.control_drive)
    sizes = [float(x) for x in settings.split("sizes=")[1].split()[0].split(",")]
    dirs = int(settings.split("dirs=")[1].split()[0])

    def per_size(df):
        ok = np.array([[int(v) for v in s.split("|")] for s in df.ok_per_size])
        return 100 * ok.sum(axis=0) / (dirs * len(df))

    print(f"settings: {settings}")
    print(f"storm: {len(storm)} points, median basin {storm.basin_radius_m.median():.2f} m, "
          f"{int(storm.capped.sum())} capped")
    print(f"control: {len(control)} points, median basin {control.basin_radius_m.median():.2f} m, "
          f"{int(control.capped.sum())} capped")
    print("recovery rate by offset size (all points x directions):")
    ps, pc = per_size(storm), per_size(control)
    for s, x, y in zip(sizes, ps, pc):
        print(f"  {s:4.2f} m: storm {x:5.1f}%   control {y:5.1f}%")
    for col in [c for c in storm.columns if c.startswith("yaw")]:
        print(f"  {col}: storm {100 * storm[col].sum() / (2 * len(storm)):.0f}%  control {100 * control[col].sum() / (2 * len(control)):.0f}%")

    # pair by location
    tree = cKDTree(control[["east", "north"]].to_numpy())
    d, j = tree.query(storm[["east", "north"]].to_numpy())
    pairs = storm.assign(gap_m=d, ctrl_idx=j)[d <= a.max_gap].copy()
    pairs["control_basin_m"] = control.basin_radius_m.to_numpy()[pairs.ctrl_idx]
    pairs["control_capped"] = control.capped.to_numpy()[pairs.ctrl_idx]
    pairs["diff_m"] = pairs.basin_radius_m - pairs.control_basin_m
    # distance along the route from the first storm point, so the table reads in road order
    xy = storm[["east", "north"]].to_numpy()
    along = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    pairs["along_m"] = along[pairs.index]
    print(f"\npaired points (nearest control point within {a.max_gap} m): {len(pairs)} of {len(storm)}; "
          f"median gap {pairs.gap_m.median():.2f} m, max {pairs.gap_m.max():.2f} m")
    print("along_m  storm_basin  control_basin  diff(storm-control)")
    for _, r in pairs.iterrows():
        sc = ">=" if r.capped else "  "
        cc = ">=" if r.control_capped else "  "
        print(f"  {r.along_m:6.0f}   {sc}{r.basin_radius_m:4.2f}      {cc}{r.control_basin_m:4.2f}        {r.diff_m:+.2f}")
    worse = int((pairs.diff_m < 0).sum()); better = int((pairs.diff_m > 0).sum()); same = int((pairs.diff_m == 0).sum())
    print(f"storm smaller at {worse}, bigger at {better}, same at {same} of {len(pairs)} pairs")
    print(f"paired difference storm minus control: median {pairs.diff_m.median():+.2f} m, mean {pairs.diff_m.mean():+.2f} m")
    if worse + better:
        p = binomtest(worse, worse + better, 0.5).pvalue
        print(f"sign test (ties dropped): p = {p:.3f}  (points 20 m apart share road, so treat this as rough)")
    if a.save:
        pairs[["along_m", "scan_time_us", "east", "north", "basin_radius_m", "capped", "control_basin_m",
               "control_capped", "gap_m", "diff_m"]].to_csv(a.save, index=False, float_format="%.3f")
        print(f"wrote {a.save}")


if __name__ == "__main__":
    main()
