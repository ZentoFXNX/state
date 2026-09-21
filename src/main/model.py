from dataclasses import dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class CostModel:
    operation: str
    target: str
    coefficients: tuple[float, ...]

    def predict(self, *, delta_count: int, affected_groups: int, scale: int) -> float:
        features = _features(delta_count, affected_groups, scale)
        return sum(coefficient * feature for coefficient, feature in zip(self.coefficients, features))


def _features(delta_count: int, affected_groups: int, scale: int) -> tuple[float, ...]:
    return (
        1.0,
        float(delta_count),
        float(affected_groups),
        float(delta_count) * math.log1p(delta_count),
    )


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("calibration matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                current - factor * pivot_value
                for current, pivot_value in zip(augmented[row], augmented[column])
            ]
    return [augmented[row][-1] for row in range(size)]


def _read_rows(path: Path, operation: str, holdout_repetition: int | None = None) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line in input_file:
            row = json.loads(line)
            if (
                row.get("operation") == operation
                and "affected_groups" in row
                and row.get("repetition") != holdout_repetition
            ):
                rows.append(row)
    return rows


def fit_models(
    path: Path, operation: str, holdout_repetition: int | None = None
) -> dict[str, CostModel]:
    rows = _read_rows(path, operation, holdout_repetition)
    if len(rows) < 5:
        raise ValueError("at least five complete calibration rows are required")

    features = [
        _features(row["delta_count"], row["affected_groups"], row["scale"])
        for row in rows
    ]
    matrix = [
        [sum(row[i] * row[j] for row in features) for j in range(4)]
        for i in range(4)
    ]
    models = {}
    for target, field in (
        ("differential", "differential_e2e_ms"),
        ("full", "full_e2e_ms"),
    ):
        vector = [
            sum(row[i] * record[field] for row, record in zip(features, rows))
            for i in range(4)
        ]
        models[target] = CostModel(operation, target, tuple(_solve(matrix, vector)))
    return models


def evaluate_holdout(path: Path, operation: str, holdout_repetition: int = 4) -> dict:
    models = fit_models(path, operation, holdout_repetition)
    rows = _read_rows(path, operation)
    rows = [row for row in rows if row.get("repetition") == holdout_repetition]
    if not rows:
        raise ValueError("holdout repetition has no rows")

    errors = []
    correct = 0
    for row in rows:
        predicted_differential = models["differential"].predict(**{
            "delta_count": row["delta_count"],
            "affected_groups": row["affected_groups"],
            "scale": row["scale"],
        })
        predicted_full = models["full"].predict(**{
            "delta_count": row["delta_count"],
            "affected_groups": row["affected_groups"],
            "scale": row["scale"],
        })
        actual_mode = (
            "DIFFERENTIAL"
            if row["differential_e2e_ms"] < row["full_e2e_ms"]
            else "FULL"
        )
        predicted_mode = (
            "DIFFERENTIAL" if predicted_differential * 1.10 < predicted_full else "FULL"
        )
        correct += predicted_mode == actual_mode
        errors.append(
            abs(predicted_differential - row["differential_e2e_ms"])
            / row["differential_e2e_ms"]
        )
    return {
        "operation": operation,
        "holdout_repetition": holdout_repetition,
        "rows": len(rows),
        "mode_accuracy": correct / len(rows),
        "mean_relative_differential_error": sum(errors) / len(errors),
    }
