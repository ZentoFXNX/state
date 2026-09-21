from collections import defaultdict
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analysis import bootstrap_break_even


COLORS = {"DIFFERENTIAL": "#1769aa", "FULL": "#d1495b"}
OPERATIONS = ("INSERT", "UPDATE", "DELETE")


def _load(path: Path) -> dict[str, dict[float, list[dict]]]:
    rows: dict[str, dict[float, list[dict]]] = defaultdict(lambda: defaultdict(list))
    with path.open(encoding="utf-8") as input_file:
        for line in input_file:
            record = json.loads(line)
            rows[record["operation"]][record["delta_ratio"]].append(record)
    return rows


def _median(values: list[float]) -> float:
    values = sorted(values)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _p95(values: list[float]) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, round(0.95 * (len(values) - 1)))]


def plot_results(input_path: Path, output_dir: Path) -> list[Path]:
    data = _load(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    figure, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    for axis, operation in zip(axes, OPERATIONS):
        ratios = sorted(data[operation])
        differential = [_median([row["differential_e2e_ms"] for row in data[operation][ratio]]) for ratio in ratios]
        full = [_median([row["full_e2e_ms"] for row in data[operation][ratio]]) for ratio in ratios]
        differential_p95 = [_p95([row["differential_e2e_ms"] for row in data[operation][ratio]]) for ratio in ratios]
        full_p95 = [_p95([row["full_e2e_ms"] for row in data[operation][ratio]]) for ratio in ratios]
        x = [ratio * 100 for ratio in ratios]
        axis.plot(x, differential, marker="o", label="DIFFERENTIAL", color=COLORS["DIFFERENTIAL"])
        axis.plot(x, full, marker="o", label="FULL", color=COLORS["FULL"])
        axis.fill_between(x, differential, differential_p95, color=COLORS["DIFFERENTIAL"], alpha=0.12)
        axis.fill_between(x, full, full_p95, color=COLORS["FULL"], alpha=0.12)
        axis.set_title(operation)
        axis.set_xlabel("Доля изменений, %")
        axis.set_yscale("log")
        axis.grid(True, alpha=0.25)
    axes[0].set_ylabel("End-to-end latency, ms (log scale)")
    axes[-1].legend()
    figure.suptitle("pg_trickle: DIFFERENTIAL против FULL")
    figure.tight_layout()
    path = output_dir / "latency.png"
    figure.savefig(path, dpi=180)
    plt.close(figure)
    created.append(path)

    figure, axis = plt.subplots(figsize=(9, 5))
    for operation in OPERATIONS:
        ratios = sorted(data[operation])
        speedups = [
            _median([row["speedup_e2e"] for row in data[operation][ratio]])
            for ratio in ratios
        ]
        axis.plot([ratio * 100 for ratio in ratios], speedups, marker="o", label=operation)
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1, label="break-even")
    axis.axvline(15.0, color="#777777", linestyle=":", linewidth=1.5, label="GUC 15%")
    axis.set_xlabel("Доля изменений, %")
    axis.set_ylabel("Speedup = FULL / DIFFERENTIAL")
    axis.set_title("Speedup и порог выбора режима")
    axis.grid(True, alpha=0.25)
    axis.legend()
    figure.tight_layout()
    path = output_dir / "speedup.png"
    figure.savefig(path, dpi=180)
    plt.close(figure)
    created.append(path)

    figure, axis = plt.subplots(figsize=(9, 5))
    estimates = []
    estimate_values = []
    for index, operation in enumerate(OPERATIONS):
        interval = bootstrap_break_even(input_path, operation)
        if interval["median"] is None:
            continue
        lower = interval["lower"]
        upper = interval["upper"]
        median = interval["median"]
        axis.errorbar(
            index,
            median * 100,
            yerr=[[median * 100 - lower * 100], [upper * 100 - median * 100]],
            fmt="o",
            capsize=5,
            label=operation,
        )
        estimates.append(median)
        estimate_values.append(median * 100)
        axis.annotate(
            f"{median * 100:.3f}%",
            (index, median * 100),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=9,
        )
    if estimate_values:
        axis.plot(
            range(len(estimate_values)),
            estimate_values,
            color="#333333",
            linewidth=1.5,
            marker="o",
            markerfacecolor="white",
            markeredgecolor="#333333",
            label="оценка r*",
            zorder=2,
        )
    axis.axhline(15.0, color="#777777", linestyle=":", label="GUC 15%")
    axis.set_xticks(range(len(OPERATIONS)), OPERATIONS)
    axis.set_ylabel("Break-even ratio, %")
    axis.set_title("Break-even point с bootstrap 95% CI")
    axis.set_yscale("log")
    axis.set_ylim(0.3, 20)
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    path = output_dir / "break_even.png"
    figure.savefig(path, dpi=180)
    plt.close(figure)
    created.append(path)
    return created
