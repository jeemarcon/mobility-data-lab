"""Camada Bronze: ingere os CSVs brutos e persiste como tabelas DuckDB sem transformação.

Responsabilidade única: copiar os dados da fonte para o banco, preservando tudo
exatamente como chegou — inclusive registros inválidos.
"""

import duckdb
import glob
import os

DB_PATH = "data/mobility.duckdb"
DATA_DIR = "data"


def load_csv_to_bronze(con: duckdb.DuckDBPyConnection, csv_path: str, table_name: str) -> int:
    """Lê um CSV e salva como tabela no schema bronze do DuckDB.

    Não aplica nenhuma transformação ou validação — bronze é o espelho fiel da fonte.

    Args:
        con: conexão DuckDB aberta.
        csv_path: caminho para o arquivo CSV de origem.
        table_name: nome da tabela destino (sem o prefixo do schema).

    Returns:
        Número de linhas carregadas.
    """
    con.execute(f"DROP TABLE IF EXISTS bronze.{table_name}")
    con.execute(f"""
        CREATE TABLE bronze.{table_name} AS
        SELECT * FROM read_csv_auto('{csv_path}')
    """)
    count = con.execute(f"SELECT COUNT(*) FROM bronze.{table_name}").fetchone()[0]
    return count


def run():
    """Executa a camada bronze: cria o schema e ingere todos os CSVs de DATA_DIR."""
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not csv_files:
        print(f"Nenhum CSV encontrado em '{DATA_DIR}/'")
        return

    for csv_path in sorted(csv_files):
        table_name = os.path.splitext(os.path.basename(csv_path))[0]
        n = load_csv_to_bronze(con, csv_path, table_name)
        print(f"  bronze.{table_name}: {n} linhas carregadas")

    con.close()


if __name__ == "__main__":
    print("=== Bronze ===")
    run()
