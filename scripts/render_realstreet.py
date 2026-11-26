#!/usr/bin/env python3
"""Part 2 reel: "real street + what the lidar sees".

Plain words:
  - Top half of a vertical frame: the car's real front camera at that moment (from the drive's
    video.mp4, which holds every 10 Hz camera frame, one per row of applanix/camera_poses.csv).
  - Bottom half: the lidar scan taken at the same moment, seen from a camera that floats behind
    and above the car. Points are small crisp squares in two calm colours: the road in ice blue,
    everything above the road (walls, cars, poles, falling snow) in white. Far points fade into
    the dark, near points stay bright. Nothing is filtered except the car's own body (within 3 m).
  - The car is a simple shaded car shape from scripts/car_mesh.py, with a soft contact shadow.
  - The float camera glides: the car's position and heading are interpolated at 30 fps between
    the 10 Hz poses (heading smoothed over 1.5 s), so only the point cloud refreshes at 10 Hz.
    One slow push-in runs across the whole 12 s, so the hard cut feels like the same shot.
  - A thin ring on the road at the basin radius of the nearest test point (results/basin_*.csv),
    eased between test points, drawn under the car. The label holds one value per half.
  - First the snowstorm (Jan 26 2021), then a hard cut to the no-snow day (Jan 19 2021), both
    starting at the same spot on the road, each in real time. The no-snow camera needs that
    drive's video.mp4 and camera_poses.csv (scripts/fetch_control_camera.py); until they exist
    its top half says so.

Frames are written at 2160x3840 (two halves of 2160x1920). ffmpeg makes the mp4 and a 1080x1920 copy.

Run:
  uv run python scripts/render_realstreet.py --look D2 --still 38 --out results/sketch.png
  uv run python scripts/render_realstreet.py --look D2 --frames-dir /tmp/rs_frames
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from snowbound import loader  # noqa: E402
from score_60s import pose_matrix, load_points  # noqa: E402
from plot_basin_map import read_sweep  # noqa: E402
from car_mesh import draw_car  # noqa: E402

STORM, CONTROL = "boreas-2021-01-26-11-22", "boreas-2021-01-19-15-08"
W, H = 2160, 1920            # one half
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"   # index 10 = Medium, 0 = Regular
ROAD_RGB = (120, 170, 220)

# cam = (height above the road, metres behind the car, metres to the side). dolly = where the camera ends.
LOOKS = {
    "D": dict(cam=(12.5, 17.5, 0.0), dolly=(11.2, 15.6, 0.4), aim=7.0, fov=50, road="#6fa8d6", above="#e6f0f8",
              fade=55.0, px=2, ring=True, car="suv", paint=(226, 229, 233)),
}
LOOKS["D1"] = dict(LOOKS["D"], car="sedan", paint=(236, 238, 240))
LOOKS["D2"] = dict(LOOKS["D"], car="suv", paint=(168, 176, 186))   # never brighter than the lidar white   # the lead's pick: SUV body, mid-grey paint
LOOKS["D3"] = dict(LOOKS["D"], car="hatch", paint=(200, 206, 214))


# ---------- data ----------
class Drive:
    def __init__(self, name, basin_csv):
        self.name = name
        self.dir = loader.drive_path(name)
        self.poses = loader.load_poses(name)
        self.files = loader.scan_files(name)
        self.t = np.array([loader.scan_time_us(f) for f in self.files])
        self.rows = [loader.nearest_pose(self.poses, int(x))[0] for x in self.t]
        self.xyz = np.array([[r.easting, r.northing, r.altitude] for r in self.rows])
        self.tree = cKDTree(self.xyz[:, :2])
        # heading of travel, smoothed with a 15-scan (1.5 s) Hann window so the float camera turns in one smooth curve
        v = np.array([[r.vel_east, r.vel_north] for r in self.rows])
        k = np.hanning(17)[1:-1]
        k /= k.sum()
        vs = np.c_[np.convolve(v[:, 0], k, "same"), np.convolve(v[:, 1], k, "same")]
        self.fwd = vs / np.maximum(np.linalg.norm(vs, axis=1, keepdims=True), 1e-6)
        slow = np.linalg.norm(vs, axis=1) < 0.5                   # at a standstill the velocity is noise: hold the last heading
        for i in np.flatnonzero(slow):
            if i > 0:
                self.fwd[i] = self.fwd[i - 1]
        cam_csv = self.dir / "applanix" / "camera_poses.csv"
        self.cam_t = pd.read_csv(cam_csv).GPSTime.to_numpy() if cam_csv.exists() else None
        self.video = self.dir / "video.mp4"
        if "east" in pd.read_csv(basin_csv, nrows=1).columns:     # a whole-route CSV (results/route_*.csv) already holds world east/north
            b = pd.read_csv(basin_csv)
        else:
            b, _ = read_sweep(basin_csv, name)
        self.pts_tree = cKDTree(b[["east", "north"]].to_numpy())
        self.basin = b.basin_radius_m.to_numpy()
        self.capped = b.capped.astype(bool).to_numpy()
        self._mount = None

    def scan(self, i):
        T = pose_matrix(self.rows[i], np.zeros(3))
        p = load_points(self.files[i], self.rows[i], T, True)
        p = p[np.hypot(p[:, 0], p[:, 1]) > 3.0]        # the car's own body
        return p @ T[:3, :3].T + T[:3, 3], T

    def mount_height(self, i0, i1):
        """How high the lidar sits above the road, measured once from a few scans of the clip
        (5th percentile of point heights 3 to 10 m from the car). Used so the ground never bobs."""
        if self._mount is None:
            hs = []
            for i in np.linspace(i0, i1, 8).astype(int):
                pts, T = self.scan(i)
                d = np.hypot(pts[:, 0] - T[0, 3], pts[:, 1] - T[1, 3])
                near = pts[(d > 3) & (d < 10), 2]
                if len(near) > 50:
                    hs.append(T[2, 3] - np.percentile(near, 5))
            self._mount = float(np.median(hs)) if hs else 2.0
        return self._mount

    def pose_at(self, t_us):
        """Car position (on the road) and heading at any time, interpolated between the 10 Hz poses."""
        x = np.interp(t_us, self.t, self.xyz[:, 0])
        y = np.interp(t_us, self.t, self.xyz[:, 1])
        z = np.interp(t_us, self.t, self.xyz[:, 2]) - self._mount
        fx = np.interp(t_us, self.t, self.fwd[:, 0])
        fy = np.interp(t_us, self.t, self.fwd[:, 1])
        fw = np.array([fx, fy, 0.0])
        fw /= np.linalg.norm(fw)
        return np.array([x, y, z]), fw

    def scan_index(self, t_us):
        return int(np.argmin(np.abs(self.t - t_us)))

    def camera_frame_index(self, t_us):
        """Row of camera_poses.csv (= frame of video.mp4) closest to a lidar time."""
        if self.cam_t is None:
            return None
        return int(np.argmin(np.abs(self.cam_t - t_us)))

    def ring_at(self, xy):
        _, j = self.pts_tree.query(xy)
        return float(self.basin[j]), bool(self.capped[j])


# ---------- the lidar half ----------
def look_at(C, target):
    f = target - C
    f /= np.linalg.norm(f)
    r = np.cross(f, np.array([0, 0, 1.0]))
    r /= np.linalg.norm(r)
    return np.vstack([r, np.cross(f, r), f])


def project(P, C, R, fov):
    q = (P - C) @ R.T
    z = q[:, 2]
    fpx = (H / 2) / np.tan(np.radians(fov) / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        return W / 2 + fpx * q[:, 0] / z, H / 2 + fpx * q[:, 1] / z, z


def hex_rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


def splat(img, x, y, z, col, px):
    """Draw each point as a px by px square, brightest wins. Nearer points are drawn last."""
    order = np.argsort(-z)
    xi, yi = np.round(x[order]).astype(int), np.round(y[order]).astype(int)
    c = col[order]
    for dx in range(px):
        for dy in range(px):
            xx, yy = xi + dx, yi + dy
            ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
            img[yy[ok], xx[ok]] = np.maximum(img[yy[ok], xx[ok]], c[ok])


_BG = None


def background():
    """A barely-there vertical gradient and a soft glow at the vanishing point, so the half is not flat black."""
    global _BG
    if _BG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        horizon = 520.0
        g = np.clip(1 - np.abs(yy - horizon) / (H - horizon), 0, 1)[:, :, None] * np.array([6, 9, 14], np.float32)
        rr = np.hypot(xx - W / 2, yy - horizon) / 900.0
        glow = np.clip(1 - rr, 0, 1)[:, :, None] ** 2 * 0.35 * np.array([14, 24, 38], np.float32)
        _BG = (g + glow) / 255
    return _BG


def lidar_half(drive, i, car, fw, s, look, ring_r, ring_capped):
    """One 2160x1920 image: scan i's points, the car at `car` heading `fw`, dolly position s in 0..1."""
    pts, T = drive.scan(i)
    lat = np.array([-fw[1], fw[0], 0.0])
    s = s * s * (3 - 2 * s)                                # ease in and out
    h, back, side = [(1 - s) * a + s * b for a, b in zip(look["cam"], look["dolly"])]
    C = car - back * fw + side * lat + np.array([0, 0, h])
    R = look_at(C, car + look["aim"] * fw + np.array([0, 0, 0.4]))
    proj = lambda P: project(P, C, R, look["fov"])  # noqa: E731

    x, y, z = proj(pts)
    ok = (z > 1.5) & (x > -2) & (x < W + 2) & (y > -2) & (y < H + 2)
    x, y, z = x[ok], y[ok], z[ok]
    rel = pts[ok, 2] - car[2]
    fade = np.clip(0.12 + 1.05 * np.exp(-z / look["fade"]), 0, 1)   # far points fade into the dark (floor 0.12, same both days)
    above = rel > 0.25
    img = background().copy()
    road_col = np.clip(hex_rgb(look["road"]) * 1.3, 0, 1) * fade[~above, None]   # road a step brighter, same gain both days
    splat(img, x[~above], y[~above], z[~above], road_col, look["px"])
    above_img = np.zeros_like(img)
    splat(above_img, x[above], y[above], z[above], hex_rgb(look["above"]) * 0.88 * fade[above, None], look["px"])   # capped so near walls and parked cars do not blow out
    # a touch of bloom on the above-road points: a blurred copy, max-combined with the crisp one
    bloom = np.asarray(Image.fromarray((above_img * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255
    img = np.maximum(img, np.maximum(above_img, bloom * 0.9))
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    draw = ImageDraw.Draw(im, "RGBA")

    if look["ring"] and ring_r is not None:
        ang = np.linspace(0, 2 * np.pi, 360)
        ring = car + ring_r * (np.cos(ang)[:, None] * fw + np.sin(ang)[:, None] * lat) + np.array([0, 0, 0.03])
        rx, ry, rz = proj(ring)
        ring_pts = [(float(a), float(b)) for a, b in zip(rx, ry)] if np.all(rz > 0.5) else None
        if ring_pts:
            draw.polygon(ring_pts, fill=ROAD_RGB + (12,))        # the disc sits under the car, same look on both days
            draw.line(ring_pts + ring_pts[:1], fill=ROAD_RGB + (170,), width=4)

    # the car: contact shadow multiplied onto the points, then the shaded body on top (it covers the ring's middle)
    shadow = draw_car(ImageDraw.Draw(Image.new("RGBA", (W, H))), (W, H), car, fw, lat, proj, kind=look["car"],
                      paint=look["paint"], shadow=True)
    if shadow is not None:
        arr = np.asarray(im).astype(np.float32) * (np.asarray(shadow).astype(np.float32) / 255)[:, :, None]
        im = Image.fromarray(arr.astype(np.uint8))
        draw = ImageDraw.Draw(im, "RGBA")
    layer = Image.new("RGBA", (2 * W, 2 * H), (0, 0, 0, 0))             # the car at 2x, then downsampled: smooth edges
    proj2 = lambda P: (lambda x, y, z: (2 * x, 2 * y, z))(*proj(P))  # noqa: E731
    draw_car(ImageDraw.Draw(layer, "RGBA"), (2 * W, 2 * H), car, fw, lat, proj2, kind=look["car"], paint=look["paint"], shadow=False)
    im = Image.alpha_composite(im.convert("RGBA"), layer.resize((W, H), Image.LANCZOS)).convert("RGB")
    draw = ImageDraw.Draw(im, "RGBA")
    if look["ring"] and ring_r is not None and ring_pts:
        # the ring line goes over the car at low alpha: in the storm the margin is smaller than the car itself
        draw.line(ring_pts + ring_pts[:1], fill=ROAD_RGB + (40,), width=2)   # a ghost of the ring where the car covers it
    return im


# ---------- the camera half ----------
CROP = f"crop=1755:1560:346:0,scale={W}:{H}:flags=lanczos"   # the camera is 2448x2048: a top-aligned window that drops most of the hood, then scaled to the half


def extract_range(drive, k0, k1, cache):
    """Pull video frames k0..k1 in one ffmpeg pass (seeking frame by frame would decode the whole video each time)."""
    need = [k for k in range(k0, k1 + 1) if not (cache / f"{drive.name}_{k:06d}.png").exists()]
    if not need or not drive.video.exists():
        return
    tmp = cache / "tmp_%05d.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(drive.video), "-vf",
                    f"select=between(n\\,{k0}\\,{k1})," + CROP, "-fps_mode", "passthrough", str(tmp)], check=True)
    for n, k in enumerate(range(k0, k1 + 1), start=1):
        (cache / f"tmp_{n:05d}.png").rename(cache / f"{drive.name}_{k:06d}.png")


def camera_half(drive, frame_idx, cache):
    if frame_idx is None or not drive.video.exists():
        im = Image.new("RGB", (W, H), (12, 12, 14))
        ImageDraw.Draw(im).text((W / 2, H / 2), "camera footage not downloaded yet", fill=(120, 120, 120),
                                font=ImageFont.truetype(FONT, 60), anchor="mm")
        return im
    path = cache / f"{drive.name}_{frame_idx:06d}.png"
    if not path.exists():
        extract_range(drive, frame_idx, frame_idx, cache)
    return Image.open(path).convert("RGB")


def grade(im):
    """Same gentle grade on both days: more contrast, less colour, highlights rolled off and cooled, a vignette."""
    a = np.asarray(im).astype(np.float32) / 255
    lum = a.mean(axis=2)
    bp = max(float(np.percentile(lum, 1)), 0.04)            # black point from this frame's darkest 1 percent (the storm is milky)
    a = np.clip((a - bp) / (1 - bp), 0, 1)
    im = Image.fromarray((a * 255).astype(np.uint8))
    im = ImageEnhance.Contrast(im).enhance(1.12)
    im = ImageEnhance.Color(im).enhance(0.85)
    a = np.asarray(im).astype(np.float32) / 255
    a = a - 0.22 * a ** 3                                   # pull the brightest tones down (the storm sky is near white)
    hi = np.clip((a.mean(axis=2, keepdims=True) - 0.6) / 0.4, 0, 1)
    a = a * (1 + hi * np.array([-0.03, 0.0, 0.03], np.float32))   # cool the highlights a touch, to match the lidar half
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    a = a * (1 - 0.20 * np.clip(rr - 0.5, 0, 1) / 0.9)[:, :, None]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


_GRAD = None


def compose(top, bottom, label, sub):
    global _GRAD
    frame = Image.new("RGB", (W, 2 * H), (0, 0, 0))
    frame.paste(grade(top), (0, 0))
    frame.paste(bottom, (0, H))
    if _GRAD is None:   # the seam: camera fades to black over its last 80 px; the lidar half starts black and clears over 420 px
        g = Image.new("RGBA", (W, 2 * H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        for yy in range(80):
            gd.line([(0, H - 80 + yy), (W, H - 80 + yy)], fill=(0, 0, 0, int(255 * yy / 80)))
        for yy in range(420):
            a = 255 if yy < 60 else (int(255 - 105 * (yy - 60) / 220) if yy < 280 else int(150 * (1 - (yy - 280) / 140)))
            gd.line([(0, H + yy), (W, H + yy)], fill=(0, 0, 0, a))
        _GRAD = g
    frame = Image.alpha_composite(frame.convert("RGBA"), _GRAD).convert("RGB")
    d = ImageDraw.Draw(frame)
    d.text((132, H + 110), label, fill=(255, 255, 255), font=ImageFont.truetype(FONT, 110, index=10), anchor="lm")
    if sub:
        d.text((132, H + 205), sub, fill=(205, 218, 230), font=ImageFont.truetype(FONT, 72), anchor="lm")
    return frame


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--look", default="D2", choices=list(LOOKS))
    ap.add_argument("--start", type=float, default=36.0, help="storm scan-seconds where the storm clip starts")
    ap.add_argument("--start-us", type=int, help="absolute storm scan time (us) where the clip starts; overrides --start. "
                    "The Nov 21 clip started at 1611678399605530 (36 s into the first study's 60 s stretch).")
    ap.add_argument("--seconds", type=float, default=6.0, help="length of each day's clip")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--still", type=float, help="one storm frame at this storm scan-second, and the matching no-snow frame beside it")
    ap.add_argument("--closeup", action="store_true", help="still only: camera 6 m from the car, to judge the car shape")
    ap.add_argument("--frames-dir")
    ap.add_argument("--cache", default="/tmp/rs_cam_cache")
    ap.add_argument("--out", default="results/sketch.png")
    ap.add_argument("--storm-csv", default="results/basin_storm.csv", help="ring and label values for the storm (a basin_*.csv or a whole-route route_storm*.csv)")
    ap.add_argument("--control-csv", default="results/basin_control.csv")
    a = ap.parse_args()
    look = dict(LOOKS[a.look])
    if a.closeup:
        look.update(cam=(3.2, 6.5, 2.4), dolly=(3.2, 6.5, 2.4), aim=2.0, fov=50)
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    storm, clear = Drive(STORM, a.storm_csv), Drive(CONTROL, a.control_csv)
    n = int(a.seconds * a.fps)

    def clip_start(sec):
        """Storm scan at `sec` (or at --start-us), and the no-snow scan taken closest to that spot on the road."""
        i0 = storm.scan_index(a.start_us if a.start_us else storm.t[0] + sec * 1e6)
        j0 = int(clear.tree.query(storm.xyz[i0, :2])[1])
        storm.mount_height(i0, min(i0 + int(a.seconds * 10), len(storm.t) - 1))
        clear.mount_height(j0, min(j0 + int(a.seconds * 10), len(clear.t) - 1))
        return i0, j0

    def frame(drive, t_us, s, label, sub, ring_r, ring_capped):
        car, fw = drive.pose_at(t_us)
        top = camera_half(drive, drive.camera_frame_index(int(t_us)), cache)
        bottom = lidar_half(drive, drive.scan_index(t_us), car, fw, s, look, ring_r, ring_capped)
        return compose(top, bottom, label, sub)

    def sub_text(drive, xy):
        r, capped = drive.ring_at(xy)
        return "Room for error here: " + ("3 m+" if capped else f"{r:g} m")      # plain words: more room is better

    if a.still is not None:
        i0, j0 = clip_start(a.still)
        f1 = frame(storm, storm.t[i0], 0.3, "Snowstorm", sub_text(storm, storm.xyz[i0, :2]), *storm.ring_at(storm.xyz[i0, :2]))
        f2 = frame(clear, clear.t[j0], 0.3, "No snow", sub_text(clear, clear.xyz[j0, :2]), *clear.ring_at(clear.xyz[j0, :2]))
        sheet = Image.new("RGB", (2 * W + 40, 2 * H), (0, 0, 0))
        sheet.paste(f1, (0, 0))
        sheet.paste(f2, (W + 40, 0))
        sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS).save(a.out)
        print(f"wrote {a.out} (storm scan {i0}, no-snow scan {j0}, look {a.look})")
        return

    out = Path(a.frames_dir)
    out.mkdir(parents=True, exist_ok=True)
    i0, j0 = clip_start(a.start)
    for d, idx in ((storm, i0), (clear, j0)):
        k0 = d.camera_frame_index(int(d.t[idx]))
        if k0 is not None:
            extract_range(d, k0 - 2, k0 + int(a.seconds * 10) + 2, cache)
    t0 = time.time()
    k = 0
    for d, idx, label in ((storm, i0, "Snowstorm"), (clear, j0, "No snow")):
        sub = sub_text(d, d.xyz[idx, :2])                   # one value per half; the ring itself follows the road
        ring_r, _ = d.ring_at(d.xyz[idx, :2])
        for m in range(n):
            t_us = d.t[idx] + m / a.fps * 1e6
            car, _ = d.pose_at(t_us)
            target, capped = d.ring_at(car[:2])
            ring_r += (target - ring_r) * 0.15              # ease toward the nearest test point's radius over about half a second
            frame(d, t_us, k / (2 * n - 1), label, sub, ring_r, capped).save(out / f"frame_{k:05d}.png")
            if k % 30 == 0:
                print(f"  frame {k}/{2 * n} ({time.time() - t0:.0f} s)", flush=True)
            k += 1
    print(f"{k} frames in {out} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
