#!/usr/bin/env python3
"""Written with Claude (AI), Nov 25 2026. Why did snow hurt at some spots and not others?

Hypothesis (unproven): snow hurts most on wide open roads with little structure nearby.

For each of the 271 height-locked pairs (results/route_pairs_zlock.csv) this measures, at the STORM spot's true pose
(and the map measures again at the CONTROL pose):
  (a) structure: map points 0.5 to 3 m above local ground within 10 m and 20 m of the car (horizontal), plus density
  (b) open width: distance from the car to the nearest structure point on the left and on the right, perpendicular to
      the heading, using map points within 25 m ahead and behind, at least 1 m off the axis; left + right = open width.
      Also a tighter version (open_width10_m): 10 m ahead and behind, at least 1.5 m off the axis, which the 25 m strip
      hitting curbs on curves and cross streets does not spoil
  (c) clutter: share of the day's scan points (> 3 m from the lidar, < 4 m above ground) with no map point within 0.5 m
  (d) speed from the sweep CSVs
Local ground = median z of the map points within 2 to 6 m of the car that lie in the lowest 20 percent of z there.
Found on the first run (Nov 25): on the stretches where the map drive on disk has one scan per 0.1 s (chunks 001 to 003,
009, 010, 012, 013, 019, 020) the sweep's map holds the map drive's own traffic, stamped along the road at car height, so
(a) and (b) as first defined count ghost cars in the car's own lane. So every map measure is computed three ways:
  raw    : the sweep's map as is (every map scan within 25 m)                       columns n_struct_10m, left_m, ...
  thin   : the map thinned to one scan per 1.2 s everywhere (the sweep's nominal design)   columns *_thin
  static : from the thin map, only 0.5 m ground cells that at least 3 different map scans put a band point in
           (a wall or pole is seen by every passing scan, a moving car lands in a cell once)   columns *_static
The static columns are the headline structure and open-width measures; the raw ones are kept as a record.
Frame: the sweep's frame (scripts/sweep_route.py). Each chunk (pair prefix 000 to 022) gets the same local map as the
sweep: every map-drive scan within 25 m of the chunk's storm and control points, keep_ring, 0.3 m voxel per scan,
0.2 m voxel overall, in metres east-north-up relative to the chunk's first storm point. Car pose = pose_matrix(row, origin).

Run:  cd ~/snowbound && nice -n 19 uv run python scripts/why_spots.py            # measure + stats + figures + note tables
      nice -n 19 uv run python scripts/why_spots.py --stats-only                # reuse results/why_spots.csv
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import mannwhitneyu, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402
from score_60s import keep_ring, load_points, pose_matrix, voxel_downsample  # noqa: E402

STORM, CONTROL, MAP = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08", "boreas-2020-11-26-13-58"
ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
LO, HI = 0.5, 3.0          # "structure" band above local ground, metres
OPEN_CAP = 40.0            # open-width distance reported when no structure point is found on a side
MEASURES = [("n_struct_10m_static", "static structure points within 10 m", "points"),
            ("open_width10_m_static", "open width (10 m strip, left + right)", "m"),
            ("clutter_share", "storm clutter (scan points off the map)", "share"),
            ("speed_mps", "speed", "m/s")]


def build_cloud(test_xy, origin):
    """Same point cloud as score_60s.build_map(..., every=1) without the normals."""
    poses = loader.load_poses(MAP)
    files = loader.scan_files(MAP)
    rows = [loader.nearest_pose(poses, loader.scan_time_us(f))[0] for f in files]
    xy = np.array([[r.easting - origin[0], r.northing - origin[1]] for r in rows])
    dist, _ = cKDTree(test_xy).query(xy)
    chosen = np.flatnonzero(dist < 25.0)
    t_us = np.array([loader.scan_time_us(files[j]) for j in chosen])
    thin, last = [], -1e18
    for j, t in zip(chosen, t_us):
        if t - last >= 1.2e6:
            thin.append(j)
            last = t
    chunks, ids = [], []
    for j in chosen:
        T = pose_matrix(rows[j], origin)
        pts = voxel_downsample(keep_ring(load_points(files[j], rows[j], T, True)), 0.3)
        chunks.append(pts @ T[:3, :3].T + T[:3, 3])
        ids.append(np.full(len(pts), j))
    full = voxel_downsample(np.vstack(chunks), 0.2)
    thin_set = set(thin)
    tp = np.vstack([c for c, j in zip(chunks, chosen) if j in thin_set])
    ti = np.concatenate([i for i, j in zip(ids, chosen) if j in thin_set])
    keys = np.floor(tp / 0.2).astype(np.int64)
    _, keep = np.unique(keys, axis=0, return_index=True)
    return full, len(chosen), tp[keep], ti[keep], len(thin)


def heading_of(poses, row):
    """Direction of travel from vel_east, vel_north. If the car is nearly stopped (< 0.5 m/s), use the velocity of the
    nearest pose in time that moves faster than 1 m/s (the pose file's heading column has another convention)."""
    v = np.array([row.vel_east, row.vel_north])
    if np.hypot(*v) >= 0.5:
        return np.arctan2(v[1], v[0]), False
    sp = np.hypot(poses.vel_east.to_numpy(), poses.vel_north.to_numpy())
    ok = np.flatnonzero(sp > 1.0)
    j = ok[np.argmin(np.abs(poses.GPSTime.to_numpy()[ok] - row.GPSTime))]
    return np.arctan2(poses.vel_north.iat[j], poses.vel_east.iat[j]), True


def map_measures(cloud, tree2d, car, heading, scan_id=None, min_scans=3, ground=None):
    """(a) and (b) at one car position, from the chunk's map. With scan_id, only band points in 0.5 m ground cells
    that at least `min_scans` different map scans hit are counted (static structure)."""
    out = {}
    near = tree2d.query_ball_point(car[:2], 6.0)
    near = np.array(near)
    r = np.hypot(*(cloud[near, :2] - car[:2]).T)
    ring = cloud[near[(r >= 2.0)]]
    if len(ring) < 20:
        return None
    z = ring[:, 2]
    if ground is None:
        ground = float(np.median(z[z <= np.quantile(z, 0.2)]))
    out["ground_z_m"] = ground
    out["n_ground_pts"] = int(len(ring))
    idx = np.array(tree2d.query_ball_point(car[:2], 25.0))
    p = cloud[idx]
    h = p[:, 2] - ground
    band = (h >= LO) & (h <= HI)
    struct = p[band]
    if scan_id is not None:
        sid = scan_id[idx][band]
        cell = np.floor(struct[:, :2] / 0.5).astype(np.int64)
        key = cell[:, 0] * 1_000_003 + cell[:, 1]
        pair_key = np.unique(np.c_[key, sid], axis=0)
        cells, n_scans = np.unique(pair_key[:, 0], return_counts=True)
        good = cells[n_scans >= min_scans]
        struct = struct[np.isin(key, good)]
        out["n_cells_static_25m"] = int(len(good))
    d = np.hypot(*(struct[:, :2] - car[:2]).T)
    out["n_struct_10m"] = int((d <= 10).sum())
    out["n_struct_20m"] = int((d <= 20).sum())
    out["dens_10m_per_m2"] = out["n_struct_10m"] / (np.pi * 100)
    out["dens_20m_per_m2"] = out["n_struct_20m"] / (np.pi * 400)
    out["dens_10to20_per_m2"] = (out["n_struct_20m"] - out["n_struct_10m"]) / (np.pi * 300)
    fwd = np.array([np.cos(heading), np.sin(heading)])
    left = np.array([-fwd[1], fwd[0]])
    rel = struct[:, :2] - car[:2]
    s, t = rel @ fwd, rel @ left
    band = np.abs(s) <= 25.0
    tl = t[band & (t >= 1.0)]
    tr = -t[band & (t <= -1.0)]
    out["left_m"] = float(tl.min()) if len(tl) else OPEN_CAP
    out["right_m"] = float(tr.min()) if len(tr) else OPEN_CAP
    out["open_width_m"] = out["left_m"] + out["right_m"]
    out["open_capped"] = int(len(tl) == 0 or len(tr) == 0)
    # tighter version: 10 m ahead and behind, at least 1.5 m off the axis (outside the car body), less hit by curves
    band = np.abs(s) <= 10.0
    tl = t[band & (t >= 1.5)]
    tr = -t[band & (t <= -1.5)]
    out["left10_m"] = float(tl.min()) if len(tl) else OPEN_CAP
    out["right10_m"] = float(tr.min()) if len(tr) else OPEN_CAP
    out["open_width10_m"] = out["left10_m"] + out["right10_m"]
    out["open10_capped"] = int(len(tl) == 0 or len(tr) == 0)
    return out


def clutter(cloud_tree, scan_file, row, T, ground):
    pts = keep_ring(load_points(scan_file, row, T, True))
    moved = pts @ T[:3, :3].T + T[:3, 3]
    moved = moved[moved[:, 2] - ground < 4.0]
    d, _ = cloud_tree.query(moved, distance_upper_bound=0.5)
    return float(np.mean(~np.isfinite(d))), int(len(moved))


def measure(pairs, storm, ctrl):
    poses = {STORM: loader.load_poses(STORM), CONTROL: loader.load_poses(CONTROL)}
    rows_out = []
    t0 = time.time()
    for k, grp in pairs.groupby(pairs.pair.str[:3]):
        ids = list(grp.pair)
        srow = [loader.nearest_pose(poses[STORM], int(storm.loc[i, "scan_time_us"]))[0] for i in ids]
        crow = [loader.nearest_pose(poses[CONTROL], int(ctrl.loc[i, "scan_time_us"]))[0] for i in ids]
        all_xy = np.array([[r.easting, r.northing] for pair in zip(srow, crow) for r in pair])
        origin = np.array([srow[0].easting, srow[0].northing, srow[0].altitude])
        cloud, n_map, tcloud, tid, n_thin = build_cloud(all_xy - origin[:2], origin)
        tree3, tree2 = cKDTree(cloud), cKDTree(cloud[:, :2])
        ttree3, ttree2 = cKDTree(tcloud), cKDTree(tcloud[:, :2])
        for i, sr, cr in zip(ids, srow, crow):
            rec = dict(pair=i, chunk=k, n_map_scans=n_map, n_map_pts=len(cloud), n_map_scans_thin=n_thin, n_map_pts_thin=len(tcloud))
            for day, row, drive, df in (("storm", sr, STORM, storm), ("control", cr, CONTROL, ctrl)):
                T = pose_matrix(row, origin)
                hd, slow = heading_of(poses[drive], row)
                m = map_measures(cloud, tree2, T[:3, 3], hd)
                if m is None:
                    print(f"  {i} {day}: too few ground points, skipped", flush=True)
                    continue
                scan_file = loader.drive_path(drive) / "lidar" / f"{int(df.loc[i, 'scan_time_us'])}.bin"
                share, n = clutter(tree3, scan_file, row, T, m["ground_z_m"])
                m.update(clutter_share=share, n_scan_pts=n, speed_mps=float(df.loc[i, "speed_mps"]), heading_from_neighbour=int(slow))
                mt = map_measures(tcloud, ttree2, T[:3, 3], hd, ground=m["ground_z_m"])
                ms = map_measures(tcloud, ttree2, T[:3, 3], hd, scan_id=tid, ground=m["ground_z_m"])
                share_t, _ = clutter(ttree3, scan_file, row, T, m["ground_z_m"])
                for src, suf in ((mt, "_thin"), (ms, "_static")):
                    m.update({a + suf: b for a, b in src.items() if a not in ("ground_z_m", "n_ground_pts")})
                m["clutter_share_thin"] = share_t
                pre = "" if day == "storm" else "ctrl_"
                rec.update({pre + a: b for a, b in m.items()})
            rows_out.append(rec)
        print(f"chunk {k}: {len(ids)} pairs, {n_map} map scans, {len(cloud):,} map points ({time.time() - t0:.0f} s)", flush=True)
    return pd.DataFrame(rows_out)


def rank_biserial(a, b):
    """Positive when group a tends to be larger than group b."""
    u = mannwhitneyu(a, b, alternative="two-sided").statistic
    return 2 * u / (len(a) * len(b)) - 1


def fmt_p(p):
    return "under 0.001" if p < 0.001 else f"{p:.3f}"


def stats(df, label, keys=None):
    keys = keys or [m[0] for m in MEASURES] + ["open_width_m_static", "left10_m_static", "right10_m_static", "n_struct_20m_static", "dens_10m_per_m2_static", "dens_20m_per_m2_static", "left_m_static", "right_m_static",
                                               "n_struct_10m_thin", "n_struct_20m_thin", "open_width_m_thin", "n_struct_10m", "n_struct_20m", "open_width_m",
                                               "clutter_share_thin", "ctrl_clutter_share", "ctrl_speed_mps", "n_map_scans", "ctrl_n_struct_10m_static", "ctrl_open_width_m_static"]
    hurt, same, big = df[df.group == "hurt"], df[df.group == "same"], df[df.group == "bigger"]
    nb = df[df.group != "bigger"]
    lines = [f"### {label}: hurt {len(hurt)}, same {len(same)}, bigger {len(big)} (bigger kept out of the two-group test)", "",
             "| measure | typical, hurt | typical, same | typical, bigger | hurt minus same | Mann-Whitney p (hurt vs same) | rank-biserial (hurt vs same) | Spearman with diff_m, all | Spearman, no bigger |",
             "|---|---|---|---|---|---|---|---|---|"]
    table = []
    for k in keys:
        a, b = hurt[k].dropna(), same[k].dropna()
        p = mannwhitneyu(a, b, alternative="two-sided").pvalue
        rb = rank_biserial(a, b)
        r_all, p_all = spearmanr(df[k], df.diff_m, nan_policy="omit")
        r_nb, p_nb = spearmanr(nb[k], nb.diff_m, nan_policy="omit")
        row = dict(subset=label, measure=k, n_hurt=len(a), n_same=len(b), median_hurt=a.median(), median_same=b.median(),
                   median_bigger=big[k].median(), p_mw=p, rank_biserial=rb, spearman_all=r_all, spearman_all_p=p_all,
                   spearman_nobig=r_nb, spearman_nobig_p=p_nb)
        table.append(row)
        g = lambda x: f"{x:.3g}" if abs(x) < 10 else f"{x:.0f}"  # noqa: E731
        lines.append(f"| {k} | {g(a.median())} | {g(b.median())} | {g(big[k].median()) if len(big) else 'n/a'} | {g(a.median() - b.median())} | {fmt_p(p)} | {rb:+.2f} | {r_all:+.2f} (p {fmt_p(p_all)}) | {r_nb:+.2f} (p {fmt_p(p_nb)}) |")
    return "\n".join(lines) + "\n", pd.DataFrame(table)


def by_chunk(df):
    rows = []
    for k, g in df.groupby("chunk"):
        rows.append(dict(chunk=k, pairs=len(g), hurt=int((g.group == "hurt").sum()), share_hurt=(g.group == "hurt").mean(),
                         storm_median=g.storm_basin_m.median(), control_median=g.control_basin_m.median(),
                         **{m: g[m].median() for m, _, _ in MEASURES}, n_struct_20m_static=g.n_struct_20m_static.median(),
                         n_struct_10m_raw=g.n_struct_10m.median(), open_width_m_static=g.open_width_m_static.median(), n_map_scans=int(g.n_map_scans.iloc[0]), n_map_scans_thin=int(g.n_map_scans_thin.iloc[0])))
    t = pd.DataFrame(rows)
    lines = ["| chunk | pairs | hurt | share hurt | storm typical | no snow typical | static structure 10 m | static structure 20 m | open width (25 m strip) | open width (10 m strip) | clutter | speed | raw structure 10 m | map scans (thinned) |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in t.itertuples():
        lines.append(f"| {r.chunk} | {r.pairs} | {r.hurt} | {100 * r.share_hurt:.0f}% | {r.storm_median:g} m | {r.control_median:g} m | {r.n_struct_10m_static:.0f} | {r.n_struct_20m_static:.0f} | {r.open_width_m_static:.1f} m | {r.open_width10_m_static:.1f} m | {r.clutter_share:.3f} | {r.speed_mps:.1f} m/s | {r.n_struct_10m_raw:.0f} | {r.n_map_scans} ({r.n_map_scans_thin}) |")
    rho = {m: spearmanr(t.share_hurt, t[m]) for m, _, _ in MEASURES}
    lines.append("")
    lines.append("Across the 23 chunks, Spearman of share hurt with the chunk's typical value: " + "; ".join(f"{m} {r[0]:+.2f} (p {fmt_p(r[1])})" for m, r in rho.items()) + ".")
    return "\n".join(lines) + "\n", t


def figure(df, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 4, figsize=(16, 5), dpi=100)
    fig.patch.set_facecolor("white")
    for ax, (k, title, unit) in zip(axes, MEASURES):
        a, b = df[df.group == "hurt"][k].dropna(), df[df.group == "same"][k].dropna()
        p = mannwhitneyu(a, b, alternative="two-sided").pvalue
        for x, vals, c in ((0, a, "#c0392b"), (1, b, "#2c3e50")):
            ax.scatter(x + rng.uniform(-0.18, 0.18, len(vals)), vals, s=12, alpha=0.5, color=c, linewidths=0)
            ax.hlines(vals.median(), x - 0.3, x + 0.3, color="black", lw=2)
            ax.text(x, vals.median(), f" {vals.median():.3g}", va="bottom", ha="left", fontsize=9)
        ax.set_xticks([0, 1])
        ax.set_xticklabels([f"hurt (n={len(a)})", f"same (n={len(b)})"])
        d = a.median() - b.median()
        ax.set_title(f"{title}\nhurt minus same, typical: {d:+.3g} {unit if unit != 'share' else ''}\nMann-Whitney p = {fmt_p(p)}", fontsize=10)
        ax.set_ylabel(unit)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Storm spots where snow hurt (storm basin smaller than no snow) vs spots where it did not. Black bar = typical (median). Height-locked run.", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def examples(df, out):
    from PIL import Image, ImageDraw, ImageFont
    hurt = df[df.group == "hurt"].copy()
    same = df[df.group == "same"].copy()
    # hurt spots: most open and least structure (rank sum of open width descending and structure ascending)
    hurt["score"] = hurt.open_width10_m_static.rank(ascending=False) + hurt.n_struct_10m_static.rank(ascending=True)
    pick = list(hurt.sort_values("score").pair[:2]) + list(same.sort_values("n_struct_10m_static", ascending=False).pair[:2])
    tiles = []
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except OSError:
        font = ImageFont.load_default()
    for pid in pick:
        r = df.set_index("pair").loc[pid]
        im = Image.open(ROOT / "docs" / "media" / "spots" / f"{pid}_storm_cam.jpg").convert("RGB")
        w, h = im.size
        canvas = Image.new("RGB", (w, h + 140), "white")
        canvas.paste(im, (0, 0))
        dr = ImageDraw.Draw(canvas)
        cap = lambda v, c: ("3 m+" if c else f"{v:g} m")  # noqa: E731
        lines = [f"{pid} ({r.group}): storm {cap(r.storm_basin_m, r.storm_capped)}, no snow {cap(r.control_basin_m, r.control_capped)}",
                 f"static structure within 10 m: {int(r.n_struct_10m_static)} points",
                 f"open width (10 m strip): {r.open_width10_m_static:.1f} m",
                 f"  left {r.left10_m_static:.1f} m, right {r.right10_m_static:.1f} m"]
        for n, s in enumerate(lines):
            dr.text((12, h + 8 + 32 * n), s, fill="black", font=font)
        tiles.append(canvas)
    W = sum(t.width for t in tiles) + 10 * (len(tiles) - 1)
    sheet = Image.new("RGB", (W, tiles[0].height), "white")
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width + 10
    sheet.save(out, quality=88)
    return pick


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats-only", action="store_true")
    a = ap.parse_args()
    pairs = pd.read_csv(RES / "route_pairs_zlock.csv")
    storm = pd.read_csv(RES / "route_storm_zlock.csv").set_index("pair")
    ctrl = pd.read_csv(RES / "route_control_zlock.csv").set_index("pair")
    out_csv = RES / "why_spots.csv"
    if a.stats_only and out_csv.exists():
        df = pd.read_csv(out_csv, dtype={"pair": str, "chunk": str})
    else:
        m = measure(pairs, storm, ctrl)
        df = pairs.merge(m, on="pair")
        df["group"] = np.where(df.storm_basin_m < df.control_basin_m, "hurt", np.where(df.storm_basin_m == df.control_basin_m, "same", "bigger"))
        df.to_csv(out_csv, index=False)
    print(df.group.value_counts().to_string())
    print(f"heading taken from a neighbouring pose (car nearly stopped): storm {int(df.heading_from_neighbour.sum())}, control {int(df.ctrl_heading_from_neighbour.sum())}")
    print(f"open width (10 m strip) capped on a side, static: storm {int(df.open10_capped_static.sum())}, control {int(df.ctrl_open10_capped_static.sum())}")
    print(f"open width capped on a side (raw / thin / static): storm {int(df.open_capped.sum())} / {int(df.open_capped_thin.sum())} / {int(df.open_capped_static.sum())}, "
          f"control {int(df.ctrl_open_capped.sum())} / {int(df.ctrl_open_capped_thin.sum())} / {int(df.ctrl_open_capped_static.sum())}")
    txt_all, t_all = stats(df, "All 271 pairs")
    capped = df[df.control_capped == 1]
    txt_cap, t_cap = stats(capped, "Pairs where no snow was 3 m+ (could have been cut)")
    txt_chunk, t_chunk = by_chunk(df)
    figure(df, RES / "why_spots.png")
    pick = examples(df, RES / "why_spots_examples.jpg")
    print("\n" + txt_all + "\n" + txt_cap + "\n" + txt_chunk)
    print("examples:", pick)
    # storm vs control at the same spots, paired (is the storm scan more cluttered than the control scan?)
    dc = df.clutter_share - df.ctrl_clutter_share
    print(f"clutter storm minus control, typical {dc.median():+.3f}, storm higher at {(dc > 0).sum()} of {len(dc)} spots")
    print(f"spearman storm clutter vs control clutter {spearmanr(df.clutter_share, df.ctrl_clutter_share)[0]:+.2f}")
    print(f"spearman storm structure vs control-pose structure (static) {spearmanr(df.n_struct_10m_static, df.ctrl_n_struct_10m_static)[0]:+.2f}")
    print(f"spearman raw vs static structure within 10 m {spearmanr(df.n_struct_10m, df.n_struct_10m_static)[0]:+.2f}; map scans vs raw {spearmanr(df.n_map_scans, df.n_struct_10m)[0]:+.2f}; map scans vs static {spearmanr(df.n_map_scans, df.n_struct_10m_static)[0]:+.2f}; map scans vs diff_m {spearmanr(df.n_map_scans, df.diff_m)[0]:+.2f}")


if __name__ == "__main__":
    main()
