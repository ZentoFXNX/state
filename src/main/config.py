from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class MainConfig:
    database_url: str = "postgresql://experiment:experiment@localhost:5433/experiment"
    scale: int = 100_000
    delta_ratios: tuple[float, ...] = (0.001, 0.002, 0.003, 0.004, 0.005, 0.007, 0.01)
    repetitions: int = 5
    seed_base: int = 1000
    operations: tuple[str, ...] = ("INSERT", "UPDATE", "DELETE")
    result_path: Path = PROJECT_ROOT / "results" / "pilot.jsonl"
