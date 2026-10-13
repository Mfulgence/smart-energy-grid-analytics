"""One shared look for every chart in the report.

Keeping the styling in one place means all figures use the same colours, fonts
and grid, and each analysis script only has to describe WHAT it plots.

Design choices
    * One measure = one colour. Colour is only used to tell series apart.
    * The three series colours were chosen to stay distinguishable for readers
      with colour-vision deficiency, and every multi-series chart has a legend.
    * Grid lines and axes are light grey so the data stands out.
    * Every axis is labelled with its unit (kWh, kW or %).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")            # draw to files; no window is opened
import matplotlib.pyplot as plt  # noqa: E402

from common import RESULTS_DIR   # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]     # blue, orange, aqua (fixed order)
HIGHLIGHT = "#eb6834"                          # used to emphasise selected marks
MUTED = "#b9b8b2"                              # de-emphasised marks
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 10, "text.color": TEXT,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_SECONDARY, "axes.titlecolor": TEXT,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": TEXT_SECONDARY, "ytick.color": TEXT_SECONDARY,
    "legend.frameon": False, "lines.linewidth": 2,
})


def new_figure(width: float = 10, height: float = 4.5, **kwargs):
    """Create a figure and axes with the shared style."""
    return plt.subplots(figsize=(width, height), **kwargs)


def save(fig, name: str) -> str:
    """Save a figure as results/<name>.png and return the relative path."""
    path = RESULTS_DIR / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Chart saved: results/{name}.png")
    return str(path)
