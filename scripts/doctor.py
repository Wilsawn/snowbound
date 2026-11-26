"""Snowbound doctor: checks the tools and the data are ready. Read-only.
Run: make doctor"""
import importlib
import sys

from snowbound import loader

ok = True


def check(label, good, extra="", required=True):
    global ok
    if required:
        ok &= bool(good)
    tag = "OK  " if good else ("FAIL" if required else "TODO")
    print(f"  {tag} {label}" + (f"  ({extra})" if extra else ""))


print(f"Python {sys.version.split()[0]}  at {sys.executable}")
check("Python 3.12", sys.version_info[:2] == (3, 12))

print("Tools:")
for mod in ["numpy", "scipy", "pandas", "matplotlib", "PIL", "pytest"]:
    try:
        m = importlib.import_module(mod)
        check(mod, True, getattr(m, "__version__", "?"))
    except Exception as e:
        check(mod, False, str(e).splitlines()[0])

print(f"Data ({loader.DATA_DIR}):")
check("data folder", loader.DATA_DIR.is_dir())
for drive, need_scans in [(loader.MAP_DRIVE, True), (loader.SNOW_DRIVE, True), (loader.CONTROL_DRIVE, False)]:
    try:
        poses = loader.load_poses(drive)
        check(f"{drive} poses", len(poses) > 0, f"{len(poses)} rows")
    except Exception as e:
        check(f"{drive} poses", False, str(e).splitlines()[0])
        continue
    scans = loader.scan_files(drive)
    check(f"{drive} lidar scans", len(scans) > 0, f"{len(scans)} scans" if scans else "not downloaded yet, Step 2",
          required=need_scans)
    if scans:
        mid = scans[len(scans) // 2]
        pts = loader.load_scan(mid)
        check(f"{drive} scan readable", pts.shape[1] == 6, f"{len(pts)} points x 6 columns")
        _, gap = loader.nearest_pose(poses, loader.scan_time_us(mid))
        check(f"{drive} scan has a pose within 5 ms", gap <= 5000, f"{gap / 1000:.2f} ms")

print("\nAll good." if ok else "\nSomething failed. Fix the lines marked FAIL.")
sys.exit(0 if ok else 1)
