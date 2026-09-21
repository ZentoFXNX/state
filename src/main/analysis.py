import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import median


def p95(values: list[float]) -> float:
    if not values:
        raise ValueError("p95 requires at least one value")
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float]:
    return {"median_ms": median(values), "p95_ms": p95(values)}


def analyze_jsonl(path: Path) -> list[dict]:
    groups: dict[tuple[str, float], list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8") as input_file:
        for line in input_file:
            record = json.loads(line)
            groups[(record.get("operation", "INSERT"), record["delta_ratio"])].append(record)

    summary = []
    for (operation, ratio), records in sorted(groups.items()):
        differential = [record["differential_e2e_ms"] for record in records]
        full = [record["full_e2e_ms"] for record in records]
        differential_median = median(differential)
        full_median = median(full)
        summary.append(
            {
                "delta_ratio": ratio,
                "operation": operation,
                "differential_median_ms": differential_median,
                "differential_p95_ms": p95(differential),
                "full_median_ms": full_median,
                "full_p95_ms": p95(full),
                "speedup_median": full_median / differential_median,
            }
        )
    return summary


def first_full_better(summary: list[dict]) -> float | None:
    for row in summary:
        if row["speedup_median"] < 1:
            return row["delta_ratio"]
    return None


def estimated_break_even(summary: list[dict]) -> float | None:
    ordered = sorted(summary, key=lambda row: row["delta_ratio"])
    for previous, current in zip(ordered, ordered[1:]):
        previous_gap = previous["differential_median_ms"] - previous["full_median_ms"]
        current_gap = current["differential_median_ms"] - current["full_median_ms"]
        if previous_gap <= 0 < current_gap:
            fraction = -previous_gap / (current_gap - previous_gap)
            return previous["delta_ratio"] + fraction * (
                current["delta_ratio"] - previous["delta_ratio"]
            )
    return None


def bootstrap_break_even(
    path: Path,
    operation: str,
    iterations: int = 2000,
    seed: int = 20260919,
) -> dict[str, float | None]:
    records = []
    with path.open(encoding="utf-8") as input_file:
        for line in input_file:
            record = json.loads(line)
            if record.get("operation") == operation:
                records.append(record)
    by_ratio: dict[float, list[dict]] = defaultdict(list)
    for record in records:
        by_ratio[record["delta_ratio"]].append(record)
    generator = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        sampled = []
        for ratio, rows in by_ratio.items():
            sampled.extend(generator.choices(rows, k=len(rows)))
        summary = analyze_records(sampled)
        estimate = estimated_break_even(summary)
        if estimate is not None:
            estimates.append(estimate)
    if not estimates:
        return {"operation": operation, "samples": 0, "lower": None, "median": None, "upper": None}
    estimates.sort()
    return {
        "operation": operation,
        "samples": len(estimates),
        "lower": estimates[int(0.025 * len(estimates))],
        "median": estimates[int(0.50 * len(estimates))],
        "upper": estimates[min(len(estimates) - 1, int(0.975 * len(estimates)))],
    }


def analyze_records(records: list[dict]) -> list[dict]:
    groups: dict[float, list[dict]] = defaultdict(list)
    for record in records:
        groups[record["delta_ratio"]].append(record)
    summary = []
    for ratio, rows in sorted(groups.items()):
        differential = sorted(row["differential_e2e_ms"] for row in rows)
        full = sorted(row["full_e2e_ms"] for row in rows)
        differential_median = median(differential)
        full_median = median(full)
        summary.append(
            {
                "delta_ratio": ratio,
                "operation": rows[0].get("operation", "INSERT"),
                "differential_median_ms": differential_median,
                "full_median_ms": full_median,
            }
        )
    return summary
