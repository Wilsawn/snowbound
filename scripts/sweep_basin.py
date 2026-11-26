#!/usr/bin/env python3
"""Blind budget sweep, prototype. See notes/blind-budget.md.

For test points every --spacing metres along a stretch of a test drive:
  - push the starting guess off by each size in --offsets (metres), in --dirs directions,
    heading unchanged, and run scan-to-map ICP. "Recovered" = final error < 0.3 m and < 2 deg.
  - basin radius = the largest size where at least 7 of 8 directions (scaled to --dirs) recover
    AND every smaller size also passed. 0 if the smallest size fails.
  - separately, turn the heading by +/- each angle in --yaws (position unchanged).
The first ICP match radius (--window) is the SAME for every size (default 3.5 m), so the result
measures the road, not a search window that grows with the error. Results hold "for this window";
rerun with a few --window values to show how much the window matters.
If even the largest size recovers, the basin is reported as ">= that size (capped)".
Directions are measured from the direction of travel (0 deg = straight ahead) with a random twist
per point, so along-road and sideways errors are both sampled. --joint-yaw adds that heading error
(random sign) on top of every position offset, because position + heading together is harder.

Run on the Mac (fast); on the VM use few points/offsets:
  uv run python scripts/sweep_basin.py --test boreas-2021-01-26-11-22 --save results/basin_storm.csv
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402
from score_60s import (build_map, icp_point_to_plane, keep_ring, load_points,  # noqa: E402
                       pose_matrix, rot_z, voxel_downsample)


def recovered(T, Tg):
    err = np.hypot(*(T[:2, 3] - Tg[:2, 3]))
    dyaw = np.degrees(np.arctan2(T[1, 0], T[0, 0]) - np.arctan2(Tg[1, 0], Tg[0, 0]))
    dyaw = (dyaw + 180) % 360 - 180
    return bool(err < 0.3 and abs(dyaw) < 2.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", default=loader.SNOW_DRIVE)
    ap.add_argument("--start", type=float, default=0.0, help="seconds into the downloaded test scans")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--spacing", type=float, default=20.0, help="metres between test points")
    ap.add_argument("--max-points", type=int, default=0, help="stop after N points (0 = all)")
    ap.add_argument("--offsets", default="0.25,0.5,0.75,1,1.25,1.5,1.75,2,2.5,3")
    ap.add_argument("--dirs", type=int, default=8)
    ap.add_argument("--yaws", default="2,5,10")
    ap.add_argument("--window", type=float, default=3.5, help="first ICP match radius, same for all sizes")
    ap.add_argument("--joint-yaw", type=float, default=0.0, help="also turn the heading this much at every offset")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save", help="CSV path for one row per test point")
    a = ap.parse_args()
    sizes = [float(x) for x in a.offsets.split(",")]
    yaws = [float(x) for x in a.yaws.split(",")] if a.yaws else []
    need = int(np.ceil(a.dirs * 7 / 8))  # 7 of 8 directions, scaled

    t0 = time.time()
    poses = loader.load_poses(a.test)
    files = loader.scan_files(a.test)
    times = np.array([loader.scan_time_us(f) for f in files])
    idx = np.flatnonzero((times >= times[0] + a.start * 1e6) & (times <= times[0] + (a.start + a.seconds) * 1e6))
    rows = [loader.nearest_pose(poses, int(times[k]))[0] for k in idx]
    origin = np.array([rows[0].easting, rows[0].northing, rows[0].altitude])
    truth = [pose_matrix(r, origin) for r in rows]
    xy = np.array([T[:2, 3] for T in truth])

    # test points every `spacing` metres of driving
    picks, last = [], None
    for i, p in enumerate(xy):
        if last is None or np.hypot(*(p - last)) >= a.spacing:
            picks.append(i)
            last = p
    if a.max_points:
        picks = picks[: a.max_points]

    cloud, normals, tree, n_map = build_map(xy, origin, True)
    print(f"map: {n_map} scans, {len(cloud):,} points; {len(picks)} test points ({time.time() - t0:.0f} s)")

    rng = np.random.default_rng(a.seed)
    out = []
    for i in picks:
        k, row, Tg = idx[i], rows[i], truth[i]
        scan = voxel_downsample(keep_ring(load_points(files[k], row, Tg, True)), 0.5)
        heading = np.arctan2(row.vel_north, row.vel_east)       # direction of travel
        twist = rng.uniform(0, 2 * np.pi / a.dirs)              # random twist per point
        basin, still_ok, per_size = 0.0, True, []
        for s in sizes:
            ok = 0
            for d in range(a.dirs):
                ang = heading + twist + 2 * np.pi * d / a.dirs
                T0 = Tg.copy()
                T0[:2, 3] += s * np.array([np.cos(ang), np.sin(ang)])
                if a.joint_yaw:
                    T0[:3, :3] = rot_z(np.radians(a.joint_yaw) * rng.choice([-1, 1])) @ T0[:3, :3]
                T, _ = icp_point_to_plane(scan, T0, cloud, normals, tree, first_radius=a.window)
                ok += recovered(T, Tg)
            per_size.append(ok)
            if still_ok and ok >= need:
                basin = s
            else:
                still_ok = False
        capped = still_ok  # every size passed: the true basin is at least the largest size
        yaw_ok = {}
        for y in yaws:
            good = 0
            for sign in (-1, 1):
                T0 = Tg.copy()
                T0[:3, :3] = rot_z(np.radians(y) * sign) @ T0[:3, :3]
                T, _ = icp_point_to_plane(scan, T0, cloud, normals, tree, first_radius=a.window)
                good += recovered(T, Tg)
            yaw_ok[y] = good
        speed = float(np.hypot(row.vel_east, row.vel_north))
        out.append((int(times[k]), float(Tg[0, 3]), float(Tg[1, 3]), speed, basin, capped, per_size, yaw_ok))
        shown = f">={basin:.2f} m (capped)" if capped else f"{basin:.2f} m"
        print(f"  point t={int(times[k])}: basin {shown}, ok per size {per_size}, yaw ok {yaw_ok}, "
              f"speed {speed:.1f} m/s ({time.time() - t0:.0f} s)", flush=True)

    if a.save:
        with open(a.save, "w") as f:
            f.write(f"# window={a.window} joint_yaw={a.joint_yaw} sizes={a.offsets} dirs={a.dirs}\n")
            f.write("scan_time_us,x_m,y_m,speed_mps,basin_radius_m,capped,ok_per_size,"
                    + ",".join(f"yaw{y:g}_ok_of_2" for y in yaws) + "\n")
            for t, x, y, sp, b, cp, ps, yo in out:
                f.write(f"{t},{x:.2f},{y:.2f},{sp:.2f},{b},{int(cp)},{'|'.join(map(str, ps))},"
                        + ",".join(str(yo[yy]) for yy in yaws) + "\n")
    measured = [o[4] for o in out if not o[5]]
    n_capped = sum(o[5] for o in out)
    print(f"{len(out)} points: {n_capped} capped (recovered at every size, basin >= {sizes[-1]} m)")
    if measured:
        print(f"uncapped basin radius: median {np.median(measured):.2f} m, min {min(measured):.2f}, "
              f"max {max(measured):.2f} ({time.time() - t0:.0f} s total)")


if __name__ == "__main__":
    main()
