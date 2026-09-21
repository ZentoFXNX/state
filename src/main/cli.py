import argparse

from .config import MainConfig
from .db import connect
from .analysis import analyze_jsonl, bootstrap_break_even, estimated_break_even, first_full_better
from .runner import run_pilot
from .optimizer import choose_mode
from .model import evaluate_holdout, fit_models
from .plotting import plot_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pg_trickle break-even study")
    parser.add_argument(
        "command", choices=("status", "pilot", "analyze", "decide", "fit-model", "evaluate", "bootstrap", "plot"), nargs="?", default="status"
    )
    parser.add_argument("--operation", choices=("INSERT", "UPDATE", "DELETE"), default="INSERT")
    parser.add_argument("--delta-ratio", type=float, default=0.004)
    args = parser.parse_args()
    config = MainConfig()

    if args.command == "status":
        print("python environment: ready")
        print(f"scale: {config.scale}")
        print(f"delta ratios: {config.delta_ratios}")
        try:
            with connect(config.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT extversion FROM pg_extension "
                        "WHERE extname = 'pg_trickle'"
                    )
                    extension = cursor.fetchone()
                    cursor.execute(
                        "SELECT pgt_name, refresh_mode, status "
                        "FROM pgtrickle.pgt_stream_tables"
                    )
                    streams = cursor.fetchall()
            print(f"pg_trickle: {extension[0] if extension else 'missing'}")
            print(f"stream tables: {streams}")
        except Exception as error:
            print(f"database: unavailable ({error})")
        return

    if args.command == "pilot":
        records = run_pilot(config)
        print(f"pilot records: {len(records)}")
        print(f"results: {config.result_path}")
        return

    if args.command == "decide":
        decision = choose_mode(
            config.result_path,
            operation=args.operation,
            delta_ratio=args.delta_ratio,
        )
        print(decision)
        return

    if args.command == "fit-model":
        models = fit_models(config.result_path, args.operation)
        for name, model in models.items():
            print(f"{args.operation} {name}: {model.coefficients}")
        return

    if args.command == "evaluate":
        print(evaluate_holdout(config.result_path, args.operation))
        return

    if args.command == "bootstrap":
        print(bootstrap_break_even(config.result_path, args.operation))
        return

    if args.command == "plot":
        output_dir = config.result_path.parent / "plots"
        paths = plot_results(config.result_path, output_dir)
        for path in paths:
            print(path)
        return

    summary = analyze_jsonl(config.result_path)
    for row in summary:
        print(row)
    for operation in sorted({row["operation"] for row in summary}):
        operation_summary = [row for row in summary if row["operation"] == operation]
        print(f"{operation} first_full_better_ratio: {first_full_better(operation_summary)}")
        print(f"{operation} estimated_break_even_ratio: {estimated_break_even(operation_summary)}")
