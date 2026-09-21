from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter

from .config import MainConfig
from .db import (
    alter_stream_mode,
    affected_group_count,
    clear_change_buffers,
    connect,
    copy_rows,
    delete_rows,
    insert_rows,
    refresh_stream,
    reset_source,
    source_row_count,
    stream_rows,
    update_rows,
    runtime_metadata,
)
from .workload import base_batch, make_insert_batch, make_mutation_batch


@dataclass(frozen=True)
class PilotStatus:
    state: str
    reason: str


def check_pilot_readiness(config: MainConfig) -> PilotStatus:
    try:
        with connect(config.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pgtrickle.pgt_stream_tables "
                    "WHERE pgt_name IN ('sales_by_category', 'sales_by_category_full')"
                )
                ready = cursor.fetchone()[0] == 2
        return PilotStatus("ready", "both refresh targets are registered") if ready else PilotStatus(
            "blocked", "both refresh targets are required"
        )
    except Exception as error:
        return PilotStatus("blocked", str(error))


def run_pilot(config: MainConfig) -> list[dict]:
    status = check_pilot_readiness(config)
    if status.state != "ready":
        raise RuntimeError(status.reason)

    records: list[dict] = []
    config.result_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(config.database_url) as connection:
        metadata = runtime_metadata(connection)
        for operation in config.operations:
            for repetition in range(config.repetitions):
                for ratio in config.delta_ratios:
                    reset_source(connection)
                    base = base_batch(config.scale)
                    copy_rows(connection, base.rows)
                    clear_change_buffers(connection)

                    alter_stream_mode(connection, "sales_by_category", "FULL")
                    refresh_stream(connection, "sales_by_category")
                    alter_stream_mode(connection, "sales_by_category", "DIFFERENTIAL")
                    refresh_stream(connection, "sales_by_category_full")

                    delta_count = max(1, round(config.scale * ratio))
                    seed = config.seed_base + repetition
                    if operation == "INSERT":
                        batch = make_insert_batch(
                            start_id=config.scale + 1,
                            count=delta_count,
                            seed=seed,
                        )
                        affected_groups = len({row[2] for row in batch.rows})
                        write_ms = insert_rows(connection, batch.rows)
                    else:
                        batch = make_mutation_batch(
                            count=delta_count,
                            seed=seed,
                            operation=operation,
                        )
                        affected_groups = affected_group_count(
                            connection, [row[0] for row in batch.rows]
                        )
                        write_ms = (
                            update_rows(connection, batch.rows)
                            if operation == "UPDATE"
                            else delete_rows(connection, batch.rows)
                        )

                    differential_started = perf_counter()
                    differential_ms = refresh_stream(connection, "sales_by_category")
                    differential_e2e_ms = write_ms + (
                        perf_counter() - differential_started
                    ) * 1000

                    full_started = perf_counter()
                    full_ms = refresh_stream(connection, "sales_by_category_full")
                    full_e2e_ms = write_ms + (perf_counter() - full_started) * 1000

                    differential_rows = stream_rows(connection, "sales_by_category")
                    full_rows = stream_rows(connection, "sales_by_category_full")
                    if differential_rows != full_rows:
                        raise RuntimeError(
                            f"result mismatch at operation={operation}, "
                            f"ratio={ratio}, repetition={repetition}"
                        )

                    records.append(
                        {
                            "scale": config.scale,
                                                **metadata,
                            "operation": operation,
                            "delta_count": delta_count,
                            "delta_ratio": ratio,
                            "affected_groups": affected_groups,
                            "repetition": repetition,
                            "seed": batch.seed,
                            "write_ms": write_ms,
                            "differential_refresh_ms": differential_ms,
                            "full_refresh_ms": full_ms,
                            "differential_e2e_ms": differential_e2e_ms,
                            "full_e2e_ms": full_e2e_ms,
                            "speedup_e2e": full_e2e_ms / differential_e2e_ms,
                            "source_rows": source_row_count(connection),
                        }
                    )

    with config.result_path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record) + "\n")
    return records
