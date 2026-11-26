#!/usr/bin/env python3
"""Build the data files and small images for the website in docs/.

Plain words:
  - Reads the paired test points (results/route_pairs.csv if it exists, else results/basin_pairs.csv
    from the first 460 m study) and writes docs/data/route.json: for every spot its latitude and
    longitude, the room for error on both days ("3 m+" when capped), and the names of its images.
  - Latitude and longitude come from the map drive's applanix/gps_post_process.csv (Boreas gives
    them in radians next to the same easting/northing). The local frame is a flat tangent plane, so
    one affine fit maps east/north to lat/lon with a residual under 1 cm; nothing is guessed.
  - For every spot, two dashcam crops (storm and no snow) from each drive's video.mp4 (frame =
    camera pose row nearest the scan time) and two small top-down lidar snapshots (the real scan,
    nothing filtered but the car's own body), 480 px wide JPEGs.
  - Also the route line (storm poses) as lat/lon, thinned, and the two scans for the 3D viewer
    (same spot on both days, see export_scans).

Run: uv run python scripts/build_site.py
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402
from score_60s import pose_matrix, load_points  # noqa: E402

STORM, CONTROL, MAP = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08", "boreas-2020-11-26-13-58"
DOCS = Path("docs")


def latlon_fit():
    g = pd.read_csv(loader.drive_path(MAP) / "applanix" / "gps_post_process.csv",
                    usecols=["easting", "northing", "latitude", "longitude"]).dropna()
    A = np.c_[g.easting, g.northing, np.ones(len(g))]
    cl = np.linalg.lstsq(A, np.degrees(g.latitude), rcond=None)[0]
    cn = np.linalg.lstsq(A, np.degrees(g.longitude), rcond=None)[0]
    res = np.abs(A @ cl - np.degrees(g.latitude)).max() * 111320
    return cl, cn, float(res)


def to_latlon(cl, cn, e, n):
    return float(cl[0] * e + cl[1] * n + cl[2]), float(cn[0] * e + cn[1] * n + cn[2])


class Drive:
    def __init__(self, name):
        self.name = name
        self.poses = loader.load_poses(name)
        self.files = loader.scan_files(name)
        self.t = np.array([loader.scan_time_us(f) for f in self.files])
        self.rows = [loader.nearest_pose(self.poses, int(x))[0] for x in self.t]
        self.xy = np.array([[r.easting, r.northing] for r in self.rows])
        self.tree = cKDTree(self.xy)
        cam = loader.drive_path(name) / "applanix" / "camera_poses.csv"
        self.cam_t = pd.read_csv(cam).GPSTime.to_numpy() if cam.exists() else None
        self.video = loader.drive_path(name) / "video.mp4"

    def nearest_scan(self, e, n):
        d, i = self.tree.query([e, n])
        return int(i), float(d)

    def dashcam(self, i, out):
        """One video frame, cropped to drop the hood, 480 px wide."""
        if out.exists() or self.cam_t is None or not self.video.exists():
            return out.exists()
        k = int(np.argmin(np.abs(self.cam_t - self.t[i])))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{k / 30:.3f}", "-i", str(self.video),
                        "-vf", "crop=2160:1560:144:0,scale=480:347", "-frames:v", "1", "-q:v", "5", str(out)], check=True)
        return True

    def dashcam_big(self, i, out, width=1600):
        """One full video frame (hood cropped), wide, for the full-screen hero."""
        if out.exists() or self.cam_t is None or not self.video.exists():
            return out.exists()
        k = int(np.argmin(np.abs(self.cam_t - self.t[i])))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{k / 30:.3f}", "-i", str(self.video),
                        "-vf", f"crop=2448:1540:0:0,scale={width}:-2", "-frames:v", "1", "-q:v", "4", str(out)], check=True)
        return True

    def lidar_snapshot(self, i, out, half=16.0, px=400):
        """Top-down view of the real scan, the car at the centre heading up. Drawn at 2x and averaged
        down, so dense areas (walls, parked cars, a cloud of snow) read as brighter, not as a solid blob."""
        if out.exists():
            return
        row = self.rows[i]
        T = pose_matrix(row, np.zeros(3))
        p = load_points(self.files[i], row, T, True)
        p = p[np.hypot(p[:, 0], p[:, 1]) > 3.0]
        h = np.arctan2(row.vel_north, row.vel_east)
        w = p @ T[:3, :3].T                                   # world orientation, car at origin
        c, s = np.cos(np.pi / 2 - h), np.sin(np.pi / 2 - h)
        x, y = c * w[:, 0] - s * w[:, 1], s * w[:, 0] + c * w[:, 1]
        n = px * 2
        ok = (np.abs(x) < half) & (np.abs(y) < half)
        xi = ((x[ok] + half) / (2 * half) * (n - 1)).astype(int)
        yi = ((half - y[ok]) / (2 * half) * (n - 1)).astype(int)
        z = w[ok, 2] - np.percentile(w[ok, 2], 5)
        above = z > 0.25
        img = np.zeros((n, n, 3), np.float32)
        road = np.array([0.33, 0.52, 0.72], np.float32)
        white = np.array([0.90, 0.94, 0.98], np.float32)
        img[yi[~above], xi[~above]] = road * 0.8
        img[yi[above], xi[above]] = white
        img = img.reshape(px, 2, px, 2, 3).mean(axis=(1, 3))     # average 2x2 blocks: a half-filled block is half as bright
        img = np.clip(img * 1.4, 0, 1)
        im = Image.fromarray((img * 255).astype(np.uint8))
        im.save(out, quality=72)


def export_scans(storm, clear, spot_east, spot_north, n_keep=200000, stack=5):
    """The 3D viewer's two clouds, at the SAME spot: the no-snow scan nearest the spot and the storm scan
    nearest that scan's position, each stacked with its neighbours (stack scans, 0.1 s apart on these
    streets, so about 0.5 s of driving) placed with the recorded poses and expressed in the centre scan's
    lidar frame (x forward, y left, z up). Nothing removed but the car's own body (within 3 m) and points
    beyond 60 m, then thinned at random to n_keep points. Written as int16 xyz in centimetres (6 bytes),
    a brightness byte (how far the point is, 255 near) and a snow byte (1 = a lonely point above the road,
    the page paints those ice blue), 8 bytes a point, so the page does no per-point work."""
    ci, _ = clear.nearest_scan(spot_east, spot_north)
    si, gap = storm.nearest_scan(*clear.xy[ci])
    out = {}
    for name, d, i in (("storm", storm, si), ("clear", clear, ci)):
        Tc = pose_matrix(d.rows[i], np.zeros(3))
        chunks = []
        for j in range(i - stack // 2, i + stack // 2 + 1):
            if j < 0 or j >= len(d.files) or abs(int(d.t[j]) - int(d.t[i])) > 1.0e6:
                continue
            Tj = pose_matrix(d.rows[j], np.zeros(3))
            p = load_points(d.files[j], d.rows[j], Tj, True)
            pw = p @ Tj[:3, :3].T + Tj[:3, 3]
            pc = (pw - Tc[:3, 3]) @ Tc[:3, :3]
            r = np.hypot(pc[:, 0], pc[:, 1])
            chunks.append(pc[(r > 3) & (r < 60)])
        p = np.vstack(chunks)
        rng = np.random.default_rng(0)
        q = p[rng.choice(len(p), size=min(n_keep, len(p)), replace=False)]
        ground = np.percentile(q[:, 2], 5)
        z = q[:, 2] - ground
        # lonely points above the road (at most 2 points in a 0.6 m cell) are snow in the air
        cell = np.floor(q / 0.6).astype(np.int64)
        keys = cell[:, 0] * 1_000_003 + cell[:, 1] * 1_009 + cell[:, 2]
        _, inv, counts = np.unique(keys, return_inverse=True, return_counts=True)
        snow = ((z > 0.4) & (counts[inv] <= 2)).astype(np.uint8)
        dist = np.hypot(q[:, 0], q[:, 1])
        bright = ((0.18 + 0.82 * np.exp(-dist / 45)) * np.where(z > 0.25, 1.0, 0.6) * 255).astype(np.uint8)
        xyz = np.c_[q[:, 0], q[:, 1], z]
        rec = np.zeros(len(q), dtype=[("xyz", "<i2", 3), ("b", "u1"), ("s", "u1")])
        rec["xyz"] = np.clip(np.round(xyz * 100), -32000, 32000).astype(np.int16)
        rec["b"] = bright
        rec["s"] = snow
        rec.tofile(DOCS / "data" / f"scan_{name}.bin")
        out[name] = dict(file=f"data/scan_{name}.bin", points=int(len(q)), of=int(len(p)), scans=len(chunks), scan_time_us=int(d.t[i]),
                         layout="int16 x y z (cm, z above the road), uint8 brightness, uint8 snow", snow_points=int(snow.sum()),
                         east=round(float(d.xy[i, 0]), 2), north=round(float(d.xy[i, 1]), 2))
    out["gap_between_scans_m"] = round(float(gap), 2)
    json.dump(out, open(DOCS / "data" / "scans.json", "w"), indent=1)
    print(f"3D clouds: storm {out['storm']['points']} of {out['storm']['of']} points from {out['storm']['scans']} scans "
          f"({out['storm']['snow_points']} snow), clear {out['clear']['points']} of {out['clear']['of']} from {out['clear']['scans']}, {gap:.1f} m apart")


def export_street(pairs, voxel=0.35, n_keep=220000):
    """The street itself for the 3D hero: map-drive scans within 25 m of the test spots, placed with
    their recorded poses, deskewed, thinned to one point per voxel then at random to n_keep, in a
    local frame whose origin is the first test spot (x east, y north, z up). float32 xyz."""
    xy = pairs[["east", "north"]].to_numpy()
    origin = np.array([xy[0, 0], xy[0, 1], 0.0])
    poses = loader.load_poses(MAP)
    files = loader.scan_files(MAP)
    rows = [loader.nearest_pose(poses, loader.scan_time_us(f))[0] for f in files]
    mxy = np.array([[r.easting, r.northing] for r in rows])
    d, _ = cKDTree(xy).query(mxy)
    chosen = np.flatnonzero(d < 25.0)
    origin[2] = rows[chosen[0]].altitude
    chunks = []
    for j in chosen:
        T = pose_matrix(rows[j], origin)
        pts = load_points(files[j], rows[j], T, True)
        r = np.hypot(pts[:, 0], pts[:, 1])
        pts = pts[(r > 3) & (r < 45)]
        chunks.append(pts @ T[:3, :3].T + T[:3, 3])
    cloud = np.vstack(chunks)
    keys = np.floor(cloud / voxel).astype(np.int64)
    _, idx = np.unique(keys, axis=0, return_index=True)
    cloud = cloud[idx]
    rng = np.random.default_rng(0)
    if len(cloud) > n_keep:
        cloud = cloud[rng.choice(len(cloud), size=n_keep, replace=False)]
    cloud.astype(np.float32).tofile(DOCS / "data" / "street.bin")
    spots = [[round(float(e - origin[0]), 2), round(float(n - origin[1]), 2)] for e, n in xy]
    json.dump(dict(file="data/street.bin", points=int(len(cloud)), map_scans=int(len(chosen)), voxel_m=voxel,
                   origin_east=float(origin[0]), origin_north=float(origin[1]), origin_alt=float(origin[2]),
                   spots_xy=spots), open(DOCS / "data" / "street.json", "w"))
    print(f"street cloud: {len(cloud)} points from {len(chosen)} map scans")


def export_car(kind="suv"):
    """The clip's car (scripts/car_mesh.py, same body as the part 2 render) as triangles for the page's
    3D hero: float32 positions (N x 9), float32 normals (N x 9), uint8 material (0 paint, 1 glass,
    2 rubber), car frame (x forward, y left, z up, metres)."""
    from car_mesh import car_mesh
    tris, nrm, mat = car_mesh(kind)
    n = len(tris)
    with open(DOCS / "data" / "car.bin", "wb") as f:
        f.write(tris.astype(np.float32).tobytes())
        f.write(np.repeat(nrm, 3, axis=0).astype(np.float32).tobytes())
        f.write(mat.astype(np.uint8).tobytes())
    json.dump(dict(file="data/car.bin", triangles=int(n), body=kind, layout="pos f32 n*9, nrm f32 n*9, mat u8 n"),
              open(DOCS / "data" / "car.json", "w"))
    print(f"car: {n} triangles")


def hero_spot(pairs):
    """The spot the story is told at. Rule: no-snow room at the cap (3 m+), storm room above 0 (0 m on both
    days is the method failing, not snow), and, so the number is one we measured twice, a spot on the first
    study's street where that study (results/basin_pairs.csv) agrees within 0.5 m. Smallest storm room wins;
    ties go to the closest pair."""
    ok = pairs[(pairs.control_capped == 1) & (pairs.storm_basin_m > 0)].copy()
    first = Path("results/basin_pairs.csv")
    if first.exists() and "pair" in pairs and not str(pairs["pair"].iloc[0]).startswith("b_"):
        b = pd.read_csv(first)
        d, j = cKDTree(b[["east", "north"]].to_numpy()).query(ok[["east", "north"]].to_numpy())
        agree = (d <= 5.0) & (np.abs(b.basin_radius_m.to_numpy()[j] - ok.storm_basin_m.to_numpy()) <= 0.5)
        if agree.any():
            ok = ok[agree]
    return ok.sort_values(["storm_basin_m", "gap_m"]).iloc[0]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--street", action="store_true", help="also export the street cloud (slow, unused by the page)")
    ap.add_argument("--suffix", default="", help="read results/route_pairs<suffix>.csv, route_storm<suffix>.csv, route_control<suffix>.csv (e.g. _zlock for the height-locked rerun)")
    a = ap.parse_args()
    cl, cn, res = latlon_fit()
    print(f"lat/lon fit residual {res:.3f} m")
    storm, clear = Drive(STORM), Drive(CONTROL)
    src = Path(f"results/route_pairs{a.suffix}.csv") if Path(f"results/route_pairs{a.suffix}.csv").exists() else Path("results/basin_pairs.csv")
    pairs = pd.read_csv(src)
    if src.name == "basin_pairs.csv":   # the first study's columns
        pairs = pairs.rename(columns={"basin_radius_m": "storm_basin_m", "capped": "storm_capped"})
        pairs["pair"] = [f"b_{i:03d}" for i in range(len(pairs))]
    print(f"{len(pairs)} paired spots from {src}")
    per_size = {}
    for day, f in (("storm", f"results/route_storm{a.suffix}.csv"), ("clear", f"results/route_control{a.suffix}.csv")):
        if Path(f).exists():
            t = pd.read_csv(f)
            per_size[day] = dict(zip(t["pair"].astype(str), t["ok_per_size"].astype(str)))
    (DOCS / "media" / "spots").mkdir(parents=True, exist_ok=True)
    spots = []
    for _, r in pairs.iterrows():
        pid = str(r["pair"])
        lat, lon = to_latlon(cl, cn, r.east, r.north)
        si, _ = storm.nearest_scan(r.east, r.north)
        ci, cgap = clear.nearest_scan(r.east, r.north)
        files = {}
        for day, d, i in (("storm", storm, si), ("clear", clear, ci)):
            cam = DOCS / "media" / "spots" / f"{pid}_{day}_cam.jpg"
            lid = DOCS / "media" / "spots" / f"{pid}_{day}_lidar.jpg"
            if d.dashcam(i, cam):
                files[f"{day}_cam"] = f"media/spots/{cam.name}"
            d.lidar_snapshot(i, lid)
            files[f"{day}_lidar"] = f"media/spots/{lid.name}"
        for key in list(files):                                  # WebP copies (about half the bytes); the page loads these
            jpg = DOCS / files[key]
            webp = jpg.with_suffix(".webp")
            if not webp.exists():
                Image.open(jpg).save(webp, "WEBP", quality=74, method=4)
            files[key] = files[key][:-4] + ".webp"
        ok = {f"{day}_ok": [int(x) for x in per_size[day][pid].split("|")] for day in per_size if pid in per_size[day]}
        spots.append(dict(id=pid, lat=round(lat, 7), lon=round(lon, 7),
                          storm_m=float(r.storm_basin_m), storm_capped=bool(r.storm_capped),
                          clear_m=float(r.control_basin_m), clear_capped=bool(r.control_capped),
                          gap_m=round(float(r.gap_m), 1), **files, **ok))
    # route line: storm poses, thinned to one every 2 s, only the part the spots cover (plus a margin)
    sp = storm.poses
    line = [to_latlon(cl, cn, e, n) for e, n in zip(sp.easting.to_numpy()[::20], sp.northing.to_numpy()[::20])]
    out = dict(source=str(src), n=len(spots), latlon_fit_residual_m=round(res, 3), sizes_m=[0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3],
               storm_median_m=float(pairs.storm_basin_m.median()), clear_median_m=float(pairs.control_basin_m.median()),
               storm_capped=int(pairs.storm_capped.sum()), clear_capped=int(pairs.control_capped.sum()),
               storm_smaller=int((pairs.storm_basin_m < pairs.control_basin_m).sum()),
               storm_same=int((pairs.storm_basin_m == pairs.control_basin_m).sum()),
               storm_bigger=int((pairs.storm_basin_m > pairs.control_basin_m).sum()),
               both_capped=int(((pairs.storm_capped == 1) & (pairs.control_capped == 1)).sum()),
               storm_zero=int((pairs.storm_basin_m == 0).sum()), clear_zero=int((pairs.control_basin_m == 0).sum()),
               diff_median_m=float((pairs.storm_basin_m - pairs.control_basin_m).median()),
               route=[[round(a, 6), round(b, 6)] for a, b in line], spots=spots)
    (DOCS / "data").mkdir(exist_ok=True)
    # the 3D viewer's two scans and the full-screen dashcam: at the hero spot
    hero = hero_spot(pairs)
    export_scans(storm, clear, hero.east, hero.north)
    si, _ = storm.nearest_scan(hero.east, hero.north)
    storm.dashcam_big(si, DOCS / "media" / "hero_cam.jpg")
    out["hero"] = dict(id=str(hero["pair"]), storm_m=float(hero.storm_basin_m), clear_m=float(hero.control_basin_m),
                       clear_capped=bool(hero.control_capped), cam="media/hero_cam.jpg")
    json.dump(out, open(DOCS / "data" / "route.json", "w"), separators=(",", ":"))
    print(f"hero spot {hero['pair']}: storm {hero.storm_basin_m} m, no snow {hero.control_basin_m} m (capped {hero.control_capped})")
    export_car()
    if a.street:
        export_street(pairs)
    size = sum(f.stat().st_size for f in (DOCS / "media" / "spots").glob("*")) / 1e6
    print(f"wrote docs/data/route.json ({len(spots)} spots), spot images {size:.1f} MB")


if __name__ == "__main__":
    main()
