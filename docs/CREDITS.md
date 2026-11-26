# Credits and licenses for the Snowbound site (docs/)

Data
- Boreas dataset, University of Toronto, CC BY 4.0: https://www.boreas.utias.utoronto.ca/ (license: https://creativecommons.org/licenses/by/4.0/)
- The study this builds on: Burnett et al., arXiv 2203.10174: https://arxiv.org/abs/2203.10174

The page
- The scans, the car, the push rings, the result bars and the loop are drawn on HTML canvas and SVG with no library; every line in docs/index.html is written for this page.
- detect-gpu 5.0.70 (device tier for the point count and the still fallback), MIT: https://github.com/pmndrs/detect-gpu
- Type: Familjen Grotesk and IBM Plex Mono, SIL Open Font License, served by Google Fonts.
- The dashcam frames and the twelve-second clip are from the Boreas camera; the lidar views are drawn from the Boreas scans with only the car's own body (within 3 m) removed.

Checks
- Frame-rate, scroll recordings and Lighthouse: Chromium through Playwright, and Google Lighthouse, Apache-2.0.

Not affiliated with the University of Toronto or any car company.
