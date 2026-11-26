#!/usr/bin/env python3
"""Basin sweep over the whole shared route, both days, in parallel. Same test as scripts/sweep_basin.py
and the same settings as notes/results-storm-vs-control.md (offsets 0.25 to 3 m in 8 directions,
5 deg heading error added, 3.5 m first match radius, recovered = under 0.3 m and 2 deg).

Plain words:
  - Test points come from the no-snow day's downloaded scans (thinned to one every 1.5 s, about
    22 m apart). For each one, the storm scan closest to that spot is the paired storm point
    (storm scans are about 11 m apart, so the pair gap is at most about 6 m). Points with no storm
    scan within --max-gap are dropped. So every point is paired by construction.
  - The route is cut into chunks of --chunk points. Each chunk gets its own local map built from
    the map-drive scans within 25 m (the map drive on disk is thinned to one scan per 1.2 s, and
    every one of those is used; the first study used one per 0.4 s).
  - Chunks run in parallel, one process each (--workers). Each writes its own CSVs, so a crash
    loses one chunk, not the run. The final step joins them into results/route_storm.csv,
    results/route_control.csv and results/route_pairs.csv.

Run:
  uv run python scripts/sweep_route.py --workers 8
  uv run python scripts/sweep_route.py --max-points 2 --workers 1      # quick test
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402
from score_60s import build_map, icp_point_to_plane, keep_ring, load_points, pose_matrix, rot_z, voxel_downsample  # noqa: E402
from sweep_basin import recovered  # noqa: E402
from fetch_route import storm_segments, other_windows  # noqa: E402

STORM, CONTROL, MAP = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08", "boreas-2020-11-26-13-58"
SIZES = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3]
DIRS, YAWS, WINDOW, JOINT_YAW = 8, [2, 5, 10], 3.5, 5.0
NEED = int(np.ceil(DIRS * 7 / 8))


def scans_in_windows(drive, wins):
    """Downloaded scans of `drive` whose time falls in any of the windows, with their poses."""
    poses = loader.load_poses(drive)
    files = loader.scan_files(drive)
    t = np.array([loader.scan_time_us(f) for f in files])
    keep = np.zeros(len(t), bool)
    for a, b in wins:
        keep |= (t >= a) & (t <= b)
    idx = np.flatnonzero(keep)
    rows = [loader.nearest_pose(poses, int(t[i]))[0] for i in idx]
    xy = np.array([[r.easting, r.northing] for r in rows])
    return [files[i] for i in idx], t[idx], rows, xy


def pick_points(spacing, max_gap, max_points):
    segs, storm = storm_segments(400.0)
    swins = [(a, b) for a, b, _ in segs]
    cwins = other_windows(segs, storm, CONTROL)
    sf, st, srows, sxy = scans_in_windows(STORM, swins)
    cf, ct, crows, cxy = scans_in_windows(CONTROL, cwins)
    tree = cKDTree(sxy)
    pts, last = [], None
    for j in range(len(cf)):
        if last is not None and np.hypot(*(cxy[j] - last)) < spacing:
            continue
        d, i = tree.query(cxy[j])
        if d > max_gap:
            continue
        pts.append(dict(ctrl=(cf[j], int(ct[j]), crows[j]), storm=(sf[i], int(st[i]), srows[i]), gap=float(d)))
        last = cxy[j]
    if max_points:
        pts = pts[:max_points]
    return pts


def sweep_point(file, row, Tg, cloud, normals, tree, rng):
    """One test point, exactly as sweep_basin.py does it."""
    scan = voxel_downsample(keep_ring(load_points(file, row, Tg, True)), 0.5)
    heading = np.arctan2(row.vel_north, row.vel_east)
    twist = rng.uniform(0, 2 * np.pi / DIRS)
    basin, still_ok, per_size = 0.0, True, []
    for s in SIZES:
        ok = 0
        for d in range(DIRS):
            ang = heading + twist + 2 * np.pi * d / DIRS
            T0 = Tg.copy()
            T0[:2, 3] += s * np.array([np.cos(ang), np.sin(ang)])
            T0[:3, :3] = rot_z(np.radians(JOINT_YAW) * rng.choice([-1, 1])) @ T0[:3, :3]
            T, _ = icp_point_to_plane(scan, T0, cloud, normals, tree, first_radius=WINDOW)
            ok += recovered(T, Tg)
        per_size.append(ok)
        if still_ok and ok >= NEED:
            basin = s
        else:
            still_ok = False
    yaw_ok = {}
    for y in YAWS:
        good = 0
        for sign in (-1, 1):
            T0 = Tg.copy()
            T0[:3, :3] = rot_z(np.radians(y) * sign) @ T0[:3, :3]
            T, _ = icp_point_to_plane(scan, T0, cloud, normals, tree, first_radius=WINDOW)
            good += recovered(T, Tg)
        yaw_ok[y] = good
    return basin, still_ok, per_size, yaw_ok


def run_chunk(args):
    k, pts, outdir, seed = args
    t0 = time.time()
    out = Path(outdir)
    done = out / f"chunk_{k:03d}.done"
    if done.exists():
        return k, "skipped (done)"
    # one local map for the chunk, from the map scans near its points (every downloaded map scan)
    all_xy = np.array([[p[d][2].easting, p[d][2].northing] for p in pts for d in ("storm", "ctrl")])
    origin = np.array([all_xy[0, 0], all_xy[0, 1], pts[0]["storm"][2].altitude])
    cloud, normals, tree, n_map = build_map(all_xy - origin[:2], origin, True, every=1)
    rows_out = {"storm": [], "ctrl": []}
    for n, p in enumerate(pts):
        rng = np.random.default_rng(seed + 1000 * k + n)      # fixed per point, so a rerun gives the same answer
        for day in ("storm", "ctrl"):
            file, t_us, row = p[day]
            Tg = pose_matrix(row, origin)
            basin, capped, per_size, yaw_ok = sweep_point(file, row, Tg, cloud, normals, tree, rng)
            rows_out[day].append(dict(pair=f"{k:03d}_{n:03d}", scan_time_us=t_us, east=row.easting, north=row.northing,
                                      speed_mps=float(np.hypot(row.vel_east, row.vel_north)), basin_radius_m=basin,
                                      capped=int(capped), ok_per_size="|".join(map(str, per_size)),
                                      **{f"yaw{y:g}_ok_of_2": yaw_ok[y] for y in YAWS}, pair_gap_m=p["gap"]))
    for day in ("storm", "ctrl"):
        pd.DataFrame(rows_out[day]).to_csv(out / f"chunk_{k:03d}_{day}.csv", index=False)
    done.write_text(f"{n_map} map scans, {len(cloud)} points, {time.time() - t0:.0f} s\n")
    return k, f"{len(pts)} points, {n_map} map scans, {time.time() - t0:.0f} s"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spacing", type=float, default=20.0)
    ap.add_argument("--max-gap", type=float, default=8.0)
    ap.add_argument("--chunk", type=int, default=24)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-points", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="results/chunks/route-chunks")
    a = ap.parse_args()
    pts = pick_points(a.spacing, a.max_gap, a.max_points)
    gaps = [p["gap"] for p in pts]
    print(f"{len(pts)} paired test points, pair gap median {np.median(gaps):.1f} m, max {max(gaps):.1f} m", flush=True)
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    chunks = [(k, pts[i:i + a.chunk], a.outdir, a.seed) for k, i in enumerate(range(0, len(pts), a.chunk))]
    t0 = time.time()
    with Pool(a.workers) as pool:
        for k, msg in pool.imap_unordered(run_chunk, chunks):
            print(f"  chunk {k}: {msg} ({time.time() - t0:.0f} s elapsed)", flush=True)
    # join
    for day, name in (("storm", "route_storm.csv"), ("ctrl", "route_control.csv")):
        parts = sorted(Path(a.outdir).glob(f"chunk_*_{day}.csv"))
        df = pd.concat([pd.read_csv(p) for p in parts], ignore_index=True)
        df.to_csv(Path("results") / name, index=False)
        print(f"wrote results/{name}: {len(df)} points, median basin {df.basin_radius_m.median():.2f} m, {int(df.capped.sum())} capped")
    s = pd.read_csv("results/route_storm.csv").set_index("pair")
    c = pd.read_csv("results/route_control.csv").set_index("pair")
    pairs = pd.DataFrame(dict(east=s.east, north=s.north, storm_basin_m=s.basin_radius_m, storm_capped=s.capped,
                              control_basin_m=c.basin_radius_m, control_capped=c.capped, gap_m=s.pair_gap_m))
    pairs["diff_m"] = pairs.storm_basin_m - pairs.control_basin_m
    pairs.to_csv("results/route_pairs.csv")
    print(f"wrote results/route_pairs.csv: {len(pairs)} pairs, storm minus control median {pairs.diff_m.median():+.2f} m, "
          f"storm smaller at {(pairs.diff_m < 0).sum()}, bigger at {(pairs.diff_m > 0).sum()}, same at {(pairs.diff_m == 0).sum()}")


if __name__ == "__main__":
    main()
