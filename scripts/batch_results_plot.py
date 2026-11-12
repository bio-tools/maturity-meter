"""
Coverage analysis of tool-assessment metrics.

Reads the ODS file (sheet 1: metric details, sheet 2: measured metrics per tool),
stores both as pandas DataFrames and produces:
  1. Percentage of tools covered by each metric
  2. Histogram: number of tools per % of indicators covered
  3. The same two plots for each indicator category
  4. Spearman correlation matrices of the measured values: all indicators,
     within each category, and across categories (see correlations())
  5. Plots 1-2 for each metric source, plus a per-source overview
     (see source_coverage())

A metric is "covered" for a tool when the cell has a value (empty = not covered).
Note: a measured value of `false` or 0 counts as covered.

Usage:
    python metric_coverage.py "pre_run 1.ods" [output_dir]
Requires: pandas, matplotlib, odfpy  (pip install pandas matplotlib odfpy)
"""

import json
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BIN_WIDTH = 10  # width (in %) of the coverage bins in the histogram


def load(path):
    metrics = pd.read_excel(path, engine="odf", sheet_name=0)
    tools = pd.read_excel(path, engine="odf", sheet_name=1)
    tools = tools.set_index(tools.columns[0])
    tools.index.name = "Tool"
    # Strip whitespace-only strings so they count as missing
    tools = tools.apply(
        lambda c: c.map(lambda v: np.nan if isinstance(v, str) and not v.strip() else v)
    )
    return metrics, tools


def category_map(metrics):
    """category -> list of metrics. Metrics with several categories
    (e.g. 'Compatibility, Security, Sustainability') are counted in each."""
    out = {}
    for metric, cats in zip(
        metrics["Metric"], metrics["Indicator category"], strict=True
    ):
        for cat in str(cats).split(","):
            out.setdefault(cat.strip(), []).append(metric)
    return dict(sorted(out.items()))


def plot_metric_coverage(covered, title, ax):
    pct = covered.mean(axis=0).mul(100).sort_values()
    ax.barh(pct.index, pct.values, color="#4C72B0")
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of tools covered")
    ax.set_title(title)
    ax.tick_params(axis="y", labelsize=7 if len(pct) > 30 else 9)
    ax.grid(axis="x", alpha=0.3)
    return pct


def plot_tool_coverage(covered, title, ax):
    pct = covered.mean(axis=1).mul(100)
    bins = np.arange(0, 100 + BIN_WIDTH, BIN_WIDTH)
    counts, _ = np.histogram(pct, bins=bins)
    labels = [f"{lo}-{hi}%" for lo, hi in zip(bins[:-1], bins[1:], strict=True)]
    bars = ax.bar(labels, counts, color="#DD8452")
    ax.bar_label(bars, fontsize=8)
    ax.set_xlabel("% of indicators covered")
    ax.set_ylabel("Number of tools")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)
    return pct


def make_plots(covered, name, out_dir):
    slug = re.sub(r"\W+", "_", name).strip("_").lower()
    n = covered.shape[1]

    fig, ax = plt.subplots(figsize=(9, max(3, 0.18 * n + 1.5)))
    metric_pct = plot_metric_coverage(
        covered, f"{name}: % of tools covered by each metric ({n} metrics)", ax
    )
    fig.tight_layout()
    fig.savefig(out_dir / f"{slug}_metric_coverage.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    tool_pct = plot_tool_coverage(
        covered, f"{name}: indicator coverage per tool ({len(covered)} tools)", ax
    )
    fig.tight_layout()
    fig.savefig(out_dir / f"{slug}_tool_coverage.png", dpi=150)
    plt.close(fig)
    return metric_pct, tool_pct


# ---------------------------------------------------------------------------
# Correlation analysis on measured values
# ---------------------------------------------------------------------------
MIN_PAIRS = 10  # minimum number of tools with both values to compute a correlation


def _to_number(v, metric):
    """Convert one cell to a float (NaN if not convertible).
    - True/False and "true"/"false"  -> 1/0
    - numbers / numeric strings       -> float
    - "Y"/"N"                         -> 1/0
    - ISO durations "PT123S"          -> seconds
    - JSON lists [{"value": ...}, ...] (one entry per publication) ->
      sum of values for count metrics, mean otherwise
    Anything else (URLs, dates, free text) -> NaN.
    """
    if isinstance(v, (bool, np.bool_)):
        return float(v)
    if isinstance(v, (int, float, np.number)):
        return float(v)
    if not isinstance(v, str):
        return np.nan
    s = v.strip()
    low = s.lower()
    if low in ("true", "false"):
        return float(low == "true")
    if low in ("y", "n"):
        return float(low == "y")
    m = re.fullmatch(r"PT(\d+(?:\.\d+)?)S", s)
    if m:
        return float(m.group(1))
    if s.startswith("["):
        try:
            vals = [
                _to_number(e.get("value"), metric)
                for e in json.loads(s)
                if isinstance(e, dict)
            ]
        except (ValueError, AttributeError):
            return np.nan
        vals = [x for x in vals if not np.isnan(x)]
        if not vals:
            return np.nan
        return float(np.sum(vals) if "count" in metric.lower() else np.mean(vals))
    try:
        return float(s)
    except ValueError:
        return np.nan


def to_numeric(tools):
    """tools x metrics DataFrame of floats; drops indicators that are unusable
    for correlation (fewer than MIN_PAIRS values, or the same value for every tool)."""
    num = pd.DataFrame(
        {c: tools[c].map(lambda v, c=c: _to_number(v, c)) for c in tools.columns}
    )
    n_values, n_unique = num.notna().sum(), num.nunique()
    reason = pd.Series("", index=num.columns)
    reason[n_values == 0] = "no numeric values (text, URLs, dates)"
    reason[(n_values > 0) & (n_unique <= 1)] = "same value for every tool"
    reason[(n_unique > 1) & (n_values < MIN_PAIRS)] = (
        f"fewer than {MIN_PAIRS} tools measured"
    )
    dropped = reason[reason != ""].sort_index()
    return num.loc[:, reason == ""], dropped


def category_scores(num, cats):
    """Per-tool score for each category: mean percentile rank (0-1) of the tool
    over the category's indicators (ranks make indicators on different scales
    comparable)."""
    ranks = num.rank(pct=True)
    return pd.DataFrame(
        {
            cat: ranks[[c for c in cols if c in ranks]].mean(axis=1)
            for cat, cols in cats.items()
            if any(c in ranks for c in cols)
        }
    )


def plot_corr(corr, title, path):
    n = len(corr)
    cell = 0.6 if n <= 15 else 0.2  # inches per cell; extra room for the long labels
    size = n * cell + 4.5
    fig, ax = plt.subplots(figsize=(size + 1, size))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(n), corr.columns, rotation=90, fontsize=6 if n > 30 else 8)
    ax.set_yticks(range(n), corr.index, fontsize=6 if n > 30 else 8)
    if n <= 15:  # annotate small matrices
        for i in range(n):
            for j in range(n):
                val = corr.iat[i, j]
                if not np.isnan(val):
                    ax.text(
                        j,
                        i,
                        f"{val:.2f}",
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="white" if abs(val) > 0.6 else "black",
                    )
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Spearman ρ")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def correlations(metrics, tools, out_dir):
    out_dir = out_dir / "correlations"
    out_dir.mkdir(parents=True, exist_ok=True)
    num, dropped = to_numeric(tools)
    cats = category_map(metrics)
    corr_kw = dict(method="spearman", min_periods=MIN_PAIRS)

    # 1. All indicators
    corr = num.corr(**corr_kw)
    corr.round(3).to_csv(out_dir / "all_indicators_corr.csv")
    plot_corr(
        corr,
        f"All indicators ({num.shape[1]} usable)",
        out_dir / "all_indicators_corr.png",
    )

    # 2. Within each category
    for cat, cols in cats.items():
        cols = [c for c in cols if c in num.columns]
        if len(cols) < 2:
            print(f"  skipped '{cat}': fewer than 2 usable indicators")
            continue
        slug = re.sub(r"\W+", "_", cat).strip("_").lower()
        c = num[cols].corr(**corr_kw)
        c.round(3).to_csv(out_dir / f"{slug}_corr.csv")
        plot_corr(c, f"{cat} ({len(cols)} indicators)", out_dir / f"{slug}_corr.png")

    # 3. Across categories (on per-tool category scores)
    scores = category_scores(num, cats)
    scores.round(3).to_csv(out_dir / "category_scores.csv")
    c = scores.corr(**corr_kw)
    c.round(3).to_csv(out_dir / "across_categories_corr.csv")
    plot_corr(
        c,
        "Across categories (mean percentile rank per tool)",
        out_dir / "across_categories_corr.png",
    )

    dropped.rename_axis("indicator").rename("reason").to_csv(
        out_dir / "dropped_indicators.csv"
    )
    print(
        f"Correlations: {num.shape[1]} usable indicators, {len(dropped)} dropped. "
        f"Saved to {out_dir.resolve()}"
    )


# ---------------------------------------------------------------------------
# Coverage per metric source (the "Source" column of the first sheet)
# ---------------------------------------------------------------------------
def source_coverage(metrics, covered, out_dir):
    out_dir = out_dir / "by_source"
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = metrics.groupby("Source")["Metric"].apply(list).to_dict()

    # Same two plots as for the categories, one pair per source
    summary_tool = pd.DataFrame(index=covered.index)
    for src, cols in sorted(sources.items(), key=lambda kv: kv[0].lower()):
        cols = [c for c in cols if c in covered.columns]
        _, summary_tool[src] = make_plots(covered[cols], src, out_dir)
    summary_tool.round(1).to_csv(out_dir / "tool_coverage_by_source.csv")

    # Overview: one bar per source
    overview = pd.DataFrame(
        {
            src: {
                "metrics": len(cols),
                "% tools with >=1 metric": covered[cols].any(axis=1).mean() * 100,
                "mean % of source metrics covered": covered[cols].mean(axis=1).mean()
                * 100,
            }
            for src, cols in sources.items()
        }
    ).T.sort_values("% tools with >=1 metric")
    overview.round(1).to_csv(out_dir / "source_overview.csv")

    fig, ax = plt.subplots(figsize=(9, 0.35 * len(overview) + 1.5))
    y = np.arange(len(overview))
    ax.barh(
        y + 0.2,
        overview["% tools with >=1 metric"],
        0.4,
        label="% of tools with at least 1 metric",
        color="#4C72B0",
    )
    ax.barh(
        y - 0.2,
        overview["mean % of source metrics covered"],
        0.4,
        label="mean % of the source's metrics covered",
        color="#DD8452",
    )
    ax.set_yticks(
        y,
        [
            f"{s} ({int(n)})"
            for s, n in zip(overview.index, overview["metrics"], strict=True)
        ],
    )
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of tools")
    ax.set_title("Coverage per metric source (number of metrics in brackets)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "source_overview.png", dpi=150)
    plt.close(fig)
    print(f"Source coverage: {len(sources)} sources. Saved to {out_dir.resolve()}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pre_run 1.ods"
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "coverage_plots")
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics, tools = load(path)
    covered = tools.notna()  # bool DataFrame: tools x metrics
    correlations(metrics, tools, out_dir)

    metric_pct, tool_pct = make_plots(covered, "All indicators", out_dir)
    summary_metric = metric_pct.rename("All indicators").to_frame()
    summary_tool = tool_pct.rename("All indicators").to_frame()

    for cat, cols in category_map(metrics).items():
        cols = [c for c in cols if c in covered.columns]
        m_pct, t_pct = make_plots(covered[cols], cat, out_dir)
        summary_metric[cat] = m_pct
        summary_tool[cat] = t_pct

    summary_metric.round(1).to_csv(out_dir / "metric_coverage.csv")
    summary_tool.round(1).to_csv(out_dir / "tool_coverage.csv")

    source_coverage(metrics, covered, out_dir)
    print(
        f"{len(tools)} tools, {tools.shape[1]} metrics. "
        f"Plots and CSVs saved to {out_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
