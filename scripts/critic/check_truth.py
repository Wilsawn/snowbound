"""Critic check: run the route matcher from the recorded TRUE pose (no push) at spots 1-4, 15, 16.
Rebuilds the chunk 0 and chunk 1 maps exactly as scripts/sweep_route.py run_chunk does
(all chunk points storm+ctrl, origin = chunk's first storm pose, build_map every=1, deskew on).
Run: cd ~/snowbound && nice -n 19 uv run python <this file>"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
R = Path.home() / "snowbound"
sys.path.insert(0, str(R / "src")); sys.path.insert(0, str(R / "scripts"))
from snowbound import loader
from score_60s import build_map, icp_point_to_plane, keep_ring, load_points, pose_matrix, rot_z, voxel_downsample
from scipy.spatial import cKDTree
STORM, CONTROL = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08"
WINDOW = 3.5
S = pd.read_csv(R / "results/route_storm.csv"); C = pd.read_csv(R / "results/route_control.csv")
P = {STORM: loader.load_poses(STORM), CONTROL: loader.load_poses(CONTROL)}
def row_file(drive, t):
    return loader.nearest_pose(P[drive], int(t))[0], loader.drive_path(drive) / "lidar" / f"{int(t)}.bin"
def yaw(T): return np.degrees(np.arctan2(T[1, 0], T[0, 0]))
def resid(scan, T, cloud, normals, tree):
    m = scan @ T[:3, :3].T + T[:3, 3]
    d, j = tree.query(m, distance_upper_bound=0.5)
    ok = np.isfinite(d)
    r = np.abs(np.einsum("ij,ij->i", m[ok] - cloud[j[ok]], normals[j[ok]]))
    return ok.mean(), float(np.median(r)) if ok.any() else np.nan
targets = {0: [("storm", "000_000"), ("storm", "000_001"), ("storm", "000_002"), ("storm", "000_003"),
               ("ctrl", "000_001"), ("ctrl", "000_002")],
           1: [("storm", "001_002"), ("storm", "001_003"), ("ctrl", "001_002"), ("ctrl", "001_003")]}
out = []
for k, todo in targets.items():
    pre = f"{k:03d}_"
    s, c = S[S.pair.str.startswith(pre)], C[C.pair.str.startswith(pre)]
    rows_s = [row_file(STORM, t)[0] for t in s.scan_time_us]
    rows_c = [row_file(CONTROL, t)[0] for t in c.scan_time_us]
    all_xy = np.array([[r.easting, r.northing] for pair in zip(rows_s, rows_c) for r in pair])
    origin = np.array([all_xy[0, 0], all_xy[0, 1], rows_s[0].altitude])
    cloud, normals, tree, n_map = build_map(all_xy - origin[:2], origin, True, every=1)
    print(f"chunk {k}: {n_map} map scans, {len(cloud)} map points", flush=True)
    for day, pair in todo:
        df, drive = (S, STORM) if day == "storm" else (C, CONTROL)
        t = int(df.set_index("pair").loc[pair, "scan_time_us"])
        row, f = row_file(drive, t)
        Tg = pose_matrix(row, origin)
        scan = voxel_downsample(keep_ring(load_points(f, row, Tg, True)), 0.5)
        n_map20 = len(tree.query_ball_point(Tg[:3, 3], 20.0))
        fr0, r0 = resid(scan, Tg, cloud, normals, tree)
        res = dict(pair=pair, day=day, scan_pts=len(scan), map_pts_20m=n_map20, inlier_at_truth=round(fr0, 3), medres_truth_cm=round(100 * r0, 1))
        for name, dyaw in (("push0", 0.0), ("yaw+5", 5.0), ("yaw-5", -5.0)):
            T0 = Tg.copy(); T0[:3, :3] = rot_z(np.radians(dyaw)) @ T0[:3, :3]
            T, ok = icp_point_to_plane(scan, T0, cloud, normals, tree, first_radius=WINDOW)
            dxy = np.hypot(*(T[:2, 3] - Tg[:2, 3])); dz = T[2, 3] - Tg[2, 3]
            dy = (yaw(T) - yaw(Tg) + 180) % 360 - 180
            fr, r = resid(scan, T, cloud, normals, tree)
            res[f"{name}_move_m"] = round(dxy, 3); res[f"{name}_dyaw_deg"] = round(dy, 2)
            if name == "push0":
                res["push0_dz_m"] = round(dz, 3); res["push0_inlier"] = round(fr, 3); res["push0_medres_cm"] = round(100 * r, 1)
                # direction of the move relative to travel
                h = np.arctan2(row.vel_north, row.vel_east); d = T[:2, 3] - Tg[:2, 3]
                res["push0_along_m"] = round(d @ [np.cos(h), np.sin(h)], 3); res["push0_side_m"] = round(d @ [-np.sin(h), np.cos(h)], 3)
        print(res, flush=True); out.append(res)
pd.DataFrame(out).to_csv(Path(__file__).with_name("truth_icp.csv"), index=False)
