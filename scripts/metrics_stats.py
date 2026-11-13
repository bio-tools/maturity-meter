#!/usr/bin/env python3
"""Summarize saved ingestion data as metric distributions and comparisons."""

import argparse
import json
import math
import re
import statistics
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

from metrics_report import (
    SUPERLINTER_METRIC,
    Metric,
    category_label,
    metric_description,
    metric_name,
    parse_timestamp,
    reported_metrics,
)

Value = str | int | float | bool


@dataclass
class Series:
    metric: Metric
    kind: str
    values: dict[str, Value]
    reason: str = ""
    comparable: bool = True


def label(metric: Metric) -> str:
    return f"{metric.source}: {metric_name(metric)} [{metric.identifier}]"


def classify(value: Value) -> tuple[str, Value]:
    if isinstance(value, bool):
        return "boolean", value
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return "invalid", value
        return "numeric", value
    if value.strip().lower() in ("true", "false"):
        return "boolean", value.strip().lower() == "true"
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return "grouped", value
    return "categorical", value


def load_series(
    paths: list[Path], as_of: datetime | None = None
) -> tuple[list[Series], int]:
    as_of = as_of or datetime.now(UTC)
    values: dict[Metric, dict[str, Value]] = {}
    tools: dict[str, Path] = {}
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            metrics = reported_metrics(data, input_path=path, as_of=as_of)
            repository = data["request"]["repository"]
            biotools_id = data["request"].get("biotools_id")
            if biotools_id is not None and (
                not isinstance(biotools_id, str) or not biotools_id.strip()
            ):
                raise ValueError("biotools_id must be a non-empty string or null")
            tool = (
                f"bio.tools:{biotools_id.strip().casefold()}"
                if biotools_id
                else f"repository:{repository}"
            )
        except (ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
            raise ValueError(f"{path}: invalid ingestion data: {error}") from error
        if tool in tools:
            raise ValueError(
                f"Duplicate tool {tool} in {tools[tool]} "
                f"and {path}; select one result per tool"
            )
        tools[tool] = path
        for metric, value in metrics.items():
            values.setdefault(metric, {})[tool] = value
    if not values:
        raise ValueError("No reported metrics found in the input files")
    values.setdefault(SUPERLINTER_METRIC, {})
    series = []
    for metric, observations in sorted(values.items()):
        classified = {tool: classify(value) for tool, value in observations.items()}
        kinds = {kind for kind, _ in classified.values()}
        if not kinds:
            kind, reason = "excluded", "No SuperLinter results in the inputs"
        elif (
            kinds == {"grouped"}
            and metric.source == "europe_pmc"
            and metric.identifier == "publication.isOpenAccess"
        ):
            kind, reason = "publication", ""
        elif "grouped" in kinds:
            kind, reason = "excluded", "Contains grouped publication or check values"
        elif "invalid" in kinds:
            kind, reason = "excluded", "Contains a non-finite numeric value"
        elif len(kinds) != 1:
            kind, reason = "excluded", "Contains incompatible value types"
        else:
            kind, reason = kinds.pop(), ""
        series.append(
            Series(
                metric,
                kind,
                {k: v for k, (_, v) in classified.items()},
                reason,
                kind != "publication"
                and not (
                    metric.source == "OpenEBench"
                    and re.search(r"\[\d+\]", metric.identifier)
                ),
            )
        )
    return series, len(tools)


def similarities(
    series: list[Series], minimum: int
) -> dict[str, list[tuple[float, int, Metric, Metric]]]:
    result: dict[str, list[tuple[float, int, Metric, Metric]]] = {
        "numeric": [],
        "boolean": [],
    }
    for left, right in combinations(series, 2):
        if (
            left.kind != right.kind
            or left.kind not in result
            or not left.comparable
            or not right.comparable
        ):
            continue
        shared = sorted(left.values.keys() & right.values.keys())
        if len(shared) < minimum:
            continue
        a = [left.values[key] for key in shared]
        b = [right.values[key] for key in shared]
        if left.kind == "boolean":
            score = sum(x == y for x, y in zip(a, b, strict=True)) / len(shared)
        else:
            try:
                score = statistics.correlation(a, b)
            except statistics.StatisticsError:
                continue
            if not math.isfinite(score):
                continue
        result[left.kind].append((score, len(shared), left.metric, right.metric))
    for pairs in result.values():
        pairs.sort(key=lambda pair: (-pair[0], -pair[1], pair[2], pair[3]))
    return result


def text_pages(pdf, title: str, paragraphs: list[str]) -> None:
    import matplotlib.pyplot as plt

    lines = []
    for paragraph in paragraphs:
        lines.extend(textwrap.wrap(paragraph, width=92) or [""])
        lines.append("")
    for start in range(0, max(1, len(lines)), 42):
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.08, 0.95, title, fontsize=15, weight="bold", va="top")
        fig.text(0.08, 0.90, "\n".join(lines[start : start + 42]), fontsize=9, va="top")
        pdf.savefig(fig)
        plt.close(fig)


def publication_counts(series: Series) -> Counter[str]:
    return Counter(
        str(item["value"])
        for group in series.values.values()
        for item in json.loads(group)
        if isinstance(item, dict) and "value" in item
    )


def summary_value(series: Series) -> str:
    """Summarize a series without combining grouped tool observations."""
    if series.kind == "excluded":
        return f"Excluded: {series.reason}"
    if series.kind == "numeric":
        values = list(series.values.values())
        return (
            f"Median {statistics.median(values):.4g}; "
            f"range {min(values):.4g} to {max(values):.4g}"
        )
    if series.kind == "boolean":
        counts = Counter(series.values.values())
        return f"True {counts[True]}; false {counts[False]}"
    if series.kind == "publication":
        counts = publication_counts(series)
        return "Publication observations: " + ", ".join(
            f"{key} {count}" for key, count in sorted(counts.items())
        )
    counts = Counter(str(value) for value in series.values.values())
    mode, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return f"{len(counts)} distinct; mode {textwrap.shorten(mode, width=35)} ({count})"


def summary_rows(series: list[Series], tools: int) -> list[tuple[str, ...]]:
    """Produce one source-qualified row per metric, including excluded metrics."""
    ordered = sorted(
        series,
        key=lambda s: (
            category_label(s.metric) or "Uncategorized",
            metric_name(s.metric),
            s.metric.source,
            s.metric.identifier,
        ),
    )
    return [
        (
            f"{metric_name(s.metric)}\n[{s.metric.identifier}]",
            s.metric.source,
            category_label(s.metric) or "Uncategorized",
            f"{len(s.values)}/{tools}\n({len(s.values) / tools:.1%})",
            summary_value(s)
            + (
                "; positional, not compared"
                if not s.comparable and s.kind not in ("publication", "excluded")
                else ""
            ),
        )
        for s in ordered
    ]


def summary_pages(pdf, series: list[Series], tools: int, as_of: datetime) -> None:
    """Draw a paginated, source-qualified metric overview."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    widths = (40, 13, 15, 11, 23)
    positions = (0.03, 0.43, 0.55, 0.68, 0.76, 0.97)
    line_height = 0.015
    row_padding = 0.009
    top, bottom = 0.80, 0.07
    max_lines = int((top - bottom - row_padding) / line_height)
    pages: list[list[tuple[list[list[str]], float]]] = [[]]
    remaining = top - bottom
    for row in summary_rows(series, tools):
        cells = [
            [
                line
                for paragraph in text.split("\n")
                for line in (textwrap.wrap(paragraph, width=width) or [""])
            ]
            for text, width in zip(row, widths, strict=True)
        ]
        line_count = max(map(len, cells))
        for start in range(0, line_count, max_lines):
            part = [cell[start : start + max_lines] for cell in cells]
            height = max(map(len, part)) * line_height + row_padding
            if height > remaining and pages[-1]:
                pages.append([])
                remaining = top - bottom
            pages[-1].append((part, height))
            remaining -= height

    for page_number, rows in enumerate(pages, 1):
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax.text(0.03, 0.95, "Metric summary", fontsize=18, weight="bold", va="top")
        ax.text(
            0.03,
            0.90,
            f"{len(series)} source-qualified metrics · {tools} tools · "
            f"Activity reference: {as_of.isoformat()}",
            fontsize=9,
            color="#4b5563",
            va="top",
        )
        ax.text(
            0.03,
            0.86,
            "Coverage counts tools with a value; excluded metrics remain listed. "
            "Publication counts are per observation, not per tool.",
            fontsize=8,
            color="#4b5563",
            va="top",
        )
        ax.add_patch(
            Rectangle(
                (positions[0], top),
                positions[-1] - positions[0],
                0.035,
                facecolor="#243b53",
                edgecolor="none",
            )
        )
        for x, heading in zip(
            positions,
            ("Metric / identifier", "Source", "Category", "Coverage", "Summary"),
            strict=False,
        ):
            ax.text(
                x + 0.004,
                top + 0.0175,
                heading,
                color="white",
                fontsize=8,
                weight="bold",
                va="center",
            )
        y = top
        for index, (cells, height) in enumerate(rows):
            y -= height
            ax.add_patch(
                Rectangle(
                    (positions[0], y),
                    positions[-1] - positions[0],
                    height,
                    facecolor="#f2f6fa" if index % 2 == 0 else "white",
                    edgecolor="#d8e1ea",
                    linewidth=0.3,
                )
            )
            for x, lines in zip(positions, cells, strict=False):
                ax.text(
                    x + 0.004,
                    y + height - 0.004,
                    "\n".join(lines),
                    fontsize=7,
                    va="top",
                    linespacing=1.15,
                )
        ax.text(
            0.97,
            0.025,
            f"Summary {page_number}/{len(pages)}",
            ha="right",
            fontsize=8,
            color="#4b5563",
        )
        pdf.savefig(fig)
        plt.close(fig)


def write_report(
    paths: list[Path], output: Path, minimum: int, as_of: datetime | None = None
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    as_of = as_of or datetime.now(UTC)
    series, tools = load_series(paths, as_of=as_of)
    comparisons = similarities(series, minimum)
    with PdfPages(output) as pdf:
        summary_pages(pdf, series, tools, as_of)
        text_pages(
            pdf,
            "Reported metrics: distributions and comparisons",
            [
                f"Inputs: {tools} distinct tools; {len(series)} metrics.",
                f"Activity calculation reference: {as_of.isoformat()}.",
                "Each observation is one reported value or source-specific "
                "derived indicator for one tool. Missing values "
                "are not interpreted as zero or false.",
                "Numeric pairs use Pearson correlation, ranked from positive to "
                "negative. Boolean pairs use the proportion of matching values. "
                f"Both use only jointly reported tools, with at least {minimum} "
                "tools per pair. Constant numeric series cannot be correlated.",
                "Agreement can be high by chance, especially for imbalanced "
                "boolean values. Correlation is not equivalence or causation.",
                "Grouped publication open-access values are charted per "
                "publication observation, not compared per tool. Other "
                "publication and repeated-check groups are excluded, as are "
                "metrics with mixed types or non-finite values. Categorical "
                "values and positional OpenEBench list entries are charted but "
                "not compared. Different tools may share one repository. "
                "Results reflect the available sample, not all tools.",
            ],
        )
        for kind, heading in (
            ("numeric", "Numeric similarity: Pearson correlation"),
            ("boolean", "Boolean similarity: exact agreement"),
        ):
            pairs = comparisons[kind][:20]
            paragraphs = [
                f"{score:.3f} (n={n}): {label(left)} / {label(right)}"
                for score, n, left, right in pairs
            ]
            text_pages(pdf, heading, paragraphs or ["No eligible pairs."])
        excluded = [s for s in series if s.kind == "excluded"]
        text_pages(
            pdf,
            "Excluded metrics",
            [
                f"{label(s.metric)} — {s.reason} ({len(s.values)} reported tools)"
                for s in excluded
            ]
            or ["No excluded metrics."],
        )
        positional = [
            s
            for s in series
            if s.kind != "excluded" and not s.comparable and s.kind != "publication"
        ]
        text_pages(
            pdf,
            "Excluded from comparison only",
            [
                f"{label(s.metric)} — positional OpenEBench list entry; "
                "positions may represent different observations across tools."
                for s in positional
            ]
            or ["No positional OpenEBench metrics."],
        )
        for s in series:
            if s.kind == "excluded":
                continue
            fig, ax = plt.subplots(figsize=(8.27, 11.69))
            fig.subplots_adjust(left=0.16, right=0.95, bottom=0.22, top=0.72)
            fig.text(
                0.08,
                0.95,
                textwrap.fill(label(s.metric), 62),
                fontsize=12,
                weight="bold",
                va="top",
            )
            description = (
                f"{metric_description(s.metric)} "
                f"Category: {category_label(s.metric) or 'Uncategorized'}.\n"
                f"Type: {s.kind}; reported: {len(s.values)}/{tools}; "
                f"missing: {tools - len(s.values)}."
            )
            if s.kind == "publication":
                description += (
                    " Each bar counts publication observations, not tools; "
                    "excluded from comparisons."
                )
            elif not s.comparable:
                description += " Positional list entry; excluded from comparisons."
            fig.text(0.08, 0.85, textwrap.fill(description, 90), fontsize=10, va="top")
            if s.kind == "numeric":
                bins = min(30, max(1, math.ceil(math.sqrt(len(s.values)))))
                ax.hist(list(s.values.values()), bins=bins, edgecolor="white")
                ax.set_xlabel("Reported value")
            elif s.kind == "publication":
                counts = publication_counts(s)
                ordered = sorted(counts.items())
                ax.barh([value for value, _ in ordered], [n for _, n in ordered])
                ax.invert_yaxis()
                ax.set_xlabel("Number of publication observations")
            else:
                counts = Counter(
                    str(v).lower() if isinstance(v, bool) else v
                    for v in s.values.values()
                )
                ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
                if len(ordered) > 20:
                    ordered = ordered[:19] + [
                        ("Other categories", sum(count for _, count in ordered[19:]))
                    ]
                ax.barh([str(value) for value, _ in ordered], [n for _, n in ordered])
                ax.invert_yaxis()
                ax.set_xlabel("Number of tools")
            if s.kind == "numeric":
                ax.set_ylabel("Number of tools")
            pdf.savefig(fig)
            plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", nargs="+", type=Path, help="Saved --save-data JSON files"
    )
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output PDF")
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=5,
        help="Minimum jointly reported tools for comparison (default: 5)",
    )
    parser.add_argument(
        "--as-of",
        type=parse_timestamp,
        help="Reference ISO timestamp with timezone for activity (default: now)",
    )
    args = parser.parse_args()
    if args.output.suffix.lower() != ".pdf":
        parser.error("output must have a .pdf extension")
    if args.min_overlap < 3:
        parser.error("--min-overlap must be at least 3")
    if any(args.output.resolve() == path.resolve() for path in args.inputs):
        parser.error("output must not overwrite an input file")
    try:
        write_report(args.inputs, args.output, args.min_overlap, args.as_of)
    except ImportError as error:
        print(f"Error: install report dependencies: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
