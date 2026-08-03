"""Camada Bronze: ingere os CSVs brutos e persiste como tabelas DuckDB sem transformação.

Responsabilidade única: copiar os dados da fonte para o banco, preservando tudo
exatamente como chegou — inclusive registros inválidos.
"""

import duckdb
import glob
import os
import sys

DB_PATH = "data/mobility.duckdb"

# --test troca a pasta de origem E o schema de destino, sem tocar nos dados de produção
USE_TEST_DATA = "--test" in sys.argv
DATA_DIR = "tests/data" if USE_TEST_DATA else "data"
SCHEMA = "bronze_test" if USE_TEST_DATA else "bronze"

def load_csv_to_bronze(con: duckdb.DuckDBPyConnection, csv_path: str, table_name: str) -> int:
    """Lê um CSV e salva como tabela no schema bronze (ou bronze_test) do DuckDB.

    Não aplica nenhuma transformação ou validação — bronze é o espelho fiel da fonte.

    Args:
        con: conexão DuckDB aberta.
        csv_path: caminho para o arquivo CSV de origem.
        table_name: nome da tabela destino (sem o prefixo do schema).
        schema: schema de destino — "bronze" para produção, "bronze_test" para testes.

    Returns:
        Número de linhas carregadas.
    """
    con.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table_name}")

    if USE_TEST_DATA:
        # busca o schema da tabela de produção para guiar os TRY_CASTs
        # assim valores inválidos viram NULL em vez de mudar o tipo da coluna inteira
        try:
            prod_cols = con.execute(f"DESCRIBE bronze.{table_name}").fetchall()
            casts = ", ".join(f"TRY_CAST({col} AS {dtype}) AS {col}" for col, dtype, *_ in prod_cols)
            source = f"SELECT {casts} FROM read_csv_auto('{csv_path}', all_varchar=true)"
        except Exception:
            # tabela de produção não existe ainda: carrega sem cast
            source = f"SELECT * FROM read_csv_auto('{csv_path}')"
    else:
        source = f"SELECT * FROM read_csv_auto('{csv_path}')"

    con.execute(f"CREATE TABLE {SCHEMA}.{table_name} AS {source}")
    count = con.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table_name}").fetchone()[0]
    return count


def run():
    """Executa a camada bronze: cria o schema e ingere todos os CSVs de DATA_DIR."""
    con = duckdb.connect(DB_PATH)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not csv_files:
        print(f"Nenhum CSV encontrado em '{DATA_DIR}/'")
        return

    for csv_path in sorted(csv_files):
        table_name = os.path.splitext(os.path.basename(csv_path))[0]
        n = load_csv_to_bronze(con, csv_path, table_name)
        print(f"  {SCHEMA}.{table_name}: {n} linhas carregadas")

    con.close()


if __name__ == "__main__":
    print("=== Bronze ===")
    run()
