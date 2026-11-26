# Burnett et al., in plain words
Nov 20 2026, checked against the paper.

**Version warning:** this guide uses arXiv **v3** (8 Jun 2023), which updated the ground truth and the results. v1/v2 (the 2022 RA-L version, titled "Should Radar Replace Lidar...") report different lidar numbers for the storm: **4.7 cm lateral**, not 2.3 cm. Always say which version you compare against.

## 1. Summary
Question: in bad weather, does radar beat lidar at localizing a car against a map built earlier? They built three "Teach and Repeat" pipelines (lidar-to-lidar, radar-to-radar, radar-to-lidar), built a map from one Boreas drive and localized later drives against it. Result: lidar was the most accurate everywhere, even in a snowstorm with ice covering about 1/4 of its view (Fig. 7). Radar came close with a much smaller map: 5.6 vs 86.4 MB/km (Table II).

## 2. Setup
- **Drives (Sec. IV):** map = 2020-11-26. Test = 2020-12-04, 2021-01-26 (snowstorm), 2021-02-09, 2021-03-09, 2021-06-29 (rain), 2021-09-08 (night). v3 appendix adds 2021-10-05, 10-26, 11-06, 11-28.
- **Map:** lidar only, "no GPS or IMU information is required". Not one big map: a chain of small submaps. A new one is added when the car has moved more than 10 m or turned more than 30 deg; each holds the last 3 scans (Sec. III-A).
- **Odometry:** CT-ICP, point-to-plane, with motion compensation (Sec. III-C).
- **Localization:** ICP aligns the motion-compensated live scan to the nearest submap. The starting guess comes from odometry and is kept as a prior in the cost (Sec. III-D).
- **Preprocessing (lidar):** 0.3 m voxels, keep points with a plane score above 0.95, at most 20,000 (Sec. III-B).
- **Metric:** RMSE of the pose of the live sensor relative to the map, split into lateral, longitudinal and heading, in 2D (Sec. IV).
- **Ground truth:** post-processed GNSS + IMU + wheel encoders with RTX corrections, "typically 2-4 cm" error (Sec. IV).

## 3. Key lidar numbers (Table I, v3)
| Drive | Lateral (m) | Longitudinal (m) | Heading (deg) |
|---|---|---|---|
| 2021-01-26 snow | 0.023 | 0.026 | 0.040 |
| 2021-06-29 rain | 0.025 | 0.056 | 0.050 |
| 2021-09-08 night | 0.030 | 0.036 | 0.048 |
| 2020-12-04 | 0.060 | 0.059 | 0.035 |
| Mean of 6 | 0.032 | 0.039 | 0.042 |
v1/v2 Table I for comparison: 2021-01-26 = 0.047 / 0.034 / 0.034, 2020-12-04 lateral 0.057, mean lateral 0.052.

So "2.3 cm" = v3 lidar-to-lidar lateral RMSE on the snowstorm drive.

## 4. Checklist for a fair reproduction
- [ ] Map drive 2020-11-26, test drive 2021-01-26
- [ ] Map from lidar only (if the map is built from ground-truth poses, say so)
- [ ] Point-to-plane matching, 0.3 m voxels
- [ ] Motion-compensate scans before matching
- [ ] Starting guess from odometry, not from ground truth
- [ ] Score lateral / longitudinal / heading separately in 2D (evo does not split lateral vs longitudinal; compute it yourself)
- [ ] No IMU or wheel data
What will likely differ with the open tools used here: KISS-ICP uses its own point-to-point ICP and constant-velocity deskewing (not CT-ICP; this is from the tool's docs, not the paper); Open3D ICP has no prior term; one global map behaves differently from a chain of submaps.

## 5. Five terms
- **ICP:** repeatedly match nearest points and solve for the best pose until it stops changing.
- **Scan-to-map localization:** aligning the live scan to a stored map, not to the previous scan.
- **Motion distortion:** one sweep takes 0.1 s at 10 Hz, so the car moves during the scan and the cloud smears.
- **Lateral / longitudinal error:** sideways error vs error along the direction of travel.
- **RMSE:** square each error, average, take the square root. Big misses count extra.

## 6. Watch out
- 2.3 cm is inside the ground truth's own 2 to 4 cm error, so at that level no one can tell who is right.
- Snow was not lidar's worst drive: 2020-12-04 was (6.0 cm lateral in v3).
- The text points to "Table IV" for localization results, but the numbers are in Table I. Some figure references are broken.
- **The paper never tests a bad starting guess.** No baseline exists for the blind budget, which is the opening for Snowbound.

## Citation
K. Burnett, Y. Wu, D. J. Yoon, A. P. Schoellig, T. D. Barfoot, "Are We Ready for Radar to Replace Lidar in All-Weather Mapping and Localization?", IEEE RA-L, 2022. arXiv:2203.10174v3. https://arxiv.org/abs/2203.10174
