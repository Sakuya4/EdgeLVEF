"""Generate publication figures from the repository's aggregate results."""
from io import StringIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent
RESULTS = ROOT / "research" / "plax_lvef" / "results"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 10,
    "legend.fontsize": 8, "legend.frameon": False,
    "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "svg.hashsalt": "edgelvef-publication",
    "savefig.dpi": 300, "savefig.bbox": "tight",
})

def save(figure, stem):
    for extension in ("png", "pdf", "svg"):
        target = OUTPUT / f"{stem}.{extension}"
        if extension == "svg":
            buffer = StringIO()
            figure.savefig(buffer, format="svg", facecolor="white", metadata={"Date": None})
            target.write_text(
                "\n".join(line.rstrip() for line in buffer.getvalue().splitlines()) + "\n",
                encoding="utf-8",
            )
        else:
            figure.savefig(target, facecolor="white")
    plt.close(figure)

def backbone_comparison():
    data = pd.read_csv(RESULTS / "backbone_ablation.csv")
    data = data.loc[data.backbone.ne("r2plus1d_18_ensemble")].sort_values("parameters_m")
    names = data.model.tolist()
    selected = np.array([name == "MobileNetV3-Large" for name in names])
    y = np.arange(len(data))
    figure, axes = plt.subplots(1, 2, figsize=(7.1, 3.6), sharey=True)
    colors = ["black" if chosen else "0.75" for chosen in selected]
    bars = axes[0].barh(y, data.parameters_m, color=colors, edgecolor="black", linewidth=0.6)
    axes[0].set_yticks(y, names)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, 14)
    axes[0].set_xlabel("Parameters (millions)")
    axes[0].set_title("(a) Student network size", loc="left")
    for bar, value in zip(bars, data.parameters_m):
        axes[0].text(value + 0.18, bar.get_y() + bar.get_height() / 2,
                     f"{value:.3f}", va="center", fontsize=8)
    axes[1].barh(y - 0.17, data.mae_pp, height=0.31,
                 color=colors, edgecolor="black", linewidth=0.6, label="Overall MAE")
    axes[1].barh(y + 0.17, data.low_ef_mae_pp, height=0.31,
                 color="white", hatch="///", edgecolor="black", linewidth=0.6, label="Low-EF MAE")
    axes[1].set_xlim(0, 9.5)
    axes[1].set_xlabel("LVEF error (percentage points)")
    axes[1].set_title("(b) Same 82-study benchmark", loc="left")
    for index, row in enumerate(data.itertuples()):
        axes[1].text(row.mae_pp + 0.10, index - 0.17, f"{row.mae_pp:.2f}", va="center", fontsize=7)
        axes[1].text(row.low_ef_mae_pp + 0.10, index + 0.17, f"{row.low_ef_mae_pp:.2f}", va="center", fontsize=7)
    axes[1].legend(loc="lower right", bbox_to_anchor=(1, -0.31), ncol=2)
    for axis in axes:
        axis.grid(axis="x", color="0.88", linewidth=0.5)
        axis.set_axisbelow(True)
    figure.tight_layout(w_pad=2)
    save(figure, "student-backbone-comparison")

def error_intervals():
    data = pd.read_csv(RESULTS / "bootstrap_intervals.csv")
    names = ["Teacher ensemble", "MobileNetV3-Large", "EfficientNet-B0"]
    figure, axes = plt.subplots(1, 2, figsize=(7.1, 2.8), sharey=True)
    markers = ["s", "o", "^"]
    for axis, metric, title in zip(axes, ["mae", "low_ef_mae"],
                                   ["(a) Overall EF error", "(b) Low-EF error"]):
        for index, row in enumerate(data.itertuples()):
            mean = getattr(row, metric + "_pp")
            low = getattr(row, metric + "_ci_low")
            high = getattr(row, metric + "_ci_high")
            axis.errorbar(mean, index, xerr=[[mean - low], [high - mean]],
                          fmt=markers[index], color="black", markersize=5,
                          capsize=3, linewidth=1.1)
            axis.text(8.4, index + 0.28, f"{mean:.2f} [{low:.2f}, {high:.2f}]",
                      va="center", fontsize=7, ha="right")
        axis.set_yticks(range(3), names)
        axis.set_xlim(0, 8.7)
        axis.set_ylim(2.6, -0.6)
        axis.set_title(title, loc="left")
        axis.set_xlabel("MAE (percentage points); 95% bootstrap CI")
        axis.grid(axis="x", color="0.88", linewidth=0.5)
    figure.tight_layout(w_pad=2)
    save(figure, "ef-error-intervals")

if __name__ == "__main__":
    backbone_comparison()
    error_intervals()
