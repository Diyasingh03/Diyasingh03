"""Grows a fresh fractal tree, seeded by the current UTC date.

Run manually:  python art/grow.py
Run automatically: .github/workflows/grow.yml, daily via cron.

The tree is a simple recursive branching structure (2D cousin of the
L-system work in Procedural3DTree), not a literal L-system string
rewrite -- kept deliberately small so it's easy to read in one sitting.
"""
import hashlib
import math
import random
from datetime import datetime, timezone

WIDTH, HEIGHT = 900, 420
PALETTE = ["#C4707E", "#7C9A7E", "#C9A15A", "#6E7FA3"]  # rose, sage, ochre, slate
TRUNK = "#8B7965"

MAX_DEPTH = 10
MIN_DEPTH_FOR_LEAF = 6


def today_seed() -> tuple[str, int]:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest = hashlib.sha256(date_str.encode()).hexdigest()
    return date_str, int(digest, 16) % (2**31)


def grow(x, y, angle, length, depth, rng, segments, leaves, accent):
    if depth == 0 or length < 4:
        if depth <= MAX_DEPTH - MIN_DEPTH_FOR_LEAF:
            leaves.append((x, y))
        return

    x2 = x + length * math.cos(angle)
    y2 = y - length * math.sin(angle)
    stroke = max(1.0, depth * 0.85)
    segments.append((x, y, x2, y2, stroke))

    n_children = 2 if depth > 2 else rng.choice([1, 2, 2, 3])
    spread = math.radians(rng.uniform(16, 34))
    decay = rng.uniform(0.72, 0.82)

    for i in range(n_children):
        jitter = rng.uniform(-0.12, 0.12)
        if n_children == 1:
            child_angle = angle + jitter
        else:
            offset = spread * (i - (n_children - 1) / 2)
            child_angle = angle + offset + jitter
        grow(x2, y2, child_angle, length * decay, depth - 1, rng, segments, leaves, accent)


def render(date_str: str, seed: int) -> str:
    rng = random.Random(seed)
    accent = PALETTE[seed % len(PALETTE)]

    segments: list[tuple[float, float, float, float, float]] = []
    leaves: list[tuple[float, float]] = []
    start_len = rng.uniform(58, 72)
    grow(WIDTH / 2, HEIGHT - 20, math.pi / 2, start_len, MAX_DEPTH, rng, segments, leaves, accent)

    branch_paths = "\n    ".join(
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{TRUNK}" stroke-width="{w:.2f}" stroke-linecap="round"/>'
        for x1, y1, x2, y2, w in segments
    )
    leaf_dots = "\n    ".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(2.2, 4.2):.2f}" fill="{accent}" opacity="{rng.uniform(0.55, 0.9):.2f}"/>'
        for x, y in leaves
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="a fractal tree grown fresh on {date_str}">
  <title>today's tree — {date_str}</title>
  <desc>Recursively branched, seeded by today's date. Regrows daily.</desc>
  <g>
    {branch_paths}
    {leaf_dots}
  </g>
</svg>
"""


def main():
    date_str, seed = today_seed()
    svg = render(date_str, seed)
    with open("art/tree.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"grew today's tree for {date_str} (seed={seed}) -> art/tree.svg")


if __name__ == "__main__":
    main()
