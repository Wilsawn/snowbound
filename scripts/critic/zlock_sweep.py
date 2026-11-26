"""Critic follow-up: redo the exact sweep (sweep_route.sweep_point, same seed per point) at storm spots 1,2,3,16,15
with the ICP height locked (z translation and roll/pitch not updated). If room for error comes back, the drop was
the matcher sliding vertically onto snow clutter. Run: cd ~/snowbound && nice -n 19 uv run python <this file>"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
R = Path.home() / "snowbound"
sys.path.insert(0, str(R / "src")); sys.path.insert(0, str(R / "scripts"))
from snowbound import loader
import score_60s
from score_60s import build_map, keep_ring, load_points, pose_matrix, rot_z, voxel_downsample
import sweep_route

def icp_zlock(scan, T, cloud, normals, tree, iters=30, huber=0.1, first_radius=2.0):
    for n in range(iters):
        max_d = first_radius if n < 10 else (1.0 if n < 20 else 0.5)
        moved = scan @ T[:3, :3].T + T[:3, 3]
        d, j = tree.query(moved, distance_upper_bound=max_d)
        ok = np.isfinite(d)
        if ok.sum() < 50:
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
    return T, True

sweep_route.icp_point_to_plane = icp_zlock          # sweep_point looks it up in its module globals
STORM, CONTROL = sweep_route.STORM, sweep_route.CONTROL
S = pd.read_csv(R / "results/route_storm.csv"); C = pd.read_csv(R / "results/route_control.csv")
P = {STORM: loader.load_poses(STORM), CONTROL: loader.load_poses(CONTROL)}
row = lambda d, t: loader.nearest_pose(P[d], int(t))[0]
out = []
for k, pairs in {0: ["000_000", "000_001", "000_002"], 1: ["001_002", "001_003"]}.items():
    pre = f"{k:03d}_"; s, c = S[S.pair.str.startswith(pre)], C[C.pair.str.startswith(pre)]
    rs = [row(STORM, t) for t in s.scan_time_us]; rc = [row(CONTROL, t) for t in c.scan_time_us]
    all_xy = np.array([[r.easting, r.northing] for pr in zip(rs, rc) for r in pr])
    origin = np.array([all_xy[0, 0], all_xy[0, 1], rs[0].altitude])
    cloud, normals, tree, _ = build_map(all_xy - origin[:2], origin, True, every=1)
    for pair in pairs:
        n = int(pair[4:]); t = int(s.set_index("pair").loc[pair, "scan_time_us"]); r = row(STORM, t)
        f = loader.drive_path(STORM) / "lidar" / f"{t}.bin"
        rng = np.random.default_rng(0 + 1000 * k + n)
        # sweep_route draws storm then ctrl from the same rng: storm comes first, so same draws
        basin, capped, per_size, yaw_ok = sweep_route.sweep_point(f, r, pose_matrix(r, origin), cloud, normals, tree, rng)
        res = dict(pair=pair, zlock_basin_m=basin, zlock_capped=int(capped), zlock_ok_per_size="|".join(map(str, per_size)),
                   orig_basin_m=float(s.set_index("pair").loc[pair, "basin_radius_m"]), orig_ok=s.set_index("pair").loc[pair, "ok_per_size"])
        print(res, flush=True); out.append(res)
pd.DataFrame(out).to_csv(Path(__file__).with_name("zlock_sweep.csv"), index=False)
