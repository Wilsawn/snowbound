"""Open one laser scan in the Rerun 3D viewer, with the 'snow' dots painted red.
Snow dots = lonely (fewer than 3 neighbours) AND dim (brightness < 2), 2.5 to 20 m from the car.
Same test as the Colab snow meter v2.
Run:  .venv/bin/python view_scan.py              (middle snow scan downloaded so far)
      .venv/bin/python view_scan.py --drive map  (the sunny day, same street)
      .venv/bin/python view_scan.py --index 0    (pick another scan)"""
import argparse, glob, os, sys
import numpy as np
from scipy.spatial import cKDTree
import rerun as rr

DATA = os.path.expanduser("~/snowbound-data")
DRIVES = {"snow": "boreas-2021-01-26-11-22", "map": "boreas-2020-11-26-13-58"}
ap = argparse.ArgumentParser()
ap.add_argument("--drive", choices=DRIVES, default="snow")
ap.add_argument("--index", type=int, default=None)
a = ap.parse_args()

scans = sorted(glob.glob(os.path.join(DATA, DRIVES[a.drive], "lidar", "*.bin")))
if not scans:
    raise SystemExit("No scans downloaded yet for this drive. Let the download run first.")
path = scans[len(scans) // 2 if a.index is None else a.index]
pts = np.fromfile(path, dtype=np.float32).reshape(-1, 6)
xyz, inten = pts[:, :3].astype(np.float64), pts[:, 3]
r = np.linalg.norm(xyz[:, :2], axis=1)
near = (r > 2.5) & (r < 20)
snow = np.zeros(len(xyz), bool)
idx = np.flatnonzero(near)
counts = cKDTree(xyz[idx]).query_ball_point(xyz[idx], np.maximum(0.10, 0.02 * r[idx]), return_length=True) - 1
snow[idx[(counts < 3) & (inten[idx] < 2)]] = True

colors = np.tile(np.array([[150, 150, 150]], np.uint8), (len(xyz), 1))
colors[snow] = [230, 60, 30]
print(f"{a.drive} scan {os.path.basename(path)}: {len(xyz)} dots, {snow.sum()} snow dots (red)")
# the viewer app lives next to this Python (in .venv/bin); make sure it can be found
os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")
rr.init("snowbound_scan", spawn=True)
rr.log("scan/everything", rr.Points3D(xyz[~snow], colors=colors[~snow], radii=0.03))
rr.log("scan/snow", rr.Points3D(xyz[snow], colors=colors[snow], radii=0.06))
rr.log("car", rr.Points3D([[0, 0, 0]], colors=[[30, 120, 230]], radii=0.5))
