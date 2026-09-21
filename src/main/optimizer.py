from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class RefreshDecision:
    operation: str
    delta_ratio: float
    predicted_differential_ms: float
    predicted_full_ms: float
    mode: str
    reason: str


def load_calibration(path: Path, operation: str) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line in input_file:
            row = json.loads(line)
            if row.get("operation", "INSERT") == operation:
                rows.append(row)
    return sorted(rows, key=lambda row: row["delta_ratio"])


def _interpolate(rows: list[dict], ratio: float, field: str) -> float:
    if not rows:
        raise ValueError("calibration data is empty")
    if ratio <= rows[0]["delta_ratio"]:
        return rows[0][field]
    if ratio >= rows[-1]["delta_ratio"]:
        return rows[-1][field]
    for left, right in zip(rows, rows[1:]):
        if left["delta_ratio"] <= ratio <= right["delta_ratio"]:
            span = right["delta_ratio"] - left["delta_ratio"]
            weight = (ratio - left["delta_ratio"]) / span
            return left[field] + weight * (right[field] - left[field])
    raise ValueError(f"cannot interpolate ratio={ratio}")


def choose_mode(
    path: Path,
    *,
    operation: str,
    delta_ratio: float,
    safety_margin: float = 0.10,
) -> RefreshDecision:
    rows = load_calibration(path, operation)
    differential = _interpolate(rows, delta_ratio, "differential_e2e_ms")
    full = _interpolate(rows, delta_ratio, "full_e2e_ms")
    if differential * (1 + safety_margin) < full:
        mode = "DIFFERENTIAL"
        reason = "predicted differential cost is below full cost with safety margin"
    else:
        mode = "FULL"
        reason = "predicted advantage is insufficient for safety margin"
    return RefreshDecision(
        operation=operation,
        delta_ratio=delta_ratio,
        predicted_differential_ms=differential,
        predicted_full_ms=full,
        mode=mode,
        reason=reason,
    )
