# scripts

What made what. Run from the repo root with `uv run python scripts/<name>.py`; the data lives in `~/snowbound-data` (see the README).

The study
- `fetch_boreas.py`, `fetch_control.py`, `fetch_route.py`: download the drives (poses, calibration, the scans along the route).
- `score_60s.py`: the matcher (point-to-plane ICP, scipy), the map builder and the first 60 s test.
- `sweep_basin.py`: the push test at one spot. `sweep_route.py`: the test at every spot along the loop, in parallel chunks. `sweep_route_zlock.py`: the same with the height locked, the run the site uses.
- `compare_basins.py`, `compare_zlock.py`: pair the days, compute the tables in the notes.
- `plot_basin_map.py`: the first study's map. `why_spots.py`: why some spots and not others.
- `critic/`: the independent checks that found the sinking-scan bug (notes/critic-most-affected.md).
- `doctor.py`: checks the tools and data are in place. `view_scan.py`: look at one scan.

The site and the clips
- `build_site.py`: writes docs/data (route.json, the two sampled scans, the car mesh) and the per-spot images. `car_mesh.py`: the car drawn in code.
- `reel/`: the dashcam and lidar clips for the short videos (`render_chase.py`, `render_realstreet.py`), the HD spot frames (`spot_cam_hd.py`), the street map for a post (`plot_street_map.py`), the control-drive camera download (`fetch_control_camera.py`).
