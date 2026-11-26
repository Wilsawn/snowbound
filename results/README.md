# results

The numbers on the site and in the README come from the height-locked run (files ending in `_zlock`). The earlier free-matcher run is kept for comparison because the page tells the story of the 147 that became 111.

- `route_pairs_zlock.csv`: one row per spot (271): storm and no-snow room for error, capped flags, the gap between the paired scans. The source of every number on the site.
- `route_storm_zlock.csv`, `route_control_zlock.csv`: the same per day, with how many of the 8 directions recovered at each push size and the car's speed.
- `route_pairs.csv`, `route_storm.csv`, `route_control.csv`: the earlier run where the matcher could also move the scan up and down (147 cut spots). Superseded.
- `why_spots.csv`, `why_spots.png`, `why_spots_examples.jpg`: the per-spot measures behind notes/results-why-spots.md.
- `basin_*.csv`, `basin_map*.png`, `street_map_*.png`: the first study on one 460 m street (notes/results-storm-vs-control.md).
- `storm-60s/`, `control-60s/`: the first 60 s tests (notes/results-60s-storm.md).
- `chunks/`: the per-chunk outputs the whole-route sweeps write as they run; the joined CSVs above are built from them.
