#!/usr/bin/env python3
"""Bar plots for two metrics from results.ods (sheet "Tool_comparison").

1. "GitHub/GitLab: default branch protected" (combined) -> number of tools with True / False
2. "Lizard: avg ccn"                  -> number of tools per value interval

Usage:
    python plot_metrics.py results.ods [output_dir]

Requires: pandas, odfpy, matplotlib  (pip install pandas odfpy matplotlib)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SHEET = "Tool_comparison"
BRANCH_COL = "GitHub: default branch protected"
GITLAB_BRANCH_COL = "GitLab: default branch protected"
CCN_COL = "Lizard: avg ccn"

# Interval edges for avg CCN (left-closed, right-open). Edit to taste.
CCN_BINS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, np.inf]

BAR_COLOR = "#4C72B0"


def to_bool(v):
    """Normalise True/False stored as bool, 1/0 or text. Returns None if missing."""
    if pd.isna(v):
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        return None
    return bool(v)


def label_bars(ax, bars):
    for b in bars:
        h = b.get_height()
        ax.annotate(
            f"{int(h)}",
            (b.get_x() + b.get_width() / 2, h),
            ha="center",
            va="bottom",
            xytext=(0, 3),
            textcoords="offset points",
            fontsize=9,
        )


def style(ax, title, xlabel):
    ax.set_title(title, fontsize=13, pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Number of tools")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)


def plot_branch_protected(df, out_dir):
    # Combine GitHub and GitLab: each tool lives on one platform, so take
    # whichever value is present (GitHub first, then GitLab).
    gh = df[BRANCH_COL].map(to_bool)
    gl = (
        df[GITLAB_BRANCH_COL].map(to_bool)
        if GITLAB_BRANCH_COL in df
        else pd.Series(None, index=df.index)
    )
    vals = gh.where(gh.notna(), gl)
    n_missing = vals.isna().sum()
    counts = vals.dropna().value_counts().reindex([True, False], fill_value=0)

    fig, ax = plt.subplots(figsize=(5, 4.5))
    bars = ax.bar(
        ["True", "False"], counts.values, color=["#2E9E44", "#D64545"], width=0.6
    )
    label_bars(ax, bars)
    style(ax, "GitHub + GitLab: default branch protected", "Default branch protected")
    ax.set_ylim(0, counts.max() * 1.12)
    if n_missing:
        fig.text(
            0.99,
            0.01,
            f"{n_missing} tools without a value excluded",
            ha="right",
            va="bottom",
            fontsize=8,
            color="gray",
        )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    path = out_dir / "github_default_branch_protected.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(
        f"GitHub + GitLab default branch protected: True={counts[True]}, False={counts[False]}, missing={n_missing} -> {path}"
    )


def plot_avg_ccn(df, out_dir):
    vals = pd.to_numeric(df[CCN_COL], errors="coerce")
    n_missing = vals.isna().sum()
    vals = vals.dropna()

    bins = list(CCN_BINS)
    if vals.min() < bins[0]:  # make sure nothing falls below the first edge
        bins[0] = np.floor(vals.min())
    labels = [
        f"≥{lo:g}" if np.isinf(hi) else f"{lo:g}–{hi:g}"
        for lo, hi in zip(bins[:-1], bins[1:])
    ]
    counts = (
        pd.cut(vals, bins=bins, labels=labels, right=False)
        .value_counts()
        .reindex(labels)
    )

    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(labels, counts.values, color=BAR_COLOR, width=0.8)
    label_bars(ax, bars)
    style(
        ax, "Average cyclomatic complexity", "Average cyclomatic complexity (interval)"
    )
    ax.set_ylim(0, counts.max() * 1.12)
    fig.text(
        0.99,
        0.01,
        f"n = {len(vals)} tools ({n_missing} without a value excluded)",
        ha="right",
        va="bottom",
        fontsize=8,
        color="gray",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    path = out_dir / "lizard_avg_ccn.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"{CCN_COL}: {counts.to_dict()}, missing={n_missing} -> {path}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(src, sheet_name=SHEET, engine="odf")
    plot_branch_protected(df, out_dir)
    plot_avg_ccn(df, out_dir)


if __name__ == "__main__":
    main()
