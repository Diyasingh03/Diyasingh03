"""Grows a fresh fractal tree, seeded by the current UTC date.

Run manually:  python art/grow.py
Run automatically: .github/workflows/grow.yml, daily via cron.
"""
import hashlib
import math
import random
from datetime import datetime, timezone

WIDTH, HEIGHT = 900, 420
CANVAS_MARGIN = 8
GREENS = ["#3F7D46", "#5B9C5E", "#2E5E38"]
BLOSSOM = "#E8759A"
BLOSSOM_CHANCE = 0.18
TRUNK = "#8B7965"
LEAF_STROKE_DARKEN = 0.72

MAX_GENERATIONS = 9
MIN_BRANCH_GENERATIONS = 3
BUDGET_MIN, BUDGET_MAX = 560, 700  # trunk's total reach in px
RUN_MIN, RUN_MAX = 1, 3            # straight sub-segments per branch decision
RUN_WOBBLE_DEG = 6
RUN_STEP_FRACTION = (0.06, 0.11)   # budget spent per run sub-segment
CHILD_BUDGET_MIN, CHILD_BUDGET_MAX = 0.62, 0.95
MAIN_BOUGH_BUDGET_MIN = 0.85
SIDE_CROSSOVER_DEG = 12  # how far a bough may angle past vertical into its sibling's half

TROPISM_MAX_DEG = 10  # max droop once a bough's budget is spent

SEGMENT_SLICES = 2

TWIG_LEAF_MIN_GEN = 2
TWIG_LEAF_CHANCE = 0.45
TERMINAL_CLUSTER = (2, 4)  # (min, max) leaves per branch tip

MIN_LEAF_SCALE = 0.55
MAX_LEAF_SCALE = 1.25

# Markov transition P(0/1/2/3 children | generation): stop rises on a logistic
# curve; the rest shifts from bushy (fork/triple) to modest (single) with gen.
STOP_CENTER_GEN = 6.3
STOP_STEEPNESS = 0.9
STOP_CEILING = 0.75
BUSHY_FADE_GEN = 8


def children_distribution(gen: int) -> list[tuple[int, float]]:
    stop = STOP_CEILING / (1 + math.exp(-(gen - STOP_CENTER_GEN) * STOP_STEEPNESS))
    remaining = 1 - stop
    bushiness = max(0.0, 1 - gen / BUSHY_FADE_GEN)
    triple_share = 0.35 * bushiness
    fork_share = 0.45 + 0.15 * bushiness
    single_share = max(0.0, 1 - fork_share - triple_share)
    return [
        (0, stop),
        (1, remaining * single_share),
        (2, remaining * fork_share),
        (3, remaining * triple_share),
    ]


def choose_children_count(gen: int, rng: random.Random) -> int:
    options = children_distribution(gen)
    total = sum(w for _, w in options)
    roll = rng.uniform(0, total)
    upto = 0.0
    for count, w in options:
        upto += w
        if roll <= upto:
            return count
    return options[-1][0]


def add_terminal_cluster(x: float, y: float, angle: float, rng: random.Random, leaves: list) -> None:
    for _ in range(rng.randint(*TERMINAL_CLUSTER)):
        jx = x + rng.uniform(-6, 6)
        jy = y + rng.uniform(-6, 6)
        leaves.append((jx, jy, angle))


def clamp_point(x: float, y: float) -> tuple[float, float]:
    return (
        min(max(x, CANVAS_MARGIN), WIDTH - CANVAS_MARGIN),
        min(max(y, CANVAS_MARGIN), HEIGHT - CANVAS_MARGIN),
    )


def clamp_to_side(angle: float, side: int) -> float:
    # side=+1 (right) stays <= vertical+margin; side=-1 (left) stays >= vertical-margin
    if side == 0:
        return angle
    margin = math.radians(SIDE_CROSSOVER_DEG)
    vertical = math.pi / 2
    if side > 0:
        return min(angle, vertical + margin)
    return max(angle, vertical - margin)


def leaf_color(rng: random.Random) -> str:
    if rng.random() < BLOSSOM_CHANCE:
        return BLOSSOM
    return rng.choice(GREENS)


def darken(hex_color: str, factor: float) -> str:
    r = int(hex_color[1:3], 16) * factor
    g = int(hex_color[3:5], 16) * factor
    b = int(hex_color[5:7], 16) * factor
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"


def today_seed() -> tuple[str, int]:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest = hashlib.sha256(date_str.encode()).hexdigest()
    return date_str, int(digest, 16) % (2**31)


def grow(x, y, angle, budget, gen, rng, segments, leaves, side=0, bough_budget=None):
    # side: 0 = trunk, +1 = right bough, -1 = left. bough_budget = that bough's
    # starting budget, for deriving its droop.
    run_len = rng.randint(RUN_MIN, RUN_MAX) if gen > 0 else 1
    draw_angle = angle
    for _ in range(run_len):
        if budget < 6:
            break
        seg_len = min(budget * rng.uniform(*RUN_STEP_FRACTION), budget)
        angle += math.radians(rng.uniform(-RUN_WOBBLE_DEG, RUN_WOBBLE_DEG))
        angle = clamp_to_side(angle, side)

        if side != 0 and bough_budget:
            spent_frac = min(1.0, max(0.0, 1 - budget / bough_budget))
            draw_angle = angle - math.radians(TROPISM_MAX_DEG) * spent_frac * side
        else:
            draw_angle = angle

        stroke_start = max(1.0, math.sqrt(budget) * 0.5)
        stroke_end = max(1.0, math.sqrt(max(budget - seg_len, 0.0)) * 0.5)
        px, py = x, y
        for slice_i in range(1, SEGMENT_SLICES + 1):
            t = slice_i / SEGMENT_SLICES
            sx, sy = clamp_point(x + seg_len * t * math.cos(draw_angle), y - seg_len * t * math.sin(draw_angle))
            width = stroke_start + (stroke_end - stroke_start) * t
            segments.append((px, py, sx, sy, width))
            px, py = sx, sy

        x, y = px, py
        budget -= seg_len

        if gen >= TWIG_LEAF_MIN_GEN and rng.random() < TWIG_LEAF_CHANCE:
            leaves.append((x, y, draw_angle))

    if budget < 6 or gen >= MAX_GENERATIONS:
        add_terminal_cluster(x, y, draw_angle, rng, leaves)
        return

    if gen == 0:
        n_children = 2  # guarantee the trunk splits into a left and right side
    else:
        n_children = choose_children_count(gen, rng)
        if n_children == 0 and gen < MIN_BRANCH_GENERATIONS:
            n_children = 1  # don't let a bough fully stop too early

    if n_children == 0:
        add_terminal_cluster(x, y, draw_angle, rng, leaves)
        return

    # only the trunk's split fans out wide; later splits stay narrower
    spread_deg = rng.uniform(34, 58) if gen == 0 else rng.uniform(24, 42)
    spread = math.radians(spread_deg)

    for i in range(n_children):
        offset = spread * (i - (n_children - 1) / 2) if n_children > 1 else 0.0
        jitter = math.radians(rng.uniform(-8, 8))
        child_angle = angle + offset + jitter

        if gen == 0:
            child_side = 1 if i == 0 else -1  # i == 0 -> right, i == 1 -> left
        else:
            child_side = side
        child_angle = clamp_to_side(child_angle, child_side)

        budget_floor = MAIN_BOUGH_BUDGET_MIN if gen < MIN_BRANCH_GENERATIONS else CHILD_BUDGET_MIN
        child_budget = budget * rng.uniform(budget_floor, CHILD_BUDGET_MAX)
        child_bough_budget = child_budget if gen == 0 else bough_budget
        grow(x, y, child_angle, child_budget, gen + 1, rng, segments, leaves, child_side, child_bough_budget)


def leaf_shape(x: float, y: float, angle: float, rng: random.Random, size_scale: float) -> str:
    fill = leaf_color(rng)
    stroke = darken(fill, LEAF_STROKE_DARKEN)
    opacity = rng.uniform(0.85, 1.0)

    if fill == BLOSSOM:
        r = rng.uniform(6, 9.5) * size_scale
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="0.6" opacity="{opacity:.2f}"/>'
        )

    length = rng.uniform(18, 28) * size_scale
    width = length * rng.uniform(0.6, 0.95)
    jitter_deg = rng.uniform(-25, 25)
    rotate_deg = -math.degrees(angle) + jitter_deg

    path = f"M0,0 Q{length * 0.35:.1f},{-width / 2:.1f} {length:.1f},0 " \
           f"Q{length * 0.35:.1f},{width / 2:.1f} 0,0 Z"
    return (
        f'<path d="{path}" fill="{fill}" stroke="{stroke}" stroke-width="0.8" '
        f'opacity="{opacity:.2f}" transform="translate({x:.1f},{y:.1f}) rotate({rotate_deg:.1f})"/>'
    )


def render(date_str: str, seed: int) -> str:
    rng = random.Random(seed)

    segments: list[tuple[float, float, float, float, float]] = []
    leaves: list[tuple[float, float, float]] = []
    start_budget = rng.uniform(BUDGET_MIN, BUDGET_MAX)
    grow(WIDTH / 2, HEIGHT - 20, math.pi / 2, start_budget, 0, rng, segments, leaves)

    branch_paths = "\n    ".join(
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{TRUNK}" stroke-width="{w:.2f}" stroke-linecap="round"/>'
        for x1, y1, x2, y2, w in segments
    )
    leaf_ys = [y for _, y, _ in leaves]
    top_y, bottom_y = min(leaf_ys), max(leaf_ys)
    y_span = max(bottom_y - top_y, 1e-6)

    def size_scale(y: float) -> float:
        height_frac = 1 - (y - top_y) / y_span
        return MIN_LEAF_SCALE + (MAX_LEAF_SCALE - MIN_LEAF_SCALE) * height_frac

    leaf_shapes = "\n    ".join(
        leaf_shape(x, y, angle, rng, size_scale(y)) for x, y, angle in leaves
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="a fractal tree grown fresh on {date_str}">
  <title>today's tree — {date_str}</title>
  <desc>Recursively branched, seeded by today's date. Regrows daily.</desc>
  <g>
    {branch_paths}
    {leaf_shapes}
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
