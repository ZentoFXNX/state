from collections.abc import Iterable
from time import perf_counter

import psycopg
from psycopg import sql


INSERT_SQL = """
INSERT INTO fact_sales (id, customer_id, category_id, amount)
VALUES (%s, %s, %s, %s)
"""
UPDATE_SQL = "UPDATE fact_sales SET amount = %s WHERE id = %s"
DELETE_SQL = "DELETE FROM fact_sales WHERE id = %s"


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)

def runtime_metadata(connection: psycopg.Connection) -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('server_version')")
        postgres_version = cursor.fetchone()[0]
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'pg_trickle'")
        pg_trickle_version = cursor.fetchone()[0]
        cursor.execute("SHOW pg_trickle.differential_max_change_ratio")
        threshold = cursor.fetchone()[0]
    return {
        "postgres_version": postgres_version,
        "pg_trickle_version": pg_trickle_version,
        "differential_max_change_ratio": threshold,
    }


def insert_rows(connection: psycopg.Connection, rows: Iterable[tuple[int, int, int, float]]) -> float:
    started = perf_counter()
    with connection.cursor() as cursor:
        cursor.executemany(INSERT_SQL, rows)
    connection.commit()
    return (perf_counter() - started) * 1000


def copy_rows(connection: psycopg.Connection, rows: Iterable[tuple[int, int, int, float]]) -> float:
    started = perf_counter()
    with connection.cursor() as cursor:
        with cursor.copy(
            "COPY fact_sales (id, customer_id, category_id, amount) FROM STDIN"
        ) as copy:
            for row in rows:
                copy.write_row(row)
    connection.commit()
    return (perf_counter() - started) * 1000


def update_rows(connection: psycopg.Connection, rows: Iterable[tuple[int, float]]) -> float:
    started = perf_counter()
    with connection.cursor() as cursor:
        cursor.executemany(UPDATE_SQL, ((amount, row_id) for row_id, amount in rows))
    connection.commit()
    return (perf_counter() - started) * 1000


def delete_rows(connection: psycopg.Connection, rows: Iterable[tuple[int, float]]) -> float:
    started = perf_counter()
    with connection.cursor() as cursor:
        cursor.executemany(DELETE_SQL, ((row_id,) for row_id, _ in rows))
    connection.commit()
    return (perf_counter() - started) * 1000


def refresh_full(connection: psycopg.Connection) -> float:
    started = perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("REFRESH MATERIALIZED VIEW sales_by_category")
    connection.commit()
    return (perf_counter() - started) * 1000


def source_row_count(connection: psycopg.Connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM fact_sales")
        return cursor.fetchone()[0]


def affected_group_count(connection: psycopg.Connection, row_ids: list[int]) -> int:
    if not row_ids:
        return 0
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(DISTINCT category_id) FROM fact_sales WHERE id = ANY(%s)",
            (row_ids,),
        )
        return cursor.fetchone()[0]


def reset_source(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE fact_sales")
    connection.commit()


def clear_change_buffers(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'pgtrickle_changes'"
        )
        tables = cursor.fetchall()
        for (table_name,) in tables:
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {}.{} ").format(
                    sql.Identifier("pgtrickle_changes"),
                    sql.Identifier(table_name),
                )
            )
    connection.commit()


def refresh_stream(connection: psycopg.Connection, name: str) -> float:
    started = perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pgtrickle.refresh_stream_table(%s)", (name,))
    connection.commit()
    return (perf_counter() - started) * 1000


def alter_stream_mode(connection: psycopg.Connection, name: str, mode: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pgtrickle.alter_stream_table(%s, refresh_mode => %s)",
            (name, mode),
        )
    connection.commit()


def stream_rows(connection: psycopg.Connection, name: str) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT category_id, row_count, total_amount::text "
            f"FROM {name} ORDER BY category_id"
        )
        return cursor.fetchall()
