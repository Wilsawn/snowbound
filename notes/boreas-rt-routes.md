# Boreas Road Trip (Boreas-RT): routes, weather, sizes (checked Nov 23 2026)
Sources: paper arXiv 2602.16870 (v3, Oct 28 2026), the public S3 bucket s3://boreas (listed directly), and Open-Meteo historical weather (a model reanalysis, roughly 9 km grid, NOT a ground observation: confirm with the camera frames before claiming anything).

## The 9 routes (paper Table 3) and which bucket sequences they are
Route types matched to sequences by start/end GPS position, loop vs one-way, and duration. The paper does not publish this mapping, so it is our inference: check each one against the paper's route lengths before use.

| Route | Paper: seqs, avg length, notes | Sequences in the bucket (local start time) |
|---|---|---|
| Suburbs (loop, 7.9 km, "snow banks, snow") | 10 | 2024-12-03-12-54, 2024-12-05-14-25, 2024-12-23-16-27/16-44/17-01/17-18, 2025-01-08-10-59/11-22/12-28, 2025-02-15-16-58/17-19, 2025-02-21-14-51, 2025-02-22-11-32/12-26, 2025-09-22-13-16 (about 17 to 21 min each, start 43.7822,-79.4661) |
| Industrial (loop, 5.4 km, "snow banks, snowstorm") | 5 | 2024-12-05-14-12, 2025-02-15-15-58/16-08/16-16/16-25/16-33, 2025-02-22-11-24/11-52/12-01/12-09/12-18 (about 8 min each, same start) |
| Regional (one-way, about 6.3 km) | 6 | 2024-12-03-13-13/13-34, 2024-12-10-12-07/12-24/12-38/12-56 (both directions) |
| Skyway (loop) | 5 | 2024-12-04-11-45/11-56/12-08/12-19/12-34 (start 43.1701,-79.2266) |
| Tunnel (one-way, about 1.5 km) | 10 | 2024-12-04-14-28 ... 15-24 (both directions, start 43.117,-79.20) |
| Forest (loop) | 4 | 2025-07-18-10-00/10-33/11-00/11-25/11-53 (start 43.9853,-80.0450) |
| Farm (loop) | 10 | 2025-07-18-14-55 ... 16-05 and 2025-08-13-09-01 ... 10-36 (start 44.19,-79.47; two days a month apart, as the paper says) |
| Freeway (one-way, about 45 km) | 3 | 2025-07-18-16-24, 2025-08-13-07-54, 2025-08-13-11-52 |
| Urban (loop, downtown Toronto) | 7 | 2025-08-06-06-33 ... 12-20 (start 43.6607,-79.3950); the paper leaves it out of localization (GPS errors downtown) |
Counts in the bucket are a bit higher than the paper's for some routes (extra or partial runs, e.g. 2024-12-03-10-24 is a 2 min stub). Calibration folders (-calib) are not drives.

## Weather (Open-Meteo, hour of the drive)
- 2025-02-15, 3 to 6 pm (Industrial x5, Suburbs x2): moderate snow falling (code 73, about 0.4 to 0.6 cm/h), -3 C, about 34 cm on the ground. Matches the paper's "snowstorm" for Industrial.
- 2025-02-22, 11 am to 12 pm (Industrial x5, Suburbs x2): clear sky (code 0), no precipitation, -6 C, about 44 cm on the ground.
  -> Same routes, one week apart, falling snow vs none, snow on the ground both days: the same storm-vs-no-snow design as our first study, on 2025 data and a 128-beam lidar.
- 2024-12-23, 4 to 6 pm (Suburbs x4): light snow by 5 pm (code 73, 0.2 cm/h).
- 2024-12-04 (Skyway, Tunnel): overcast, a trace of snow at noon.
- Other winter days (Dec 3, 5, 10, Jan 8, Feb 21): overcast or clear, no snow falling.
- Summer routes (Forest, Farm, Freeway, Urban): no snow.

## Sizes (lidar only, Velodyne Alpha Prime, about 5 MB per scan)
- Industrial loop: about 17 to 19 GB per drive at full rate (about 3,400 to 3,700 scans); every 15th scan about 1.2 GB.
- Suburbs loop: about 57 GB per drive at full rate (about 11,000 scans); every 15th scan about 3.8 GB.
- Same thinning as our route study (every 15th scan, map every 8th to 12th) keeps one storm + one no-snow + one map drive of Industrial under about 6 GB.

## Ideas this opens
1. Part 3 replication: Industrial (and Suburbs) on Feb 15 2025 (snowing) vs Feb 22 2025 (clear), same blind-budget sweep. Does the 2021 result hold on new data and a newer lidar?
2. Environment study: the same sweep on every route (Tunnel and Skyway "featureless", Farm "dust clouds, featureless", Forest, Freeway, Regional) to map how the road itself changes the room for error. No snow on most of those, so it answers a different question than Snowbound.
