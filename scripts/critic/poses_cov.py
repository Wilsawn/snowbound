import sys; from pathlib import Path
import numpy as np, pandas as pd
R = Path.home()/"snowbound"; sys.path.insert(0, str(R/"src"))
from snowbound import loader
from scipy.spatial import cKDTree
STORM, CONTROL = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08"
p = loader.load_poses(STORM)
files = loader.scan_files(STORM); t0 = loader.scan_time_us(files[0]) / 1e6
print("first scan file t", t0, "first pose t", p.t_s.iloc[0], "n poses", len(p))
q = p[(p.t_s >= t0 - 1) & (p.t_s <= t0 + 20)].copy()
q["rel"] = q.t_s - t0
q["spd"] = np.hypot(q.vel_east, q.vel_north)
dt = q.t_s.diff(); step = np.hypot(q.easting.diff(), q.northing.diff())
q["step_minus_v_dt_cm"] = 100 * (step - q.spd * dt)
q["dhead_deg"] = np.degrees((q.heading.diff() + np.pi) % (2*np.pi) - np.pi)
q["dhead_minus_w_dt_deg"] = q.dhead_deg - np.degrees(q.angvel_z * dt)
q["dz_cm"] = 100*q.altitude.diff()
q["heading_deg"] = np.degrees(q.heading); q["track_deg"] = np.degrees(np.arctan2(q.vel_north, q.vel_east))
cols = ["rel","easting","northing","spd","heading_deg","track_deg","angvel_z","dt","step_minus_v_dt_cm","dhead_minus_w_dt_deg","dz_cm"]
q["dt"] = dt
print(q[cols].iloc[::5].round(3).to_string())
print("max |step-v*dt| cm", q.step_minus_v_dt_cm.abs().max().round(2), "max |dhead-w*dt| deg", q.dhead_minus_w_dt_deg.abs().max().round(3), "max dt", q.dt.max())
# map coverage: map-drive scans (files on disk) within 20 m of each spot, storm and control positions
mp = loader.load_poses(loader.MAP_DRIVE); mf = loader.scan_files(loader.MAP_DRIVE)
mxy = np.array([[r.easting, r.northing] for r in (loader.nearest_pose(mp, loader.scan_time_us(f))[0] for f in mf)])
tree = cKDTree(mxy)
S = pd.read_csv(R/"results/route_storm.csv"); C = pd.read_csv(R/"results/route_control.csv")
S["map_scans_20m"] = [len(x) for x in tree.query_ball_point(S[["east","north"]].to_numpy(), 20)]
C["map_scans_20m"] = [len(x) for x in tree.query_ball_point(C[["east","north"]].to_numpy(), 20)]
print("map scans on disk", len(mf), "; median map scans within 20 m of storm spot over all", len(S), ":", S.map_scans_20m.median(), " control:", C.map_scans_20m.median())
for i in [0,1,2,3,14,15]:
    print(f"spot {i+1} {S.pair[i]} storm map_scans_20m {S.map_scans_20m[i]}  ctrl {C.map_scans_20m[i]}")
print("percentile of 11 among storm spots", (S.map_scans_20m < 11).mean())
S[["pair","map_scans_20m"]].assign(ctrl=C.map_scans_20m).to_csv(Path(__file__).with_name("map_cov.csv"), index=False)
print(S.map_scans_20m.describe())
