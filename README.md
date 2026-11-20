# Snowbound

**Work in progress.** U of T found that lidar localization barely notices snow. I want to find where it breaks.

## The question
Burnett et al. (U of T, RA-L 2022, [arXiv 2203.10174](https://arxiv.org/abs/2203.10174)) localized a January 2021 Toronto snowstorm drive against a map from November 2020 and reported about 2.3 cm lateral error. Snowbound:
1. Reproduces that result with open tools (KISS-ICP for odometry, Open3D scan-to-map ICP, scored with evo).
2. Stress tests it: start the localizer further and further off, and compare success in the storm vs a clear day.
3. Tries one fix: a snowflake filter (DROR) on the raw scans.

Data: the [Boreas dataset](https://registry.opendata.aws/boreas/) (U of T, [paper](https://arxiv.org/abs/2203.10168)). The data is not in this repo.

## Run it
```
make setup    # Python 3.12 env via uv
make doctor   # checks tools and data
make test     # runs the tests
```
Data lives in `~/snowbound-data` (or set `SNOWBOUND_DATA`). Download with `scripts/fetch_boreas.py`.

## Pivot rule
TODO (Delo): what result changes the story, decided before seeing the numbers.

## Status
- [ ] Step 1: setup, loader, 3 data tests (Nov 23 to 29)
- [ ] Step 2: first numbers on a 60 s stretch
- [ ] Step 3: reproduce + stress test
- [ ] Step 4: one fix (DROR)
- [ ] Step 5: one core piece in C++
- [ ] Step 6: results page + video

## Who built what
- Written by Delo: tests/test_loader.py
- Written with Claude (AI): scripts/fetch_boreas.py, scripts/doctor.py, src/snowbound/loader.py
- Used as-is: KISS-ICP, Open3D, evo, Rerun
