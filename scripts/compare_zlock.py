#!/usr/bin/env python3
"""Compare the original route sweep with the height-locked rerun and write notes/results-zlock.md.

Plain words: reads results/route_pairs.csv, route_storm.csv, route_control.csv (free matcher) and the same three
with the _zlock suffix (height, roll and pitch locked), then prints and writes: the medians per day, how many pairs
come out storm smaller / same / bigger, the per-segment medians (the route's segments from fetch_route.storm_segments,
matched by scan time), the first 460 m stretch against the first study (results/basin_pairs.csv if present), the
lock check (dz_max_m per point), and the 23 spots that read 0 m before. Every number comes from the CSVs.

Run: cd ~/snowbound && uv run python scripts/compare_zlock.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

R = Path(__file__).resolve().parents[1]


def fmt(v, capped=None):
    if capped is not None and capped:
        return "3 m+"
    return f"{v:g} m"


def load(suffix):
    p = pd.read_csv(R / f"results/route_pairs{suffix}.csv", index_col=0)
    s = pd.read_csv(R / f"results/route_storm{suffix}.csv").set_index("pair")
    c = pd.read_csv(R / f"results/route_control{suffix}.csv").set_index("pair")
    return p, s, c


def counts(p):
    d = p.storm_basin_m - p.control_basin_m
    return int((d < 0).sum()), int((d == 0).sum()), int((d > 0).sum())


def main():
    p0, s0, c0 = load("")
    p1, s1, c1 = load("_zlock")
    assert list(p0.index) == list(p1.index), "the two runs do not cover the same pairs"
    n = len(p0)
    lines = ["# Whole route, height-locked rerun vs the original (Nov 23, 2026)", "",
             "Plain words: the same 271 paired test points, seeds, push sizes (0.25 to 3 m), 8 directions, 5 deg heading error and 3.5 m",
             "window as results/route_pairs.csv, but the matcher could only move the scan sideways and in yaw (scripts/sweep_route_zlock.py).",
             "Reason: the 23 November check (notes/critic-most-affected.md) found the free matcher sinks moving storm scans about 2.5 m so the",
             "snow in the air lands on the road, which the test counted as a failure. Every number below is computed by scripts/compare_zlock.py.", ""]
    # lock check
    dzs = max(float(s1.dz_max_m.max()), float(c1.dz_max_m.max()))
    lines += ["## Did the lock hold", "",
              f"Largest height change the locked matcher made at any point, either day: {dzs:.6f} m (storm max {s1.dz_max_m.max():.6f}, no snow max {c1.dz_max_m.max():.6f}).",
              "That column is a weak check on its own: the locked matcher cannot change the height by construction, so it reads 0 whenever it ran.",
              f"The proof that it did run is that the results differ from the original at {int((s1.basin_radius_m != s0.basin_radius_m).sum())} storm and "
              f"{int((c1.basin_radius_m != c0.basin_radius_m).sum())} no-snow point-days under the same seeds (the free matcher is deterministic, so a rerun of it would have matched exactly).", ""]
    # medians and caps
    lines += ["## Headline numbers", "", "| | original (free matcher) | height locked |", "|---|---|---|"]
    for name, k0, k1, cap0, cap1 in (("Storm, typical spot (median)", p0.storm_basin_m, p1.storm_basin_m, p0.storm_capped, p1.storm_capped),
                                     ("No snow, typical spot (median)", p0.control_basin_m, p1.control_basin_m, p0.control_capped, p1.control_capped)):
        lines.append(f"| {name} | {k0.median():g} m | {k1.median():g} m |")
    lines.append(f"| Storm spots at the 3 m cap | {int(p0.storm_capped.sum())} of {n} | {int(p1.storm_capped.sum())} of {n} |")
    lines.append(f"| No-snow spots at the 3 m cap | {int(p0.control_capped.sum())} of {n} | {int(p1.control_capped.sum())} of {n} |")
    a0, b0, g0 = counts(p0); a1, b1, g1 = counts(p1)
    lines.append(f"| Storm smaller / same / bigger | {a0} / {b0} / {g0} | {a1} / {b1} / {g1} |")
    d0, d1 = (p0.storm_basin_m - p0.control_basin_m), (p1.storm_basin_m - p1.control_basin_m)
    lines.append(f"| Storm minus no snow, median | {d0.median():g} m | {d1.median():g} m |")
    lines.append(f"| Storm spots at 0 m | {int((p0.storm_basin_m == 0).sum())} | {int((p1.storm_basin_m == 0).sum())} |")
    lines.append(f"| Spots at 0 m on both days | {int(((p0.storm_basin_m == 0) & (p0.control_basin_m == 0)).sum())} | {int(((p1.storm_basin_m == 0) & (p1.control_basin_m == 0)).sum())} |")
    lines.append("")
    # per-spot movement
    ds = p1.storm_basin_m - p0.storm_basin_m
    dc = p1.control_basin_m - p0.control_basin_m
    lines += ["## How the per-spot values moved", "",
              f"Storm: bigger at {int((ds > 0).sum())} spots, same at {int((ds == 0).sum())}, smaller at {int((ds < 0).sum())}; median change {ds.median():g} m, mean {ds.mean():+.2f} m.",
              f"No snow: bigger at {int((dc > 0).sum())} spots, same at {int((dc == 0).sum())}, smaller at {int((dc < 0).sum())}; median change {dc.median():g} m, mean {dc.mean():+.2f} m.", ""]
    # the 23 zero spots
    z = p0[p0.storm_basin_m == 0]
    lines += ["## The 23 spots that read 0 m in the storm before", ""]
    lines.append(f"{len(z)} spots. With the height locked: " + ", ".join(
        f"spot {list(p0.index).index(i) + 1} ({i}) {fmt(p1.loc[i, 'storm_basin_m'], p1.loc[i, 'storm_capped'])}" for i in z.index) + ".")
    lines.append(f"Of these, no snow was 0 m too at {int((z.control_basin_m == 0).sum())}; with the lock those read " + ", ".join(
        fmt(p1.loc[i, 'control_basin_m'], p1.loc[i, 'control_capped']) for i in z[z.control_basin_m == 0].index) + ".")
    lines.append("")
    # segments
    try:
        from fetch_route import storm_segments
        segs, _ = storm_segments(400.0)
        lines += ["## Per segment (the route's same-direction stretches over 400 m, by storm scan time)", "", "| segment | points | storm median, original | storm median, locked | no snow median, original | no snow median, locked |", "|---|---|---|---|---|---|"]
        t = s0.scan_time_us
        for si, (a, b, length_m) in enumerate(segs, 1):
            m = (t >= a) & (t <= b)
            if m.sum() == 0:
                continue
            idx = s0.index[m]
            lab = f"segment {si} ({length_m:.0f} m, in drive order)"
            lines.append(f"| {lab} | {int(m.sum())} | {p0.loc[idx, 'storm_basin_m'].median():g} m | {p1.loc[idx, 'storm_basin_m'].median():g} m | {p0.loc[idx, 'control_basin_m'].median():g} m | {p1.loc[idx, 'control_basin_m'].median():g} m |")
        lines.append("")
    except Exception as e:  # noqa: BLE001
        lines += [f"(segments not listed: {e})", ""]
    # first 460 m vs the first study
    bp = R / "results/basin_pairs.csv"
    if bp.exists():
        b = pd.read_csv(bp)
        col = "basin_radius_m" if "basin_radius_m" in b.columns else None
        if col and {"east", "north"}.issubset(b.columns):
            from scipy.spatial import cKDTree
            tree = cKDTree(np.c_[s0.east, s0.north])
            d, j = tree.query(np.c_[b.east, b.north])
            near = d < 5.0
            idx = s0.index[j[near]]
            lines += ["## The first study's street (results/basin_pairs.csv, route spots within 5 m; these spots lie in segment 2, not in the route's first 463 m)", "",
                      f"{int(near.sum())} of the first study's {len(b)} spots have a route spot within 5 m. Storm median there: first study {b[col][near].median():g} m, "
                      f"route original {p0.loc[idx, 'storm_basin_m'].median():g} m, route locked {p1.loc[idx, 'storm_basin_m'].median():g} m.", ""]
    # the three stops and the hero
    lines += ["## The spots the site shows", "", "| spot | pair | storm original | storm locked | no snow original | no snow locked |", "|---|---|---|---|---|---|"]
    for pid in ["003_005", "007_005", "009_008", "001_003", "000_001", "000_002"]:
        if pid in p0.index:
            k = list(p0.index).index(pid) + 1
            lines.append(f"| {k} | {pid} | {fmt(p0.loc[pid,'storm_basin_m'], p0.loc[pid,'storm_capped'])} | {fmt(p1.loc[pid,'storm_basin_m'], p1.loc[pid,'storm_capped'])} | {fmt(p0.loc[pid,'control_basin_m'], p0.loc[pid,'control_capped'])} | {fmt(p1.loc[pid,'control_basin_m'], p1.loc[pid,'control_capped'])} |")
    lines.append("")
    out = R / "notes/results-zlock.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
