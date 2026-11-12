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
from itertools import combinations
from pathlib import Path

from metrics_report import Metric, metric_description, metric_name, reported_metrics

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


def load_series(paths: list[Path]) -> tuple[list[Series], int]:
    values: dict[Metric, dict[str, Value]] = {}
    tools: dict[str, Path] = {}
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            metrics = reported_metrics(data, input_path=path)
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
    series = []
    for metric, observations in sorted(values.items()):
        classified = {tool: classify(value) for tool, value in observations.items()}
        kinds = {kind for kind, _ in classified.values()}
        if "grouped" in kinds:
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
                not (
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


def write_report(paths: list[Path], output: Path, minimum: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    series, tools = load_series(paths)
    comparisons = similarities(series, minimum)
    with PdfPages(output) as pdf:
        text_pages(
            pdf,
            "Reported metrics: distributions and comparisons",
            [
                f"Inputs: {tools} distinct tools; {len(series)} metrics.",
                "Each observation is one reported value for one tool. "
                "Missing values are not interpreted as zero or false.",
                "Numeric pairs use Pearson correlation, ranked from positive to "
                "negative. Boolean pairs use the proportion of matching values. "
                f"Both use only jointly reported tools, with at least {minimum} "
                "tools per pair. Constant numeric series cannot be correlated.",
                "Agreement can be high by chance, especially for imbalanced "
                "boolean values. Correlation is not equivalence or causation.",
                "Publication and repeated-check groups are excluded, as are "
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
        positional = [s for s in series if s.kind != "excluded" and not s.comparable]
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
                textwrap.fill(label(s.metric), 80),
                fontsize=12,
                weight="bold",
                va="top",
            )
            description = (
                f"{metric_description(s.metric)}\n"
                f"Type: {s.kind}; reported: {len(s.values)}/{tools}; "
                f"missing: {tools - len(s.values)}."
            )
            if not s.comparable:
                description += " Positional list entry; excluded from comparisons."
            fig.text(0.08, 0.85, textwrap.fill(description, 90), fontsize=10, va="top")
            if s.kind == "numeric":
                bins = min(30, max(1, math.ceil(math.sqrt(len(s.values)))))
                ax.hist(list(s.values.values()), bins=bins, edgecolor="white")
                ax.set_xlabel("Reported value")
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
    args = parser.parse_args()
    if args.output.suffix.lower() != ".pdf":
        parser.error("output must have a .pdf extension")
    if args.min_overlap < 3:
        parser.error("--min-overlap must be at least 3")
    if any(args.output.resolve() == path.resolve() for path in args.inputs):
        parser.error("output must not overwrite an input file")
    try:
        write_report(args.inputs, args.output, args.min_overlap)
    except ImportError as error:
        print(f"Error: install report dependencies: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
