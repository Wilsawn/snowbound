# Credits and licenses for the Snowbound site (docs/)

Data
- Boreas dataset, University of Toronto, CC BY 4.0: https://www.boreas.utias.utoronto.ca/ (license: https://creativecommons.org/licenses/by/4.0/)
- The study this builds on: Burnett et al., arXiv 2203.10174: https://arxiv.org/abs/2203.10174

Map
- MapLibre GL JS 4.7.1, BSD-3-Clause: https://github.com/maplibre/maplibre-gl-js
- OpenFreeMap vector tiles (free, no key): https://openfreemap.org ; data © OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright
- Our own style (roads only, our colours) is written in docs/index.html, function mapStyle().

Motion and 3D
- GSAP 3.12.5 with ScrollTrigger, "Standard No Charge GSAP License" (Webflow), free for commercial use: https://gsap.com/community/standard-license/
- three.js 0.160.0 (the point clouds, the car), MIT: https://github.com/mrdoob/three.js

Techniques copied (ideas, not code; every line in docs/index.html is written for this page)
- Split Text and Scroll Reveal, React Bits (MIT plus Commons Clause v1.0): https://reactbits.dev/text-animations/split-text and https://reactbits.dev/text-animations/scroll-reveal ; used for the word-by-word headline lift and the question lighting up.
- Sticky Scroll Reveal, Aceternity UI (Aceternity licence: free in end products, no redistribution as a template): https://ui.aceternity.com/components/sticky-scroll-reveal ; used for the pinned drive with the card that appears once the map settles.
- Number Ticker, Magic UI (MIT): https://magicui.design/docs/components/number-ticker ; used for the stat row count-up.
- Codrops "How to Build Cinematic 3D Scroll Experiences with GSAP" (Nov 2025), repo MIT: https://github.com/JosephASG/codrops-cinematic-scroll-animations ; the idea of scrubbing a three.js camera and text with ScrollTrigger, and soft additive point sprites.
- 21st.dev: Stats Counter Block (no licence shown) and Expand Map (licence unknown) were looked at; nothing copied.

Tools
- detect-gpu 5.0.70 (device tier for the point count and the still fallback), MIT: https://github.com/pmndrs/detect-gpu

Type and tools
- Switzer by Indian Type Foundry via Fontshare, ITF Free Font License: https://www.fontshare.com/fonts/switzer
- Frame-rate and Lighthouse checks: Google Chrome (headless) and Lighthouse, Apache-2.0.
