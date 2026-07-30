"""Camada Silver: aplica regras de qualidade e separa registros válidos dos problemáticos.

Comportamento por on_violation:
  - drop → linha excluída da silver e registrada na quarantine
  - warn → linha permanece na silver, mas também registrada na quarantine para rastreabilidade

A tabela quarantine inclui a coluna `violated_rules` (lista de strings) indicando
exatamente quais regras foram violadas e com qual severidade.
"""

import json
import glob
import os
import duckdb

DB_PATH = "data/mobility.duckdb"
RULES_DIR = "docs"


def load_rules(table_name: str) -> list[dict]:
    """Carrega as regras de qualidade do JSON correspondente à tabela.

    Args:
        table_name: nome da tabela (ex: 'rides').

    Returns:
        Lista de dicts com chaves 'column', 'rule', 'reason' e 'on_violation'.
        Retorna lista vazia se o arquivo não existir.
    """
    path = os.path.join(RULES_DIR, f"quality_rules_{table_name}.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def build_silver_filter(drop_rules: list[dict]) -> str:
    """Monta a cláusula WHERE que mantém apenas linhas que passam em todas as regras drop.

    Args:
        drop_rules: regras com on_violation == 'drop'.

    Returns:
        String SQL para uso em WHERE. Retorna '1=1' se não houver regras drop.
    """
    if not drop_rules:
        return "1=1"
    return " AND ".join(f"({r['rule']})" for r in drop_rules)


def build_quarantine_filter(rules: list[dict]) -> str:
    """Monta a cláusula WHERE que captura linhas que violam qualquer regra (drop ou warn).

    Args:
        rules: todas as regras da tabela.

    Returns:
        String SQL para uso em WHERE.
    """
    return " OR ".join(f"NOT ({r['rule']})" for r in rules)


def build_violated_rules_expr(rules: list[dict]) -> str:
    """Monta a expressão SQL que gera a lista de regras violadas por cada linha.

    Cada elemento da lista resultante tem o formato '[drop] reason' ou '[warn] reason'.

    Args:
        rules: todas as regras da tabela.

    Returns:
        Expressão SQL que produz um array de strings com as violações.
    """
    cases = []
    for r in rules:
        reason = r["reason"].replace("'", "''")
        severity = r["on_violation"]
        cases.append(f"CASE WHEN NOT ({r['rule']}) THEN '[{severity}] {reason}' END")
    return f"list_filter([{', '.join(cases)}], x -> x IS NOT NULL) AS violated_rules"


def apply_rules(con: duckdb.DuckDBPyConnection, table_name: str, rules: list[dict]):
    """Popula silver.<table> e silver.<table>_quarantine a partir de bronze.<table>.

    Args:
        con: conexão DuckDB aberta.
        table_name: nome da tabela sem prefixo de schema.
        rules: lista de regras com on_violation definido.
    """
    drop_rules = [r for r in rules if r.get("on_violation") == "drop"]
    all_rules  = [r for r in rules if r.get("on_violation") in ("drop", "warn")]

    # silver: apenas linhas que passam em todas as regras drop
    silver_filter = build_silver_filter(drop_rules)
    con.execute(f"DROP TABLE IF EXISTS silver.{table_name}")
    con.execute(f"""
        CREATE TABLE silver.{table_name} AS
        SELECT * FROM bronze.{table_name}
        WHERE {silver_filter}
    """)

    # quarantine: linhas que violam qualquer regra (drop ou warn), com detalhes
    if all_rules:
        quarantine_filter  = build_quarantine_filter(all_rules)
        violated_rules_col = build_violated_rules_expr(all_rules)
        con.execute(f"DROP TABLE IF EXISTS silver.{table_name}_quarantine")
        con.execute(f"""
            CREATE TABLE silver.{table_name}_quarantine AS
            SELECT *, {violated_rules_col}
            FROM bronze.{table_name}
            WHERE {quarantine_filter}
        """)
    else:
        # sem regras definidas: quarantine vazia com schema compatível
        con.execute(f"DROP TABLE IF EXISTS silver.{table_name}_quarantine")
        con.execute(f"""
            CREATE TABLE silver.{table_name}_quarantine AS
            SELECT *, []::VARCHAR[] AS violated_rules
            FROM bronze.{table_name}
            WHERE false
        """)


def run():
    """Executa a camada silver para todas as tabelas bronze disponíveis."""
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")

    tables = [
        row[0] for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'bronze'"
        ).fetchall()
    ]

    if not tables:
        print("Nenhuma tabela encontrada em bronze. Rode bronze.py primeiro.")
        con.close()
        return

    for table_name in sorted(tables):
        rules = load_rules(table_name)
        apply_rules(con, table_name, rules)

        n_silver     = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]
        n_quarantine = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}_quarantine").fetchone()[0]
        print(f"  silver.{table_name}: {n_silver} válidos | {n_quarantine} em quarantine")

    con.close()


if __name__ == "__main__":
    print("=== Silver ===")
    run()
