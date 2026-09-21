from dataclasses import dataclass
import random


@dataclass(frozen=True)
class InsertBatch:
    rows: list[tuple[int, int, int, float]]
    seed: int


@dataclass(frozen=True)
class MutationBatch:
    rows: list[tuple[int, float]]
    seed: int


def make_insert_batch(*, start_id: int, count: int, seed: int, categories: int = 100) -> InsertBatch:
    generator = random.Random(seed)
    rows = [
        (
            start_id + offset,
            generator.randint(1, 10_000),
            generator.randint(1, categories),
            round(generator.uniform(1.0, 1_000.0), 2),
        )
        for offset in range(count)
    ]
    return InsertBatch(rows=rows, seed=seed)


def base_batch(count: int, seed: int = 42) -> InsertBatch:
    return make_insert_batch(start_id=1, count=count, seed=seed)


def make_mutation_batch(*, count: int, seed: int, operation: str) -> MutationBatch:
    generator = random.Random(seed)
    ids = generator.sample(range(1, 100_001), count)
    if operation == "UPDATE":
        return MutationBatch(
            rows=[(row_id, round(generator.uniform(1.0, 1_000.0), 2)) for row_id in ids],
            seed=seed,
        )
    if operation == "DELETE":
        return MutationBatch(rows=[(row_id, 0.0) for row_id in ids], seed=seed)
    raise ValueError(f"unsupported mutation operation: {operation}")
