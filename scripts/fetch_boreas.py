#!/usr/bin/env python3
"""Safe Boreas downloader for Snowbound. Python 3.9+ standard library only.

Safety rules (do not loosen without a reason written here):
  - Only https://boreas.s3.us-west-2.amazonaws.com (the official bucket).
  - Only data file types: .bin .csv .png .txt .yaml .mp4. Everything else is refused.
  - Only keys under an allowed drive and folder. No path can leave the output folder.
  - Every file: size must match the bucket listing; MD5 must match when the bucket gives one.
  - Files are written as .part, checked, then renamed and set read-only (no execute bit).
  - Nothing downloaded is ever opened or run by this script.
  - Dry run by default. Add --go to download. Refuses if less than 20 GB would be left free.

Usage:
  python3 fetch_boreas.py week1-meta   --out ~/snowbound-data            # list only
  python3 fetch_boreas.py week1-meta   --out ~/snowbound-data --go       # download
  python3 fetch_boreas.py week1-sample --out ~/snowbound-data --start 3:30 --seconds 60 [--go]
  python3 fetch_boreas.py control-sample --out ~/snowbound-data --start 3:30 --seconds 60 [--go]   # same road, clear Dec 1, lidar only
"""
import argparse, csv, hashlib, os, re, shutil, ssl, stat, subprocess, sys, time
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET

BUCKET = "https://boreas.s3.us-west-2.amazonaws.com"
ALLOWED_EXT = {".bin", ".csv", ".png", ".txt", ".yaml", ".mp4"}
MIN_FREE_GB_AFTER = 20.0

MAP_DRIVE = "boreas-2020-11-26-13-58"    # sunny map day
CLEAR_DRIVE = "boreas-2020-12-01-13-26"  # clear winter control
SNOW_DRIVE = "boreas-2021-01-26-11-22"   # falling snow
WEEK1_DRIVES = [MAP_DRIVE, CLEAR_DRIVE, SNOW_DRIVE]
DRIVE_RE = re.compile(r"^boreas-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}$")

# Small files needed to understand a drive. No raw logs, no sbet, no radar.
META_FILES = [
    "calib/P_camera.txt", "calib/T_applanix_lidar.txt", "calib/T_camera_lidar.txt",
    "calib/camera0_intrinsics.yaml",
    "applanix/lidar_poses.csv", "applanix/camera_poses.csv",
    "video.mp4",
]
ALLOWED_DIRS = {"calib", "applanix", "lidar", "camera"}
S3 = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def check_key(key):
    """Raise if a bucket key is anything other than an allowed data file."""
    parts = key.split("/")
    if len(parts) < 2 or not DRIVE_RE.match(parts[0]):
        raise ValueError("refused key (bad drive): " + key)
    if any(p in ("", ".", "..") or "\\" in p for p in parts):
        raise ValueError("refused key (bad path): " + key)
    if len(parts) > 2 and parts[1] not in ALLOWED_DIRS:
        raise ValueError("refused key (folder not allowed): " + key)
    ext = os.path.splitext(parts[-1])[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("refused key (file type not allowed): " + key)
    return key


def local_path(out, key):
    out = os.path.realpath(out)
    p = os.path.realpath(os.path.join(out, *key.split("/")))
    if not p.startswith(out + os.sep):
        raise ValueError("refused path (outside output folder): " + key)
    return p


def ssl_context():
    """Certificate checks always stay ON. python.org builds of Python on macOS ship without
    trusted root certificates, so on a Mac we also load Apple's built-in system roots."""
    ctx = ssl.create_default_context()
    if sys.platform == "darwin":
        try:
            pem = subprocess.run(
                ["/usr/bin/security", "find-certificate", "-a", "-p",
                 "/System/Library/Keychains/SystemRootCertificates.keychain"],
                capture_output=True, text=True, check=True, timeout=30).stdout
            if "BEGIN CERTIFICATE" in pem:
                ctx.load_verify_locations(cadata=pem)
        except (OSError, subprocess.SubprocessError, ssl.SSLError) as e:
            print("note: could not load macOS system certificates (%s)" % e)
    return ctx


_CTX = None


def http_get(url):
    global _CTX
    if not url.startswith(BUCKET + "/"):
        raise ValueError("refused host: " + url)
    if _CTX is None:
        _CTX = ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": "snowbound-fetch/1"})
    return urllib.request.urlopen(req, timeout=60, context=_CTX)


def list_prefix(prefix, max_keys=None):
    """Yield (key, size, etag) for every object under prefix."""
    token, n = None, 0
    while True:
        q = {"list-type": "2", "prefix": prefix}
        if token:
            q["continuation-token"] = token
        with http_get(BUCKET + "/?" + urllib.parse.urlencode(q)) as r:
            root = ET.fromstring(r.read())
        for c in root.findall(S3 + "Contents"):
            key = c.find(S3 + "Key").text
            if key.endswith("/"):
                continue
            yield key, int(c.find(S3 + "Size").text), c.find(S3 + "ETag").text.strip('"')
            n += 1
            if max_keys and n >= max_keys:
                return
        if root.findtext(S3 + "IsTruncated") != "true":
            return
        token = root.findtext(S3 + "NextContinuationToken")


def head(key):
    """(size, etag) for one key, via a one-key listing."""
    for k, size, etag in list_prefix(key, max_keys=5):
        if k == key:
            return size, etag
    raise FileNotFoundError("not in bucket: " + key)


def ts_of(key):
    return int(os.path.splitext(key.rsplit("/", 1)[1])[0])


def read_poses(path):
    """Return list of (time_us, east, north) from a Boreas *_poses.csv. Fails loudly on surprises."""
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    head_row = [h.strip() for h in rows[0]]
    need = ["GPSTime", "easting", "northing"]
    for n in need:
        if n not in head_row:
            raise SystemExit("poses file %s has no %s column; header is %s" % (path, n, head_row))
    it, ie, inn = (head_row.index(n) for n in need)
    out = [(int(float(r[it])), float(r[ie]), float(r[inn])) for r in rows[1:] if r]
    t0 = out[0][0]
    if not (1.4e15 < t0 < 1.8e15):
        raise SystemExit("unexpected time units in %s: %s (expected microseconds)" % (path, t0))
    return out


def plan_meta(out):
    jobs = []
    for d in WEEK1_DRIVES:
        for f in META_FILES:
            key = check_key(d + "/" + f)
            size, etag = head(key)
            jobs.append((key, size, etag))
    return jobs


def parse_start(s):
    if ":" in s:
        m, sec = s.split(":")
        return int(m) * 60 + float(sec)
    return float(s)


def plan_sample(out, start, seconds, cam_hz, target=MAP_DRIVE, lidar_only=False, snow_too=True):
    """Lidar + camera for `seconds` of the snow drive, plus the same stretch of road from `target` (map drive by default).
    control-sample: target = clear Dec 1 drive, lidar only, snow window not re-downloaded."""
    snow = read_poses(local_path(out, SNOW_DRIVE + "/applanix/lidar_poses.csv"))
    mapp = read_poses(local_path(out, target + "/applanix/lidar_poses.csv"))
    t_from = snow[0][0] + int(start * 1e6)
    t_to = t_from + int(seconds * 1e6)
    win = [p for p in snow if t_from <= p[0] <= t_to]
    if not win:
        raise SystemExit("no snow-drive poses in that window; drive is %.0f s long" % ((snow[-1][0] - snow[0][0]) / 1e6))
    # Same road on the map drive, driven in the SAME direction. The loop uses some streets twice
    # (out and back), so plain nearest-point matching can grab the opposite pass.
    def direction(poses, i):
        j = min(i + 5, len(poses) - 1)
        k = max(j - 10, 0)
        return poses[j][1] - poses[k][1], poses[j][2] - poses[k][2]

    def nearest(poses_i, e, n, dvec):
        best, best_d = None, 1e18
        for i in range(len(mapp)):
            d2 = (mapp[i][1] - e) ** 2 + (mapp[i][2] - n) ** 2
            if d2 >= best_d:
                continue
            md = direction(mapp, i)
            if md[0] * dvec[0] + md[1] * dvec[1] <= 0:  # opposite direction or standing still
                continue
            best, best_d = i, d2
        return best, best_d ** 0.5

    first, last = snow.index(win[0]), snow.index(win[-1])
    i0, g0 = nearest(None, win[0][1], win[0][2], direction(snow, first))
    i1, g1 = nearest(None, win[-1][1], win[-1][2], direction(snow, last))
    if i0 is None or i1 is None:
        raise SystemExit("map drive never drives this stretch in the same direction; pick another --start")
    print("map drive match: scans %d to %d, gaps %.1f m and %.1f m (should be under 10 m)" % (i0, i1, g0, g1))
    if max(g0, g1) > 25:
        raise SystemExit("map drive does not pass near this window; pick another --start")
    if i1 <= i0 or (i1 - i0) > 3 * len(win) + 100:
        raise SystemExit("map drive match looks wrong (scans %d to %d for a %d-scan window); pick another --start" % (i0, i1, len(win)))
    m_from, m_to = mapp[max(0, i0 - 20)][0], mapp[min(len(mapp) - 1, i1 + 20)][0]

    jobs = []
    pairs = ((SNOW_DRIVE, t_from, t_to), (target, m_from, m_to)) if snow_too else ((target, m_from, m_to),)
    sensors = (("lidar", 0),) if lidar_only else (("lidar", 0), ("camera", int(1e6 / cam_hz)))
    for drive, a, b in pairs:
        for sensor, step_us in sensors:
            last = None
            for key, size, etag in list_prefix(drive + "/" + sensor + "/"):
                try:
                    check_key(key)
                    t = ts_of(key)
                except ValueError:
                    print("  skipped unexpected file: " + key)
                    continue
                if t < a or t > b:
                    continue
                if step_us and last is not None and t - last < step_us:
                    continue
                last = t
                jobs.append((check_key(key), size, etag))
    return jobs


def download(out, jobs):
    done = skipped = 0
    t_start, bytes_done = time.time(), 0
    for i, (key, size, etag) in enumerate(jobs, 1):
        dst = local_path(out, key)
        if os.path.exists(dst) and os.path.getsize(dst) == size:
            skipped += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        part = dst + ".part"
        md5 = hashlib.md5()
        with http_get(BUCKET + "/" + urllib.parse.quote(key)) as r, open(part, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                md5.update(chunk)
        got = os.path.getsize(part)
        if got != size:
            os.replace(part, part + ".bad")
            raise SystemExit("size mismatch on %s: got %d, expected %d (kept as .bad)" % (key, got, size))
        if "-" not in etag and md5.hexdigest() != etag:  # multipart ETags are not plain MD5
            os.replace(part, part + ".bad")
            raise SystemExit("checksum mismatch on %s (kept as .bad)" % key)
        os.replace(part, dst)
        os.chmod(dst, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)  # 644, never executable
        done += 1
        bytes_done += size
        rate = bytes_done / max(time.time() - t_start, 1e-6) / 1e6
        if i % 25 == 0 or i == len(jobs):
            print("  %d/%d files, %.2f GB, %.1f MB/s" % (i, len(jobs), bytes_done / 1e9, rate))
    with open(os.path.join(out, "manifest.csv"), "a", newline="") as f:
        w = csv.writer(f)
        for key, size, etag in jobs:
            w.writerow([key, size, etag, time.strftime("%Y-%m-%d %H:%M")])
    print("done: %d downloaded, %d already there" % (done, skipped))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", choices=["week1-meta", "week1-sample", "control-sample"])
    ap.add_argument("--out", required=True, help="data folder, outside iCloud, e.g. ~/snowbound-data")
    ap.add_argument("--start", default="0:00", help="sample: start time into the snow drive, m:ss")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--cam-hz", type=float, default=1.0, help="sample: camera frames per second to keep")
    ap.add_argument("--go", action="store_true", help="actually download (default is a dry run)")
    a = ap.parse_args()
    out = os.path.expanduser(a.out)
    if "Mobile Documents" in os.path.realpath(out) or "/Documents/" in os.path.realpath(out) + "/":
        raise SystemExit("refused: keep data out of Documents/iCloud. Use something like ~/snowbound-data")
    os.makedirs(out, exist_ok=True)

    if a.plan == "week1-meta":
        jobs = plan_meta(out)
    elif a.plan == "control-sample":
        jobs = plan_sample(out, parse_start(a.start), a.seconds, a.cam_hz, target=CLEAR_DRIVE, lidar_only=True, snow_too=False)
    else:
        jobs = plan_sample(out, parse_start(a.start), a.seconds, a.cam_hz)
    total = sum(s for _, s, _ in jobs)
    free = shutil.disk_usage(out).free
    by = {}
    for k, s, _ in jobs:
        g = k.split("/")[0] + " " + (k.split("/")[1] if k.count("/") > 1 else "video")
        by[g] = by.get(g, 0) + s
    print("plan %s: %d files, %.2f GB, into %s" % (a.plan, len(jobs), total / 1e9, out))
    for g in sorted(by):
        print("  %-36s %7.2f GB" % (g, by[g] / 1e9))
    print("free now %.1f GB, after %.1f GB (minimum kept: %.0f GB)" % (free / 1e9, (free - total) / 1e9, MIN_FREE_GB_AFTER))
    if (free - total) / 1e9 < MIN_FREE_GB_AFTER:
        raise SystemExit("refused: would leave less than %.0f GB free" % MIN_FREE_GB_AFTER)
    if not a.go:
        print("dry run only. Add --go to download.")
        return
    download(out, jobs)


if __name__ == "__main__":
    main()
