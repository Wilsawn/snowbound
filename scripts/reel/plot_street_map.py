#!/usr/bin/env python3
"""A bird's-eye map of the street for the post.

Plain words:
  1. Background: the street as the car's lidar saw it. We take the map-drive scans (Nov 26 2020)
     whose car position is inside the stretch's box, place every point in the world with the
     ground-truth pose (deskewed, same code as score_60s.py), and flatten them onto a 0.2 m grid:
     how many points fell in each cell, how tall the tallest point is above the lowest one in
     that cell, and how reflective the points are on average. Tall or reflective cells (walls,
     poles, parked cars, road paint) are drawn brighter, so the street shape appears.
  2. Foreground: one dot per test point from sweep_basin.py, coloured by basin radius (green =
     big margin, red = small), storm panel on the left, control panel on the right.
  3. Layout: vertical, for a phone. --layout picks one of three sketches; --vmin picks the
     colour scale floor (0 or 1 m). --size 1080 or 2160 sets the pixel width (height is 16:9).

The raster takes a few minutes, so it is cached as an .npz in --cache (outside results/).

Run:
  uv run python scripts/reel/plot_street_map.py --layout A --vmin 0 --size 1080 --out results/street_map_0to3.png
"""
import argparse
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from snowbound import loader  # noqa: E402
from score_60s import load_points, pose_matrix  # noqa: E402
from plot_basin_map import read_sweep  # noqa: E402

CELL = 0.2  # metres per grid cell


def box_from_pairs(pairs_csv, pad_side=85.0, pad_end=30.0):
    """The stretch's box in world metres: the test points' extent plus padding.
    85 m sideways makes the box about 3x taller than wide, which fills a phone panel."""
    p = pd.read_csv(pairs_csv)
    return (p.east.min() - pad_side, p.east.max() + pad_side, p.north.min() - pad_end, p.north.max() + pad_end)


def build_raster(box, every=2):
    """Flatten the map-drive lidar inside `box` onto a grid. Returns dict of 2D arrays (rows = north)."""
    e0, e1, n0, n1 = box
    nx, ny = int(np.ceil((e1 - e0) / CELL)), int(np.ceil((n1 - n0) / CELL))
    count = np.zeros((ny, nx), np.int32)
    zmax = np.full((ny, nx), -np.inf, np.float32)
    zmin = np.full((ny, nx), np.inf, np.float32)
    isum = np.zeros((ny, nx), np.float32)
    poses = loader.load_poses(loader.MAP_DRIVE)
    files = loader.scan_files(loader.MAP_DRIVE)
    rows = [loader.nearest_pose(poses, loader.scan_time_us(f))[0] for f in files]
    inside = [i for i, r in enumerate(rows) if e0 < r.easting < e1 and n0 < r.northing < n1][::every]
    origin = np.zeros(3)   # world frame directly, no local origin
    t0 = time.time()
    for n, i in enumerate(inside):
        r = rows[i]
        T = pose_matrix(r, origin)
        raw = loader.load_scan(files[i])
        pts = load_points(files[i], r, T, True)                      # deskewed, lidar frame
        rng = np.hypot(pts[:, 0], pts[:, 1])
        keep = (rng > 2.5) & (rng < 70)                               # drop the car itself and far noise
        pts, inten = pts[keep], raw[keep, 3]
        w = pts @ T[:3, :3].T + T[:3, 3]                              # into the world
        ix = ((w[:, 0] - e0) / CELL).astype(int)
        iy = ((w[:, 1] - n0) / CELL).astype(int)
        ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        ix, iy, z, inten = ix[ok], iy[ok], w[ok, 2].astype(np.float32), inten[ok]
        np.add.at(count, (iy, ix), 1)
        np.maximum.at(zmax, (iy, ix), z)
        np.minimum.at(zmin, (iy, ix), z)
        np.add.at(isum, (iy, ix), inten)
        if n % 100 == 0:
            print(f"  raster: scan {n + 1}/{len(inside)} ({time.time() - t0:.0f} s)", flush=True)
    height = np.where(count > 0, zmax - zmin, 0).astype(np.float32)   # tallest above lowest, per cell
    inten = np.where(count > 0, isum / np.maximum(count, 1), 0).astype(np.float32)
    return dict(count=count, height=height, inten=inten, box=np.array(box), n_scans=len(inside))


def shade(r):
    """Turn the three grids into one brightness image, 0 (empty) to 1 (bright)."""
    c = np.log1p(r["count"]) / np.log1p(np.percentile(r["count"][r["count"] > 0], 99))
    h = np.clip(r["height"], 0, 5) / 5                                # 5 m or taller = full
    i = np.clip(r["inten"], 0, np.percentile(r["inten"][r["count"] > 0], 98))
    i = i / max(i.max(), 1e-6)
    v = 0.30 * np.clip(c, 0, 1) + 0.50 * h + 0.20 * i
    v[r["count"] == 0] = 0
    return np.clip(v, 0, 1) * 0.7      # dimmed so the dots are the brightest thing in the picture


def draw_panel(ax, img, box, df, cmap, norm, dot_px, style, crop=0.0):
    e0, e1, n0, n1 = box
    rgb = np.zeros(img.shape + (3,), np.float32)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 0.06 + 0.86 * img, 0.07 + 0.85 * img, 0.10 + 0.82 * img   # cool off-white on near-black
    ax.imshow(rgb, extent=(e0, e1, n0, n1), origin="lower", interpolation="bilinear", zorder=0)
    if style == "segments":   # colour the road itself between consecutive points
        xy = df[["east", "north"]].to_numpy()
        for k in range(len(xy) - 1):
            ax.plot(xy[k:k + 2, 0], xy[k:k + 2, 1], color=cmap(norm(df.basin_radius_m.iloc[k])), lw=dot_px * 0.45,
                    solid_capstyle="round", zorder=3)
        ax.plot(xy[-1:, 0], xy[-1:, 1], marker="o", ms=dot_px * 0.45, color=cmap(norm(df.basin_radius_m.iloc[-1])), zorder=3)
    else:
        ax.scatter(df.east, df.north, c=df.basin_radius_m, cmap=cmap, norm=norm, s=dot_px ** 2,
                   edgecolors="white", linewidths=dot_px * 0.07, zorder=3)
    ax.set_xlim(e0 + crop, e1 - crop)   # crop the sides so the street fills the panel
    ax.set_ylim(n0, n1)
    ax.set_aspect("equal")
    ax.axis("off")


def render(r, storm, control, out, vmin, vmax, layout, width_px):
    img = shade(r)
    box = tuple(r["box"])
    W, H = width_px, int(width_px * 16 / 9)
    dpi = 100
    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi, facecolor="#0b0c10")
    # Same red-yellow-green family as results/basin_map.png, but the darkest green is dropped:
    # on a near-black background the dark green was the lowest-contrast thing in the picture.
    base = plt.get_cmap("RdYlGn")
    cmap = LinearSegmentedColormap.from_list("rdylgn_bright", base(np.linspace(0.0, 0.82, 256)))
    norm = Normalize(vmin=vmin, vmax=vmax)
    s = width_px / 1080                      # scale every size with the output
    ink, dim = "#f3f3f3", "#a9adb5"
    panels = [("Snowstorm", "Jan 26 2021", storm), ("No snow falling", "Jan 19 2021", control)]
    dot = 13 * s

    if layout == "A":   # title top, two tall panels, bar legend at bottom
        fig.text(0.5, 0.962, "Snow cuts the car's\nsafety margin", ha="center", va="center", fontsize=46 * s, color=ink, weight="bold", linespacing=1.05)
        for k, (name, date, df) in enumerate(panels):
            ax = fig.add_axes([0.06 + 0.47 * k, 0.16, 0.41, 0.66])
            draw_panel(ax, img, box, df, cmap, norm, dot, "dots")
            fig.text(0.265 + 0.47 * k, 0.862, name, ha="center", fontsize=26 * s, color=ink, weight="bold")
            fig.text(0.265 + 0.47 * k, 0.838, date, ha="center", fontsize=16 * s, color=dim)
        fig.text(0.5, 0.125, "how far off the car could be and still find itself (m)", ha="center", fontsize=17 * s, color=ink)
        cax = fig.add_axes([0.14, 0.09, 0.72, 0.018])
        legend_bar(fig, cax, cmap, norm, vmin, vmax, s, ink, dim, y_label=None)
        fig.text(0.5, 0.03, "Data: Boreas, University of Toronto", ha="center", fontsize=13 * s, color=dim)

    elif layout == "B":   # title and legend stacked at top, panels fill the rest, dots as road segments
        fig.text(0.06, 0.965, "Snow cuts the car's safety margin", ha="left", va="center", fontsize=36 * s, color=ink, weight="bold")
        fig.text(0.06, 0.935, "how far off the car could be and still find itself (m)", ha="left", va="center", fontsize=16 * s, color=dim)
        cax = fig.add_axes([0.06, 0.905, 0.6, 0.016])
        legend_bar(fig, cax, cmap, norm, vmin, vmax, s, ink, dim, y_label=None)
        for k, (name, date, df) in enumerate(panels):
            ax = fig.add_axes([0.05 + 0.47 * k, 0.05, 0.43, 0.8])
            draw_panel(ax, img, box, df, cmap, norm, dot, "segments")
            fig.text(0.265 + 0.47 * k, 0.862, f"{name}  ·  {date}", ha="center", fontsize=20 * s, color=ink, weight="bold")
        fig.text(0.94, 0.02, "Data: Boreas, University of Toronto", ha="right", fontsize=12 * s, color=dim)

    elif layout == "C":   # the chosen one: big number per panel above the street, panels use the full 9:16 height
        dot = 18 * s
        fig.text(0.5, 0.962, "Snow cuts the car's\nsafety margin", ha="center", va="center", fontsize=46 * s, color=ink,
                 weight="bold", linespacing=1.05)
        # the one sentence that explains the numbers, right under the title where it is read first
        fig.text(0.5, 0.897, "how far off the car's position guess could be\nand it still found itself on the map", ha="center", va="center",
                 fontsize=22 * s, color=dim, linespacing=1.2)
        for k, (name, date, df) in enumerate(panels):
            ax = fig.add_axes([0.02 + 0.49 * k, 0.135, 0.47, 0.62])
            draw_panel(ax, img, box, df, cmap, norm, dot, "dots", crop=30.0)
            med = df.basin_radius_m.median()
            capped_all = bool(df.capped.astype(bool).mean() > 0.5)
            big = f"{med:g} m" + ("+" if capped_all else "")        # "+" = most points recovered at every size tested
            x = 0.255 + 0.49 * k
            fig.text(x, 0.852, f"{name}, {date}", ha="center", fontsize=23 * s, color=ink, weight="bold")
            fig.text(x, 0.815, big, ha="center", va="center", fontsize=54 * s, color=cmap(norm(med)), weight="bold")
            fig.text(x, 0.782, f"typical of {len(df)} test spots", ha="center", va="center", fontsize=20 * s, color=dim)
        fig.text(0.5, 0.108, "each dot is one test spot on the street", ha="center", fontsize=22 * s, color=ink)
        steps = [vmin, (vmin + vmax) / 2, vmax]
        labels = [f"{steps[0]:g} m", f"{steps[1]:g} m", f"{steps[2]:g} m or more"]
        sw = fig.add_axes([0, 0, 1, 1], zorder=6)     # overlay axis so the swatches stay round
        sw.set_xlim(0, 1); sw.set_ylim(0, 1); sw.axis("off"); sw.patch.set_alpha(0)
        for j, (v, lab) in enumerate(zip(steps, labels)):
            x = 0.16 + 0.31 * j
            sw.scatter([x], [0.072], s=(dot * 1.2) ** 2, color=cmap(norm(v)), edgecolors="white", linewidths=dot * 0.07)
            sw.text(x + 0.03, 0.072, lab, ha="left", va="center", fontsize=24 * s, color=ink)
        fig.text(0.5, 0.033, "Data: Boreas, University of Toronto", ha="center", fontsize=19 * s, color=dim)

    fig.savefig(out, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"wrote {out} ({W}x{H}, layout {layout}, scale {vmin:g} to {vmax:g} m, {r['n_scans']} map scans)")


def legend_bar(fig, cax, cmap, norm, vmin, vmax, s, ink, dim, y_label):
    grad = np.linspace(vmin, vmax, 256)[None, :]
    cax.imshow(grad, aspect="auto", cmap=cmap, norm=norm, extent=(vmin, vmax, 0, 1))
    cax.set_yticks([])
    ticks = np.arange(vmin, vmax + 0.01, 0.5)
    cax.set_xticks(ticks)
    cax.set_xticklabels([f"{t:g}" + (" m or more" if t == vmax else "") for t in ticks], fontsize=14 * s, color=ink)
    cax.tick_params(length=0, pad=6 * s)
    for sp in cax.spines.values():
        sp.set_visible(False)
    if y_label is not None:
        fig.text(0.5, y_label, "how far off the car could be and still find itself (m)", ha="center", fontsize=17 * s, color=ink)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--storm", default="results/basin_storm.csv")
    ap.add_argument("--control", default="results/basin_control.csv")
    ap.add_argument("--pairs", default="results/basin_pairs.csv")
    ap.add_argument("--cache", default="/tmp/street_raster.npz", help="where to keep the flattened lidar grid")
    ap.add_argument("--layout", default="A", choices=list("ABC"))
    ap.add_argument("--vmin", type=float, default=0.0)
    ap.add_argument("--vmax", type=float, default=3.0)
    ap.add_argument("--size", type=int, default=1080, help="output width in pixels (height = 16:9 portrait)")
    ap.add_argument("--every", type=int, default=2, help="use every Nth map scan for the background")
    ap.add_argument("--out", default="results/street_map.png")
    ap.add_argument("--raster-preview", help="also save the bare background to this path")
    a = ap.parse_args()

    cache = Path(a.cache)
    if cache.exists():
        r = dict(np.load(cache))
        r["n_scans"] = int(r["n_scans"])
    else:
        r = build_raster(box_from_pairs(a.pairs), every=a.every)
        np.savez_compressed(cache, **r)
    if a.raster_preview:
        plt.imsave(a.raster_preview, shade(r)[::-1], cmap="gray", vmin=0, vmax=1)
    storm, _ = read_sweep(a.storm, "boreas-2021-01-26-11-22")
    control, _ = read_sweep(a.control, "boreas-2021-01-19-15-08")
    render(r, storm, control, a.out, a.vmin, a.vmax, a.layout, a.size)


if __name__ == "__main__":
    main()
