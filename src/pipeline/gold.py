"""Camada Gold: agrega dados da silver em visões analíticas prontas para consumo.

Todas as tabelas gold são construídas exclusivamente a partir da silver
(dados já validados), nunca da bronze.

Tabelas geradas:
  - gold.revenue_by_client      → total de corridas e receita por cliente
  - gold.rides_by_vehicle_type  → volume e receita por tipo de veículo
"""

import duckdb

DB_PATH = "data/mobility.duckdb"


def build_revenue_by_client(con: duckdb.DuckDBPyConnection):
    """Agrega corridas e receita por cliente, enriquecido com nome e cidade da silver.clients.

    Útil para identificar clientes de maior valor (LTV) e padrões de uso por perfil.
    """
    con.execute("DROP TABLE IF EXISTS gold.revenue_by_client")
    con.execute("""
        CREATE TABLE gold.revenue_by_client AS
        SELECT
            r.client_id,
            c.name                        AS client_name,
            c.city,
            c.is_active,
            COUNT(*)                      AS total_rides,
            ROUND(SUM(r.fare), 2)         AS total_revenue,
            ROUND(AVG(r.fare), 2)         AS avg_fare,
            ROUND(AVG(r.distance_km), 2)  AS avg_distance_km,
            MIN(r.start_time)             AS first_ride,
            MAX(r.start_time)             AS last_ride
        FROM silver.rides r
        LEFT JOIN silver.clients c ON r.client_id = c.client_id
        GROUP BY r.client_id, c.name, c.city, c.is_active
        ORDER BY total_revenue DESC
    """)


def build_rides_by_vehicle_type(con: duckdb.DuckDBPyConnection):
    """Agrega corridas e receita por tipo de veículo, com métricas de distância e duração.

    Útil para comparar desempenho operacional entre categorias da frota.
    """
    con.execute("DROP TABLE IF EXISTS gold.rides_by_vehicle_type")
    con.execute("""
        CREATE TABLE gold.rides_by_vehicle_type AS
        SELECT
            v.type                                                   AS vehicle_type,
            COUNT(*)                                                 AS total_rides,
            ROUND(SUM(r.fare), 2)                                    AS total_revenue,
            ROUND(AVG(r.fare), 2)                                    AS avg_fare,
            ROUND(AVG(r.distance_km), 2)                             AS avg_distance_km,
            ROUND(AVG(EPOCH(r.end_time - r.start_time) / 60.0), 1)  AS avg_duration_min
        FROM silver.rides r
        LEFT JOIN silver.vehicles v ON r.vehicle_id = v.vehicle_id
        GROUP BY v.type
        ORDER BY total_rides DESC
    """)


def run():
    """Executa a camada gold: cria o schema e popula todas as tabelas agregadas."""
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")

    build_revenue_by_client(con)
    n = con.execute("SELECT COUNT(*) FROM gold.revenue_by_client").fetchone()[0]
    print(f"  gold.revenue_by_client: {n} clientes")

    build_rides_by_vehicle_type(con)
    n = con.execute("SELECT COUNT(*) FROM gold.rides_by_vehicle_type").fetchone()[0]
    print(f"  gold.rides_by_vehicle_type: {n} tipos de veículo")

    con.close()


if __name__ == "__main__":
    print("=== Gold ===")
    run()
