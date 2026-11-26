#!/usr/bin/env python3
"""Written with Claude (AI), Nov 21 2026. Chase-cam lidar clips for the part 2 reel (top half of a split screen).

Plain words:
  - For a stretch of one drive, show each lidar scan from a camera that floats behind and above
    the car, looking down the street. Points are coloured by height above the road (rainbow on
    black). Falling snow stays in (nothing is filtered).
  - The car is a clean white box at the lidar's position (the lidar sits on the roof).
  - A glowing ring on the road around the car shows the "safety zone": the basin radius from
    sweep_basin.py for the nearest test point (results/basin_*.csv). The ring changes size as
    the car passes each test point. "3 m+" means that point recovered at every size tested.
  - The two clips (no snow, snowstorm) are matched by position: frame k of the control clip
    shows the control scan taken closest to where the storm car is at frame k, so both cars
    are at the same spot in both panels even though the control car drove faster.

Run:
  uv run python scripts/render_chase.py --look A --still 347 --out results/sketch_A.png      # one still at 347 m along
  uv run python scripts/render_chase.py --look A --seconds 12 --fps 30 --frames-dir /tmp/chase  # all frames
"""
import argparse
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402
from score_60s import pose_matrix, load_points  # noqa: E402
from plot_basin_map import read_sweep  # noqa: E402

STORM, CONTROL = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08"
CAR_L, CAR_W, CAR_H = 5.0, 1.95, 1.65     # white box size in metres (a full-size SUV, roughly)

# The three looks the critic chooses from. height/back = camera metres above and behind the lidar.
# The camera stays within 7 m of the car: another vehicle drove about 7 to 9.5 m behind the storm
# car for the whole stretch (checked on every 60th scan), and a camera further back than that
# would look straight through it. Nothing is filtered; the camera just sits in front of it.
LOOKS = {
    "A": dict(height=4.5, back=6.5, side=0.0, cmap="jet",   ring="thin",  pt=1.6, fov=80),
    "B": dict(height=9.0, back=7.0, side=2.0, cmap="turbo", ring="disc",  pt=1.4, fov=75),
    "C": dict(height=8.5, back=6.5, side=1.0, cmap="turbo", ring="glow",  pt=1.5, fov=76),   # the critic's pick
}


# ---------- data for one drive ----------
class Drive:
    def __init__(self, name, basin_csv):
        self.name = name
        self.poses = loader.load_poses(name)
        self.files = loader.scan_files(name)
        self.t = np.array([loader.scan_time_us(f) for f in self.files])
        self.rows = [loader.nearest_pose(self.poses, int(x))[0] for x in self.t]
        self.xy = np.array([[r.easting, r.northing] for r in self.rows])
        self.tree = cKDTree(self.xy)
        b, _ = read_sweep(basin_csv, name)
        self.pts_xy = b[["east", "north"]].to_numpy()
        self.pts_tree = cKDTree(self.pts_xy)
        self.basin = b.basin_radius_m.to_numpy()
        self.capped = b.capped.astype(bool).to_numpy()

    def scan_at(self, i):
        """World-frame points of scan i (deskewed), plus the lidar pose matrix."""
        T = pose_matrix(self.rows[i], np.zeros(3))
        p = load_points(self.files[i], self.rows[i], T, True)
        p = p[np.hypot(p[:, 0], p[:, 1]) > 3.0]       # drop returns from the car itself (same cut as score_60s.py)
        return p @ T[:3, :3].T + T[:3, 3], T

    def ring_at(self, xy):
        """Basin radius and capped flag of the test point nearest to xy."""
        _, j = self.pts_tree.query(xy)
        return float(self.basin[j]), bool(self.capped[j])


# ---------- camera ----------
def look_at(C, target):
    """Rotation that makes the camera at C look at `target`, z up. Returns rows (right, down, forward)."""
    f = target - C
    f /= np.linalg.norm(f)
    r = np.cross(f, np.array([0, 0, 1.0]))
    r /= np.linalg.norm(r)
    d = np.cross(f, r)
    return np.vstack([r, d, f])


def project(P, C, R, W, H, fov_deg):
    """Pinhole projection of world points P. Returns pixel x, y and depth."""
    q = (P - C) @ R.T
    depth = q[:, 2]
    fpx = (H / 2) / np.tan(np.radians(fov_deg) / 2)     # vertical field of view
    with np.errstate(divide="ignore", invalid="ignore"):
        x = W / 2 + fpx * q[:, 0] / depth
        y = H / 2 + fpx * q[:, 1] / depth
    return x, y, depth


def ground_height(pts, T):
    """Road height near the car: the 5th percentile of point heights 3 to 10 m from the lidar."""
    d = np.hypot(pts[:, 0] - T[0, 3], pts[:, 1] - T[1, 3])
    near = pts[(d > 3) & (d < 10), 2]
    return float(np.percentile(near, 5)) if len(near) > 50 else T[2, 3] - 2.0


def car_box(T, fw, ground):
    """8 corners of the white box, centred under the lidar, sitting on the road."""
    lat = np.array([-fw[1], fw[0], 0.0])
    c = np.array([T[0, 3], T[1, 3], ground])
    corners = []
    for a in (-0.5, 0.5):
        for b in (-0.5, 0.5):
            for h in (0.0, CAR_H):
                corners.append(c + a * CAR_L * fw + b * CAR_W * lat + np.array([0, 0, h]))
    return np.array(corners)


# ---------- drawing one frame ----------
def draw_frame(ax, drive, i, look, W, H, label, show_label=True):
    pts, T = drive.scan_at(i)
    fw = T[:3, :3] @ np.array([1.0, 0, 0])       # lidar x axis = forward
    fw[2] = 0
    fw /= np.linalg.norm(fw)
    lat = np.array([-fw[1], fw[0], 0.0])
    ground = ground_height(pts, T)
    car = np.array([T[0, 3], T[1, 3], ground])
    C = car - look["back"] * fw + look["side"] * lat + np.array([0, 0, look["height"]])
    R = look_at(C, car + 5.0 * fw + np.array([0, 0, 0.6]))

    # points: colour by height above the road, nearer points drawn larger and on top
    rel = np.clip(pts[:, 2] - ground, -0.3, 4.5)
    x, y, z = project(pts, C, R, W, H, look["fov"])
    ok = (z > 0.8) & (x > -5) & (x < W + 5) & (y > -5) & (y < H + 5)
    order = np.argsort(-z[ok])
    xs, ys, zs, hs = x[ok][order], y[ok][order], z[ok][order], rel[ok][order]
    size = np.clip(look["pt"] * 18.0 / zs, 0.8, 9.0)
    ax.scatter(xs, ys, c=hs, cmap=look["cmap"], vmin=-0.3, vmax=4.5, s=size, linewidths=0, alpha=0.9, rasterized=True)

    # the car: three visible faces of a white box, slightly see-through so a small ring still shows
    B = car_box(T, fw, ground)
    bx, by, bz = project(B, C, R, W, H, look["fov"])
    idx = lambda a, b, h: (a * 4 + b * 2 + h)  # noqa: E731  (a: back/front, b: left/right, h: bottom/top)
    faces = [([idx(0, 0, 1), idx(1, 0, 1), idx(1, 1, 1), idx(0, 1, 1)], "#ffffff"),      # roof
             ([idx(0, 0, 0), idx(0, 1, 0), idx(0, 1, 1), idx(0, 0, 1)], "#d9d9d9"),      # back
             ([idx(0, 0, 0), idx(1, 0, 0), idx(1, 0, 1), idx(0, 0, 1)], "#bfbfbf"),      # left side
             ([idx(0, 1, 0), idx(1, 1, 0), idx(1, 1, 1), idx(0, 1, 1)], "#bfbfbf")]      # right side
    for f, c in faces:
        ax.fill(bx[f], by[f], color="#ffffff", alpha=0.12, zorder=4, lw=0)
    for a_, b_ in ((0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)):
        ax.plot([bx[a_], bx[b_]], [by[a_], by[b_]], color="white", lw=1.6, zorder=7)   # the 12 edges

    # ring on the road: the safety zone for the nearest test point, drawn over the car
    r, capped = drive.ring_at(car[:2])
    ang = np.linspace(0, 2 * np.pi, 240)
    ring = car + r * (np.cos(ang)[:, None] * fw + np.sin(ang)[:, None] * lat) + np.array([0, 0, 0.05])
    rx, ry, rz = project(ring, C, R, W, H, look["fov"])
    col = "#39FF14" if r >= 2.5 else ("#FFD700" if r >= 1.5 else "#FF3030")   # green = roomy, yellow = tight, red = small
    if look["ring"] == "disc":
        ax.fill(rx, ry, color=col, alpha=0.18, zorder=5)
        ax.plot(rx, ry, color=col, lw=2.5, zorder=6)
    elif look["ring"] == "glow":
        for lw, a in ((16, 0.10), (10, 0.2), (6, 0.4), (3, 1.0)):
            ax.plot(rx, ry, color=col, lw=lw, alpha=a, zorder=8, solid_capstyle="round")
        ax.fill(rx, ry, color=col, alpha=0.16, zorder=5)
    else:
        for lw, a in ((6, 0.25), (2, 1.0)):
            ax.plot(rx, ry, color=col, lw=lw, alpha=a, zorder=6)

    # ring size label next to the ring, and the clip name
    lab = ("3 m+" if capped else f"{r:g} m") + " wiggle room"   # plain words for "basin radius": how far off the guess can be
    lx, ly, _ = project(np.array([car - max(r + 0.5, CAR_L / 2 + 0.6) * fw + np.array([0, 0, 0.05])]), C, R, W, H, look["fov"])   # always past the back of the car
    ax.text(float(lx[0]), float(ly[0]), lab, color=col, fontsize=30, weight="bold", ha="center", va="top",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=5, foreground="black")], zorder=9)
    if show_label:
        ax.text(W / 2, 44, label, color="white", fontsize=30, weight="bold", ha="center", va="center",
                path_effects=[matplotlib.patheffects.withStroke(linewidth=6, foreground="black")], zorder=9)
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")


def new_canvas(W, H):
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="black")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("black")
    return fig, ax


def frame_plan(storm, control, start_s, seconds, fps, speed):
    """Which storm scan and which control scan to show at each video frame.
    Storm: real time x speed. Control: the scan taken closest to the storm car's position."""
    n = int(seconds * fps)
    t0 = storm.t[0] + start_s * 1e6
    plan = []
    for k in range(n):
        ts = t0 + k / fps * speed * 1e6
        i = int(np.argmin(np.abs(storm.t - ts)))
        _, j = control.tree.query(storm.xy[i])
        plan.append((i, int(j)))
    return plan


def main():
    import matplotlib.patheffects  # noqa: F401  (used above)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--look", default="C", choices=list(LOOKS))
    ap.add_argument("--width", type=int, default=540, help="one panel's width; two panels make 1080")
    ap.add_argument("--height", type=int, default=960)
    ap.add_argument("--start", type=float, default=32.0, help="storm scan-seconds where the clip starts")
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--speed", type=float, default=1.5, help="playback speed of the storm drive")
    ap.add_argument("--still", type=float, help="render one side-by-side still at this many storm scan-seconds")
    ap.add_argument("--frames-dir", help="write side-by-side frames here as frame_00000.png ...")
    ap.add_argument("--out", default="results/sketch.png")
    a = ap.parse_args()
    look = LOOKS[a.look]
    W, H = a.width, a.height
    storm, control = Drive(STORM, "results/basin_storm.csv"), Drive(CONTROL, "results/basin_control.csv")

    def side_by_side(i, j, path):
        fig = plt.figure(figsize=(2 * W / 100, H / 100), dpi=100, facecolor="black")
        for k, (d, idx, lab) in enumerate(((control, j, "No snow"), (storm, i, "Snowstorm"))):
            ax = fig.add_axes([0.503 * k, 0, 0.497, 1])     # 6 px black gutter between the two clips
            ax.set_facecolor("black")
            draw_frame(ax, d, idx, look, W, H, lab)
        fig.savefig(path, dpi=100, facecolor="black")
        plt.close(fig)

    if a.still is not None:
        ts = storm.t[0] + a.still * 1e6
        i = int(np.argmin(np.abs(storm.t - ts)))
        _, j = control.tree.query(storm.xy[i])
        side_by_side(i, int(j), a.out)
        print(f"wrote {a.out} (storm scan {i} at {a.still} s, control scan {j}; look {a.look})")
        return
    plan = frame_plan(storm, control, a.start, a.seconds, a.fps, a.speed)
    out = Path(a.frames_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for k, (i, j) in enumerate(plan):
        side_by_side(i, j, out / f"frame_{k:05d}.png")
        if k % 30 == 0:
            print(f"  frame {k}/{len(plan)} ({time.time() - t0:.0f} s)", flush=True)
    print(f"{len(plan)} frames in {out} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
