#!/usr/bin/env python3
"""Wrap the original masthead in self-contained SVG motion; local output only."""

import base64
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/profile-masthead-v2.webp"
OUTPUT = ROOT / "assets/profile-masthead-motion.svg"


def masthead():
    # Keep the original pixels, full composition and type. SVG image documents
    # cannot fetch a sibling image reliably on GitHub, so embed the source bytes.
    original = base64.b64encode(SOURCE.read_bytes()).decode("ascii")
    stars = [(481, 151, 1.7, 0), (860, 79, 2.1, -1.4), (992, 36, 1.5, -3.2),
             (1944, 251, 1.8, -2.4), (761, 129, 1.4, -4.6)]
    points = "".join(
        f'<circle class="star" cx="{x}" cy="{y}" r="{radius}" '
        f'style="animation-delay:{delay}s"/>' for x, y, radius, delay in stars)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="2117" height="743" viewBox="0 0 2117 743" role="img" aria-labelledby="title desc">
<title id="title">soBigRice · CODE. CREATE. REPEAT.</title>
<desc id="desc">MiaoBoss and Mi Da Fan's neon studio. Slow orbital light trails and stars over the original masthead. Reduced motion keeps the original still image.</desc>
<defs>
  <filter id="glow" x="-50%" y="-100%" width="200%" height="300%" color-interpolation-filters="sRGB">
    <feGaussianBlur stdDeviation="3" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <linearGradient id="trail"><stop stop-color="#ff315d"/><stop offset=".75" stop-color="#ff8aa3"/><stop offset="1" stop-color="#fff0f4"/></linearGradient>
</defs>
<style>
  .orbit{{fill:none;stroke:url(#trail);stroke-width:2.5;stroke-linecap:round;stroke-dasharray:42 958;animation:orbit 12s linear infinite}}
  .orbit.second{{stroke-width:1.8;stroke-dasharray:24 976;animation-delay:-6s;opacity:.6}}
  .desk{{fill:none;stroke:#ff4b6d;stroke-width:2;stroke-linecap:round;stroke-dasharray:14 986;animation:orbit 10s linear infinite;animation-delay:-4s;opacity:.65}}
  .star{{fill:#d5faff;opacity:.3;animation:starlight 6s ease-in-out infinite}}
  .wire{{fill:none;stroke:#91a3ff;stroke-width:1;opacity:.22;transform-box:fill-box;transform-origin:center;animation:wire 24s linear infinite}}
  @keyframes orbit{{to{{stroke-dashoffset:-1000}}}}
  @keyframes starlight{{0%,100%{{opacity:.2}}50%{{opacity:.9}}}}
  @keyframes wire{{to{{transform:rotate(360deg)}}}}
  @media(prefers-reduced-motion:reduce){{.motion{{display:none}}.motion *{{animation:none}}}}
</style>
<image width="2117" height="743" href="data:image/webp;base64,{original}"/>
<!-- Trails follow the empty sky and desk; the face and lettering stay still. -->
<g class="motion" filter="url(#glow)">
  <path class="orbit" pathLength="1000" d="M1802 65C1912 42 2011 44 2047 76C2070 100 2002 162 1890 211"/>
  <path class="orbit second" pathLength="1000" d="M934 282C1010 228 1063 205 1158 170"/>
  <path class="desk" pathLength="1000" d="M610 666L755 649L895 646L1042 633"/>
  {points}
</g>
<g class="motion"><path class="wire" d="M935 64L980 88L969 133L925 151L884 115L895 77Z M935 64L925 151M895 77L969 133M980 88L884 115"/></g>
</svg>'''


if __name__ == "__main__":
    OUTPUT.write_text(masthead())
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size:,} bytes); original image unchanged.")
