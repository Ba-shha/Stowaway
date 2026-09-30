"""Survival experiment: how much storm can a hidden message survive?

Runs the REAL pipeline (lock -> repair data -> hide -> storm -> receive), so the chart
matches what the app does. The Results tab in app.py calls run_levels() to draw it live.
Run for the official chart:  python -m experiments.survival_curve
"""

import csv
from pathlib import Path

from matplotlib.figure import Figure
from PIL import Image

from stowaway.pipeline import receive, send
from stowaway.storm import damage_image

ROOT = Path(__file__).resolve().parent.parent
SPACE_IMAGE = ROOT / "assets" / "space.png"
MESSAGE = "Stowaway Deep Space Telemetry Data Alpha-7"
PASSWORD = "space-passphrase-2026"
SIZE = 300  # we test on a 300x300 crop of the space image so 100 trials stay quick
# Storm strength = chance that any one bit of the image flips.
LEVELS = [0, 1e-3, 2e-3, 3e-3, 5e-3, 7e-3, 1e-2, 1.5e-2, 2e-2, 3e-2]


def test_image() -> Image.Image:
    """A small crop of the space image with the test message hidden in it."""
    crop = Image.open(SPACE_IMAGE).convert("RGB").crop((0, 0, SIZE, SIZE))
    return send(crop, MESSAGE, PASSWORD)


def survival_point(stego, probability: float, trials: int, seed: int = 0):
    """Storm the image `trials` times. Returns (% recovered with repair, % without repair)."""
    with_repair = without_repair = 0
    for t in range(trials):
        damaged, _ = damage_image(stego, probability, seed=seed + t)  # fixed seeds, so reruns match
        with_repair += receive(damaged, PASSWORD, True) == ("ok", MESSAGE)
        without_repair += receive(damaged, PASSWORD, False) == ("ok", MESSAGE)
    return 100 * with_repair / trials, 100 * without_repair / trials


def run_levels(trials: int = 100, levels=LEVELS):
    """Yield (probability, with_repair_pct, without_repair_pct), one storm level at a time."""
    stego = test_image()
    for i, p in enumerate(levels):
        yield (p, *survival_point(stego, p, trials, seed=i * 100_000))


def make_chart(probs, with_repair, without_repair, trials: int) -> Figure:
    """Dark survival chart. Works for the saved PNG and for the live app."""
    fig = Figure(figsize=(9, 5))
    ax = fig.subplots()
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")
    xs = [p * 100 for p in probs]
    ax.plot(xs, with_repair, "o-", color="#00ffcc", lw=2.5, label="With repair data")
    ax.plot(xs, without_repair, "x--", color="#ff5555", lw=2.5, label="Without repair data")
    ax.set_xlabel("Storm intensity: chance each bit flips (%)", color="white")
    ax.set_ylabel("Messages recovered (%)", color="white")
    ax.set_title(f"Survival rate vs storm intensity ({trials} trials per level)", color="white")
    ax.set_ylim(-5, 105)
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.tick_params(colors="white")
    ax.legend(facecolor="#1a1d24", labelcolor="white")
    for side in ax.spines.values():
        side.set_color("#555")
    return fig


def run_experiment(trials: int = 100):
    rows = []
    print(f"--- Survival experiment: {trials} trials per level, real pipeline ---")
    for p, with_r, without_r in run_levels(trials):
        rows.append((p, with_r, without_r))
        print(f"flip probability {p * 100:5.2f}% | with repair {with_r:5.1f}% | without {without_r:5.1f}%")

    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "results").mkdir(exist_ok=True)
    with open(ROOT / "results" / "survival_curve.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["flip_probability", "with_repair_pct", "without_repair_pct", "trials"])
        writer.writerows((*row, trials) for row in rows)
    probs, with_r, without_r = zip(*rows)
    make_chart(probs, with_r, without_r, trials).savefig(ROOT / "assets" / "survival_curve.png",
                                                        dpi=200, facecolor="#0e1117")
    print("Saved assets/survival_curve.png and results/survival_curve.csv")


if __name__ == "__main__":
    run_experiment()