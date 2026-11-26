#!/usr/bin/env python3
"""The whole-route basin sweep again, with the matcher's height, roll and pitch locked.

Plain words:
  - Same test as scripts/sweep_route.py (same 271 paired points, same seeds, sizes 0.25 to 3 m, 8 directions,
    5 deg heading error, 3.5 m window, recovered = under 0.3 m and 2 deg), but the point-to-plane matcher may only
    move the scan in x, y and yaw. The 23 November check (notes/critic-most-affected.md) found the free matcher
    sinks moving storm scans about 2.5 m so the snow in the air lands on the road, which the test counted as a failure.
  - Every chunk is written as it finishes to results/chunks/route-chunks-zlock/ with a .done marker, so a stopped run resumes.
  - Results go to NEW files: results/route_storm_zlock.csv, route_control_zlock.csv, route_pairs_zlock.csv. The
    originals are not touched. Each row also carries dz_max_m: the largest height change the matcher made at that
    point over every run (it should be 0 with the lock; it is measured, not assumed).
  - The script refuses to run if the picked points are not the same 271 pairs (same ids and scan times) as the
    original results/route_storm.csv and route_control.csv.

Run:  cd ~/snowbound && nice -n 19 uv run python scripts/sweep_route_zlock.py --workers 6 --chunk 12
Test: nice -n 19 uv run python scripts/sweep_route_zlock.py --max-points 2 --workers 1 --outdir results/chunks/route-chunks-zlock-test --suffix _zlocktest
"""
import argparse
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sweep_route  # noqa: E402
from score_60s import build_map, pose_matrix, rot_z  # noqa: E402
from sweep_route import YAWS, pick_points, sweep_point  # noqa: E402

DZ = {"max": 0.0}   # largest |height change| seen by the locked matcher in this process, reset per point


def icp_zlock(scan, T, cloud, normals, tree, iters=30, huber=0.1, first_radius=2.0):
    """score_60s.icp_point_to_plane with the height, roll and pitch locked: only yaw, x and y are solved."""
    z0 = T[2, 3]
    for n in range(iters):
        max_d = first_radius if n < 10 else (1.0 if n < 20 else 0.5)
        moved = scan @ T[:3, :3].T + T[:3, 3]
        d, j = tree.query(moved, distance_upper_bound=max_d)
        ok = np.isfinite(d)
        if ok.sum() < 50:
            DZ["max"] = max(DZ["max"], abs(T[2, 3] - z0))
            return T, False
        p, q, nrm = moved[ok], cloud[j[ok]], normals[j[ok]]
        c = T[:3, 3]
        A = np.c_[np.cross(p - c, nrm), nrm][:, [2, 3, 4]]   # yaw, x, y only
        b = -np.einsum("ij,ij->i", p - q, nrm)
        k = max(huber, max_d / 2)
        w = np.sqrt(np.minimum(1.0, k / np.maximum(np.abs(b), 1e-9)))
        dx = np.linalg.lstsq(A * w[:, None], b * w, rcond=None)[0]
        T = T.copy()
        T[:3, :3] = rot_z(dx[0]) @ T[:3, :3]
        T[:3, 3] = c + np.r_[dx[1:], 0.0]
        if np.linalg.norm(dx) < 1e-5:
            break
    DZ["max"] = max(DZ["max"], abs(T[2, 3] - z0))
    return T, True


sweep_route.icp_point_to_plane = icp_zlock          # sweep_point looks it up in its module globals


def run_chunk(args):
    k, pts, outdir, seed = args
    t0 = time.time()
    out = Path(outdir)
    done = out / f"chunk_{k:03d}.done"
    if done.exists():
        return k, "skipped (done)"
    all_xy = np.array([[p[d][2].easting, p[d][2].northing] for p in pts for d in ("storm", "ctrl")])
    origin = np.array([all_xy[0, 0], all_xy[0, 1], pts[0]["storm"][2].altitude])
    cloud, normals, tree, n_map = build_map(all_xy - origin[:2], origin, True, every=1)
    rows_out = {"storm": [], "ctrl": []}
    for n, p in enumerate(pts):
        rng = np.random.default_rng(seed + 1000 * k + n)      # same seed per point as the original run
        for day in ("storm", "ctrl"):
            file, t_us, row = p[day]
            Tg = pose_matrix(row, origin)
            DZ["max"] = 0.0
            basin, capped, per_size, yaw_ok = sweep_point(file, row, Tg, cloud, normals, tree, rng)
            rows_out[day].append(dict(pair=f"{k:03d}_{n:03d}", scan_time_us=t_us, east=row.easting, north=row.northing,
                                      speed_mps=float(np.hypot(row.vel_east, row.vel_north)), basin_radius_m=basin,
                                      capped=int(capped), ok_per_size="|".join(map(str, per_size)),
                                      **{f"yaw{y:g}_ok_of_2": yaw_ok[y] for y in YAWS}, pair_gap_m=p["gap"],
                                      dz_max_m=float(DZ["max"])))
    for day in ("storm", "ctrl"):
        pd.DataFrame(rows_out[day]).to_csv(out / f"chunk_{k:03d}_{day}.csv", index=False)
    done.write_text(f"{n_map} map scans, {len(cloud)} points, {time.time() - t0:.0f} s\n")
    return k, f"{len(pts)} points, {n_map} map scans, {time.time() - t0:.0f} s"


def check_same_points(pts, chunk):
    """The locked run must test exactly the pairs of the original run."""
    s = pd.read_csv("results/route_storm.csv").set_index("pair")
    c = pd.read_csv("results/route_control.csv").set_index("pair")
    bad = 0
    for i, p in enumerate(pts):
        pid = f"{i // chunk:03d}_{i % chunk:03d}"
        if pid not in s.index or s.loc[pid, "scan_time_us"] != p["storm"][1] or c.loc[pid, "scan_time_us"] != p["ctrl"][1]:
            bad += 1
    return len(s), bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spacing", type=float, default=20.0)
    ap.add_argument("--max-gap", type=float, default=8.0)
    ap.add_argument("--chunk", type=int, default=12)   # the original route run used 12 points per chunk (23 chunks); the pair ids depend on it
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-points", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="results/chunks/route-chunks-zlock")
    ap.add_argument("--suffix", default="_zlock")
    a = ap.parse_args()
    pts = pick_points(a.spacing, a.max_gap, a.max_points)
    n_orig, bad = check_same_points(pts, a.chunk)
    print(f"{len(pts)} paired test points ({n_orig} in the original run), {bad} differ from the original pairing", flush=True)
    if not a.max_points and (len(pts) != n_orig or bad):
        sys.exit("the picked points are not the original pairs; stopping (nothing written)")
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    chunks = [(k, pts[i:i + a.chunk], a.outdir, a.seed) for k, i in enumerate(range(0, len(pts), a.chunk))]
    t0 = time.time()
    with Pool(a.workers) as pool:
        for k, msg in pool.imap_unordered(run_chunk, chunks):
            print(f"  chunk {k}: {msg} ({time.time() - t0:.0f} s elapsed)", flush=True)
    for day, name in (("storm", f"route_storm{a.suffix}.csv"), ("ctrl", f"route_control{a.suffix}.csv")):
        parts = sorted(Path(a.outdir).glob(f"chunk_*_{day}.csv"))
        df = pd.concat([pd.read_csv(p) for p in parts], ignore_index=True)
        df.to_csv(Path("results") / name, index=False)
        print(f"wrote results/{name}: {len(df)} points, median basin {df.basin_radius_m.median():.2f} m, "
              f"{int(df.capped.sum())} capped, dz max {df.dz_max_m.max():.4f} m")
    s = pd.read_csv(f"results/route_storm{a.suffix}.csv").set_index("pair")
    c = pd.read_csv(f"results/route_control{a.suffix}.csv").set_index("pair")
    pairs = pd.DataFrame(dict(east=s.east, north=s.north, storm_basin_m=s.basin_radius_m, storm_capped=s.capped,
                              control_basin_m=c.basin_radius_m, control_capped=c.capped, gap_m=s.pair_gap_m))
    pairs["diff_m"] = pairs.storm_basin_m - pairs.control_basin_m
    pairs.to_csv(f"results/route_pairs{a.suffix}.csv")
    print(f"wrote results/route_pairs{a.suffix}.csv: {len(pairs)} pairs, storm minus control median {pairs.diff_m.median():+.2f} m, "
          f"storm smaller at {(pairs.diff_m < 0).sum()}, bigger at {(pairs.diff_m > 0).sum()}, same at {(pairs.diff_m == 0).sum()}")


if __name__ == "__main__":
    main()
