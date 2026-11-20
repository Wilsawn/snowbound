#!/usr/bin/env python3
"""Written with Claude (AI), Nov 20 2026. Step 2 first numbers. Not final project code.

What it does, in plain words:
  1. Build a small 3D map of the road from the MAP drive (Nov 26 2020), placing each map scan
     with its ground-truth pose. (Burnett et al. build their map from lidar only; ours uses
     ground-truth poses, so say "map built from ground-truth poses" when you report numbers.)
  2. Take a stretch of the TEST drive (storm, or a control day) and, for each test scan, start
     from a guess (ground truth, or ground truth pushed off by --offset metres / --yaw degrees).
  3. Run scan-to-map ICP (point-to-plane) to slide the scan onto the map.
  4. Compare where ICP ended up with ground truth: lateral (sideways), longitudinal (along the
     direction of travel), height and heading errors. Print RMSE and success rate.

Run (on the Mac, from ~/snowbound):
  uv run python scripts/score_60s.py --test boreas-2021-01-26-11-22 --seconds 60 --every 5
  uv run python scripts/score_60s.py --test boreas-2021-01-26-11-22 --offset 1 --yaw 5
  uv run python scripts/score_60s.py --test boreas-2021-01-26-11-22 --no-deskew   # compare without deskew
Known simplifications (be honest about these when reporting):
  - Deskew (motion compensation) uses ground-truth velocity and yaw rate, not odometry.
  - Map from ground-truth poses, not from lidar odometry.
  - Uses scipy for ICP so it runs anywhere; Open3D comes later.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402


# ---------- small geometry helpers ----------
def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def pose_matrix(row, origin):
    """4x4 pose of the lidar in a local east-north-up frame (metres, origin subtracted).
    Same rotation convention as Claude's Nov 19 exploration, which lined scans up to about 10 cm.
    test_heading_sign (Delo's test) should confirm this convention."""
    T = np.eye(4)
    T[:3, :3] = (rot_z(row.heading) @ rot_y(row.pitch) @ rot_x(row.roll)).T
    T[:3, 3] = np.array([row.easting, row.northing, row.altitude]) - origin
    return T


def voxel_downsample(points, size):
    """Keep one point per cube of side `size` metres."""
    keys = np.floor(points / size).astype(np.int64)
    _, idx = np.unique(keys, axis=0, return_index=True)
    return points[idx]


def keep_ring(points, near=3.0, far=60.0):
    """Drop points on the car itself (< 3 m) and very far points (> 60 m)."""
    r = np.linalg.norm(points[:, :2], axis=1)
    return points[(r > near) & (r < far)]


def deskew(raw, row, T):
    """Undo motion smear inside one 0.1 s sweep.
    Each point has its own time t (seconds from the scan time; checked: about -0.05..+0.05 s,
    so the scan time is the MIDDLE of the sweep). At ~10 m/s the car moves up to ~0.5 m during
    half a sweep, so without this the scan is stretched along the road.
    Constant velocity + constant yaw rate, from ground truth. Returns points in the lidar frame
    at the scan time."""
    xyz, t = raw[:, :3].astype(np.float64), raw[:, 5].astype(np.float64)
    v_world = np.array([row.vel_east, row.vel_north, row.vel_up])
    v_sensor = T[:3, :3].T @ v_world              # velocity seen from the lidar
    yaw = row.angvel_z * t                        # small rotation about the lidar's up axis
    c, s = np.cos(yaw), np.sin(yaw)
    x = c * xyz[:, 0] - s * xyz[:, 1]
    y = s * xyz[:, 0] + c * xyz[:, 1]
    return np.c_[x, y, xyz[:, 2]] + t[:, None] * v_sensor


def load_points(path, row, T, use_deskew):
    raw = loader.load_scan(path)
    return deskew(raw, row, T) if use_deskew else raw[:, :3].astype(np.float64)


# ---------- the map ----------
def build_map(test_xy, origin, use_deskew, radius=25.0, every=4, voxel=0.2):
    """Stack map-drive scans that pass within `radius` m of the test stretch."""
    poses = loader.load_poses(loader.MAP_DRIVE)
    files = loader.scan_files(loader.MAP_DRIVE)
    rows = [loader.nearest_pose(poses, loader.scan_time_us(f))[0] for f in files]
    xy = np.array([[r.easting - origin[0], r.northing - origin[1]] for r in rows])
    dist, _ = cKDTree(test_xy).query(xy)
    chosen = np.flatnonzero(dist < radius)[::every]
    chunks = []
    for j in chosen:
        T = pose_matrix(rows[j], origin)
        pts = keep_ring(load_points(files[j], rows[j], T, use_deskew))
        pts = voxel_downsample(pts, 0.3)
        chunks.append(pts @ T[:3, :3].T + T[:3, 3])
    if not chunks:
        raise SystemExit("the map drive never passes this stretch; try another --start")
    cloud = voxel_downsample(np.vstack(chunks), voxel)
    tree = cKDTree(cloud)
    # Surface normal at each map point = direction of least spread among its 10 neighbours.
    _, nn = tree.query(cloud, k=10)
    nb = cloud[nn] - cloud[nn].mean(axis=1, keepdims=True)
    _, vecs = np.linalg.eigh(np.einsum("nki,nkj->nij", nb, nb))
    return cloud, vecs[:, :, 0], tree, len(chosen)


# ---------- ICP ----------
def icp_point_to_plane(scan, T, cloud, normals, tree, iters=30, huber=0.1):
    """Slide `scan` (lidar frame) onto the map, starting from pose T. Returns (pose, ok).
    Small rotations are taken about the lidar's own position (not the map origin, which can be
    hundreds of metres away). Huber weights stop odd points (snowflakes, parked cars that moved)
    from pulling too hard: residuals above `huber` metres count less."""
    for n in range(iters):
        max_d = 2.0 if n < 10 else (1.0 if n < 20 else 0.5)  # match radius shrinks as it settles
        moved = scan @ T[:3, :3].T + T[:3, 3]
        d, j = tree.query(moved, distance_upper_bound=max_d)
        ok = np.isfinite(d)
        if ok.sum() < 50:
            return T, False
        p, q, nrm = moved[ok], cloud[j[ok]], normals[j[ok]]
        c = T[:3, 3]
        A = np.c_[np.cross(p - c, nrm), nrm]      # small-angle point-to-plane, about the lidar
        b = -np.einsum("ij,ij->i", p - q, nrm)
        k = max(huber, max_d / 2)                 # loose while far off, strict once settled
        w = np.sqrt(np.minimum(1.0, k / np.maximum(np.abs(b), 1e-9)))
        dx = np.linalg.lstsq(A * w[:, None], b * w, rcond=None)[0]
        T = T.copy()
        T[:3, :3] = rot_z(dx[2]) @ rot_y(dx[1]) @ rot_x(dx[0]) @ T[:3, :3]
        T[:3, 3] = c + dx[3:]
        if np.linalg.norm(dx) < 1e-5:
            break
    return T, True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", default=loader.SNOW_DRIVE, help="drive to localize (storm or control)")
    ap.add_argument("--start", type=float, default=0.0, help="seconds into the downloaded test scans")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--every", type=int, default=5, help="use every Nth test scan (10 Hz, so 5 = 2 per second)")
    ap.add_argument("--offset", type=float, default=0.0, help="push the start guess this many metres off")
    ap.add_argument("--yaw", type=float, default=0.0, help="and turn it this many degrees")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-deskew", action="store_true", help="skip motion compensation (to compare)")
    a = ap.parse_args()

    t0 = time.time()
    poses = loader.load_poses(a.test)
    files = loader.scan_files(a.test)
    if not files:
        raise SystemExit(f"no lidar scans for {a.test}; download a sample first")
    times = np.array([loader.scan_time_us(f) for f in files])
    window = np.flatnonzero((times >= times[0] + a.start * 1e6) & (times <= times[0] + (a.start + a.seconds) * 1e6))
    window = window[:: a.every]
    rows = [loader.nearest_pose(poses, int(times[k]))[0] for k in window]
    origin = np.array([rows[0].easting, rows[0].northing, rows[0].altitude])
    truth = [pose_matrix(r, origin) for r in rows]
    test_xy = np.array([T[:2, 3] for T in truth])

    use_deskew = not a.no_deskew
    cloud, normals, tree, n_map = build_map(test_xy, origin, use_deskew)
    print(f"map: {n_map} scans from {loader.MAP_DRIVE}, {len(cloud):,} points ({time.time() - t0:.0f} s)")

    rng = np.random.default_rng(a.seed)
    lat, lon, up, yaw_err, ok_all = [], [], [], [], []
    for k, row, Tg in zip(window, rows, truth):
        scan = voxel_downsample(keep_ring(load_points(files[k], row, Tg, use_deskew)), 0.5)
        T0 = Tg.copy()
        if a.offset:
            ang = rng.uniform(0, 2 * np.pi)
            T0[:2, 3] += a.offset * np.array([np.cos(ang), np.sin(ang)])
        if a.yaw:
            T0[:3, :3] = rot_z(np.radians(a.yaw) * rng.choice([-1, 1])) @ T0[:3, :3]
        T, ok = icp_point_to_plane(scan, T0, cloud, normals, tree)
        err = T[:3, 3] - Tg[:3, 3]
        # Split the sideways vs along-the-road error using the true direction of travel.
        v = np.array([row.vel_east, row.vel_north])
        fwd = v / np.linalg.norm(v) if np.linalg.norm(v) > 0.5 else np.array([1.0, 0.0])
        lon.append(float(err[:2] @ fwd))
        lat.append(float(err[:2] @ np.array([-fwd[1], fwd[0]])))
        up.append(float(err[2]))
        dyaw = np.degrees(np.arctan2(T[1, 0], T[0, 0]) - np.arctan2(Tg[1, 0], Tg[0, 0]))
        yaw_err.append(float((dyaw + 180) % 360 - 180))
        ok_all.append(ok)

    lat, lon, up, yaw_err = map(np.array, (lat, lon, up, yaw_err))
    recovered = (np.hypot(lat, lon) < 0.3) & (np.abs(yaw_err) < 2.0) & np.array(ok_all)
    rmse = lambda x: 100 * np.sqrt(np.mean(x ** 2))  # noqa: E731
    print(f"test: {a.test}, {len(window)} scans over {a.seconds:.0f} s, start off {a.offset} m / {a.yaw} deg, "
          f"deskew {'on' if use_deskew else 'off'}")
    # RMSE mixes a steady bias with scatter, so also show the mean (bias) and std (scatter).
    for name, x, unit, k in (("lateral", lat, "cm", 100), ("longitudinal", lon, "cm", 100),
                             ("height", up, "cm", 100), ("heading", yaw_err, "deg", 1)):
        r = np.sqrt(np.mean(x ** 2)) * k
        print(f"  {name:13s} RMSE {r:6.2f} {unit}   mean {np.mean(x) * k:+6.2f}   std {np.std(x) * k:5.2f}")
    print(f"  recovered (< 30 cm and < 2 deg): {100 * recovered.mean():.0f}%")
    print(f"  ({time.time() - t0:.0f} s total)")


if __name__ == "__main__":
    main()
