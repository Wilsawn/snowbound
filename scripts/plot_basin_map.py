#!/usr/bin/env python3
"""Draws the "Blind budget" map from two sweep_basin.py CSVs.

Plain words: each test point on the road gets a colour for its basin radius, the biggest starting
error that scan-to-map ICP still recovered from. Green = big margin (the car can be far off and
still re-find itself), red = small margin. Storm (falling snow) on the top row, control (no falling
snow, same road, a week earlier) on the bottom row.

The stretch tested is a straight road (about 450 m, heading north), so a true top-down map is a
thin vertical line. The figure draws the road left to right instead: x = metres driven from the
first storm test point, measured along the storm's ground-truth path. The control points are put
at the along-road distance of the storm point they were paired with (nearest within a few metres).

Run: uv run python scripts/plot_basin_map.py --storm results/basin_storm.csv --control results/basin_control.csv --out results/basin_map.png
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402


def read_sweep(path, drive):
    """Read one sweep CSV and put its points in world (east, north) metres.
    sweep_basin.py writes x_m, y_m relative to the first scan of its own stretch, so the two
    drives have different origins. The first row of the CSV IS that first scan (x = y = 0), so
    origin = its ground-truth pose minus its (x, y)."""
    with open(path) as f:
        settings = f.readline().strip("# \n")
    df = pd.read_csv(path, comment="#")
    poses = loader.load_poses(drive)
    row0, _ = loader.nearest_pose(poses, int(df.scan_time_us.iloc[0]))
    origin = np.array([row0.easting - df.x_m.iloc[0], row0.northing - df.y_m.iloc[0]])
    df["east"] = df.x_m + origin[0]
    df["north"] = df.y_m + origin[1]
    return df, settings


def along_road(storm, control):
    """Metres driven from the first storm point, for every storm point; control points get the
    distance of their nearest storm point plus the small along-road gap to it."""
    xy = storm[["east", "north"]].to_numpy()
    seg = np.diff(xy, axis=0)
    along = np.r_[0, np.cumsum(np.hypot(*seg.T))]
    storm = storm.assign(along=along)
    tree = cKDTree(xy)
    d, j = tree.query(control[["east", "north"]].to_numpy())
    # direction of travel at each storm point, to project the control point's offset onto the road
    fwd = np.vstack([seg[0], seg]) / np.hypot(*np.vstack([seg[0], seg]).T)[:, None]
    proj = np.einsum("ij,ij->i", control[["east", "north"]].to_numpy() - xy[j], fwd[j])
    control = control.assign(along=along[j] + proj, gap=d)
    return storm, control


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--storm", default="results/basin_storm.csv")
    ap.add_argument("--control", default="results/basin_control.csv")
    ap.add_argument("--storm-drive", default="boreas-2021-01-26-11-22")
    ap.add_argument("--control-drive", default="boreas-2021-01-19-15-08")
    ap.add_argument("--out", default="results/basin_map.png")
    ap.add_argument("--vmin", type=float, default=0.0, help="bottom of the colour scale (0 = red means no margin at all)")
    ap.add_argument("--vmax", type=float, default=3.0, help="top of the colour scale (the largest offset tested)")
    ap.add_argument("--weak", default="326,462", help="along-road metres of the earlier 'weak stretch' (storm 40 to 60 s), to shade")
    a = ap.parse_args()

    storm, settings = read_sweep(a.storm, a.storm_drive)
    control, _ = read_sweep(a.control, a.control_drive)
    storm, control = along_road(storm, control)

    cmap = plt.get_cmap("RdYlGn")          # green = big margin, red = small, same scale on both rows
    norm = matplotlib.colors.Normalize(vmin=a.vmin, vmax=a.vmax)

    fig, ax = plt.subplots(figsize=(13, 5.2), facecolor="white")
    rows = [(1.0, "Storm\nJan 26 2021\nsnow falling", storm), (0.0, "Control\nJan 19 2021\nno snow falling", control)]
    x_max = max(storm.along.max(), control.along.max()) + 10
    w0, w1 = (float(v) for v in a.weak.split(","))
    ax.axvspan(w0, w1, color="#f2f2f2", zorder=0)
    ax.text((w0 + w1) / 2, 1.62, "the earlier weak stretch: storm restarts 1 m / 5 deg off\nrecovered only 62% (earlier test, 2 m match radius)", ha="center", va="center",
            fontsize=9.5, color="#555555")
    for y, label, df in rows:
        ax.plot([-10, x_max], [y, y], color="#d0d0d0", lw=10, solid_capstyle="round", zorder=1)
        ax.scatter(df.along, np.full(len(df), y), c=df.basin_radius_m, cmap=cmap, norm=norm, s=230,
                   edgecolors="white", linewidths=1.2, zorder=3)
        cap = df.capped.astype(bool).to_numpy()
        if cap.any():   # ring = recovered at every size tested, so the true basin is at least vmax
            ax.scatter(df.along[cap], np.full(cap.sum(), y), s=420, facecolors="none", edgecolors="#2b2b2b",
                       linewidths=0.9, zorder=4)
        ax.text(-18, y, label, ha="right", va="center", fontsize=11, color="#222222")
        ax.text(x_max + 6, y, f"median\n{df.basin_radius_m.median():.2f} m", ha="left", va="center",
                fontsize=10, color="#444444")
    ax.set_xlim(-120, x_max + 60)
    ax.set_ylim(-0.7, 1.9)
    ax.set_yticks([])
    ax.set_xticks(np.arange(0, x_max, 50))
    ax.set_xlabel("metres along the road (driving north, same direction both days)", fontsize=11)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#999999")
    ax.tick_params(colors="#555555")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.06, pad=0.2, aspect=45)
    lo = min(storm.basin_radius_m.min(), control.basin_radius_m.min())
    floor = (f"scale starts at {a.vmin:g} m, the smallest margin seen" if a.vmin > 0 else f"no point fell below {lo:g} m")
    cb.set_label(f"biggest start error (metres) the lidar still recovered from, {floor}     "
                 f"(ring = recovered at every size tested, at least {a.vmax:g} m)", fontsize=10)
    cb.outline.set_visible(False)
    fig.suptitle("How far off can the car's guess be and still re-find itself? Same Toronto road, with and without falling snow",
                 fontsize=13.5, y=0.99)
    fig.text(0.5, -0.03, "Scan-to-map ICP against a map from the Nov 26 2020 drive (ground-truth poses). Each point: 10 offset sizes x 8 directions "
             "plus a 5 deg heading error, 3.5 m first match radius. Data: Boreas, University of Toronto (CC BY 4.0).",
             ha="center", fontsize=9.5, color="#666666")
    fig.savefig(a.out, dpi=200, bbox_inches="tight")
    print(f"wrote {a.out}: storm {len(storm)} points, control {len(control)} points "
          f"(control to storm gap median {control.gap.median():.2f} m, max {control.gap.max():.2f} m); settings: {settings}")


if __name__ == "__main__":
    main()
