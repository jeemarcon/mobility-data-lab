import duckdb
import sys

DB_PATH = "data/mobility.duckdb"
SILVER_SCHEMA = "silver_test" if "--test" in sys.argv else "silver"


def detect_anomalies(con: duckdb.DuckDBPyConnection, table: str, column: str) -> str:
    """Detecta outliers numa coluna numérica usando o método IQR.

    Args:
        con: conexão DuckDB já aberta.
        table: nome da tabela a analisar.
        column: coluna numérica a checar.

    Returns:
        Resultado formatado com os registros considerados outliers.
    """
    # calcula os quartis e o limite superior/inferior "normal" via IQR
    query = f"""
    WITH stats AS (
        SELECT
            quantile_cont({column}, 0.25) AS q1,
            quantile_cont({column}, 0.75) AS q3
        FROM {table}
    ),
    bounds AS (
        SELECT
            q1 - 1.5 * (q3 - q1) AS lower_bound,
            q3 + 1.5 * (q3 - q1) AS upper_bound
        FROM stats
    )
    SELECT t.*
    FROM {table} t, bounds b
    WHERE t.{column} < b.lower_bound OR t.{column} > b.upper_bound
    """
    return con.execute(query).fetchdf().to_string(index=False)


if __name__ == "__main__":
    con = duckdb.connect(DB_PATH)

    print(f"[schema: {SILVER_SCHEMA}]")
    print("Outliers em distance_km (rides):")
    print(detect_anomalies(con, f"{SILVER_SCHEMA}.rides", "distance_km"))

    print("\nOutliers em fare (rides):")
    print(detect_anomalies(con, f"{SILVER_SCHEMA}.rides", "fare"))