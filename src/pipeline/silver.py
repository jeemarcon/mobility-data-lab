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
import sys

DB_PATH = "data/mobility.duckdb"
RULES_DIR = "docs"

# --test aponta para os schemas gerados por "bronze.py --test", sem tocar nos dados de produção
USE_TEST_DATA = "--test" in sys.argv
BRONZE_SCHEMA = "bronze_test" if USE_TEST_DATA else "bronze"
SILVER_SCHEMA = "silver_test" if USE_TEST_DATA else "silver"

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


def build_uniqueness_cte(table: str, uniqueness_rules: list[dict]) -> tuple[str, list[str]]:
    """Gera um CTE que adiciona colunas de contagem para cada regra de unicidade.

    Usa COUNT(*) OVER (PARTITION BY col) — window function que conta quantas vezes
    cada valor aparece na tabela, sem precisar de subquery correlacionada.

    Args:
        table: referência completa da tabela fonte (ex: 'bronze.rides').
        uniqueness_rules: regras com type == 'uniqueness'.

    Returns:
        Tupla (cte_sql, count_columns) onde count_columns são os aliases gerados,
        usados depois nos filtros WHERE.
    """
    count_cols = [f"_uniq_{r['column']}" for r in uniqueness_rules]
    select_exprs = ", ".join(
        f"COUNT(*) OVER (PARTITION BY {r['column']}) AS _uniq_{r['column']}"
        for r in uniqueness_rules
    )
    cte = f"WITH _base AS (SELECT *, {select_exprs} FROM {table})"
    return cte, count_cols


def build_silver_filter(drop_rules: list[dict], uniqueness_rules: list[dict]) -> str:
    """Monta a cláusula WHERE que mantém apenas linhas que passam em todas as regras drop.

    Regras row-level usam a expressão SQL diretamente; regras de unicidade usam
    as colunas de contagem geradas pelo CTE (_uniq_<col> = 1).

    Args:
        drop_rules: regras row-level com on_violation == 'drop'.
        uniqueness_rules: regras com type == 'uniqueness' e on_violation == 'drop'.

    Returns:
        String SQL para uso em WHERE. Retorna '1=1' se não houver regras drop.
    """
    conditions = [f"({r['rule']})" for r in drop_rules]
    conditions += [f"(_uniq_{r['column']} = 1)" for r in uniqueness_rules]
    return " AND ".join(conditions) if conditions else "1=1"


def build_quarantine_filter(rules: list[dict], uniqueness_rules: list[dict]) -> str:
    """Monta a cláusula WHERE que captura linhas que violam qualquer regra (drop ou warn).

    Args:
        rules: regras row-level de qualquer severidade.
        uniqueness_rules: regras de unicidade de qualquer severidade.

    Returns:
        String SQL para uso em WHERE.
    """
    conditions = [f"NOT ({r['rule']})" for r in rules]
    conditions += [f"(_uniq_{r['column']} > 1)" for r in uniqueness_rules]
    return " OR ".join(conditions)


def build_violated_rules_expr(rules: list[dict], uniqueness_rules: list[dict]) -> str:
    """Monta a expressão SQL que gera a lista de regras violadas por cada linha.

    Cada elemento tem o formato '[drop] reason' ou '[warn] reason'.

    Args:
        rules: regras row-level.
        uniqueness_rules: regras de unicidade (usam coluna _uniq_ gerada pelo CTE).

    Returns:
        Expressão SQL que produz um array de strings com as violações.
    """
    cases = []
    for r in rules:
        reason = r["reason"].replace("'", "''")
        severity = r["on_violation"]
        cases.append(f"CASE WHEN NOT ({r['rule']}) THEN '[{severity}] {reason}' END")
    for r in uniqueness_rules:
        reason = r["reason"].replace("'", "''")
        severity = r["on_violation"]
        cases.append(f"CASE WHEN _uniq_{r['column']} > 1 THEN '[{severity}] {reason}' END")
    return f"list_filter([{', '.join(cases)}], x -> x IS NOT NULL) AS violated_rules"


def apply_rules(con: duckdb.DuckDBPyConnection, table_name: str, rules: list[dict],
                 bronze_schema: str, silver_schema: str):
    """Popula silver.<table> e silver.<table>_quarantine a partir de bronze.<table>.

    Regras com type='uniqueness' são tratadas via window function em CTE;
    as demais são predicados row-level aplicados diretamente no WHERE.

    Args:
        con: conexão DuckDB aberta.
        table_name: nome da tabela sem prefixo de schema.
        rules: lista de regras com on_violation (e opcionalmente type) definidos.
    """
    uniqueness_rules = [r for r in rules if r.get("type") == "uniqueness"]
    row_rules        = [r for r in rules if r.get("type") != "uniqueness"]

    drop_row_rules  = [r for r in row_rules if r.get("on_violation") == "drop"]
    drop_uniq_rules = [r for r in uniqueness_rules if r.get("on_violation") == "drop"]
    all_row_rules   = [r for r in row_rules if r.get("on_violation") in ("drop", "warn")]
    all_uniq_rules  = [r for r in uniqueness_rules if r.get("on_violation") in ("drop", "warn")]
    has_rules       = bool(all_row_rules or all_uniq_rules)

    # CTE necessário apenas quando há regras de unicidade
    if uniqueness_rules:
        cte, _ = build_uniqueness_cte(f"{bronze_schema}.{table_name}", uniqueness_rules)
        source = "_base"
        # EXCLUDE remove as colunas temporárias _uniq_* do resultado final
        exclude = ", ".join(f"_uniq_{r['column']}" for r in uniqueness_rules)
        select_cols = f"* EXCLUDE ({exclude})"
    else:
        cte, source, select_cols = "", f"{bronze_schema}.{table_name}", "*"

    # CREATE TABLE ... AS <cte> SELECT ... — o CTE fica dentro do AS, não antes
    def as_query(select: str, source_: str, where: str) -> str:
        body = f"SELECT {select} FROM {source_} WHERE {where}"
        return f"{cte}\n{body}" if cte else body

    silver_filter = build_silver_filter(drop_row_rules, drop_uniq_rules)
    con.execute(f"DROP TABLE IF EXISTS {silver_schema}.{table_name}")
    con.execute(f"CREATE TABLE {silver_schema}.{table_name} AS {as_query(select_cols, source, silver_filter)}")

    con.execute(f"DROP TABLE IF EXISTS {silver_schema}.{table_name}_quarantine")
    if has_rules:
        quarantine_filter  = build_quarantine_filter(all_row_rules, all_uniq_rules)
        violated_rules_col = build_violated_rules_expr(all_row_rules, all_uniq_rules)
        con.execute(
            f"CREATE TABLE {silver_schema}.{table_name}_quarantine AS "
            f"{as_query(f'{select_cols}, {violated_rules_col}', source, quarantine_filter)}"
        )
    else:
        con.execute(f"""
            CREATE TABLE {silver_schema}.{table_name}_quarantine AS
            SELECT *, []::VARCHAR[] AS violated_rules
            FROM {bronze_schema}.{table_name}
            WHERE false
        """)


def run():
    """Executa a camada silver para todas as tabelas bronze disponíveis."""
    con = duckdb.connect(DB_PATH)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {SILVER_SCHEMA}")

    tables = [
        row[0] for row in con.execute(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{BRONZE_SCHEMA}'"
        ).fetchall()
    ]

    if not tables:
        print(f"Nenhuma tabela encontrada em {BRONZE_SCHEMA}. Rode bronze.py primeiro.")
        con.close()
        return

    for table_name in sorted(tables):
        rules = load_rules(table_name)
        apply_rules(con, table_name, rules, BRONZE_SCHEMA, SILVER_SCHEMA)

        n_silver     = con.execute(f"SELECT COUNT(*) FROM {SILVER_SCHEMA}.{table_name}").fetchone()[0]
        n_quarantine = con.execute(f"SELECT COUNT(*) FROM {SILVER_SCHEMA}.{table_name}_quarantine").fetchone()[0]
        print(f"  {SILVER_SCHEMA}.{table_name}: {n_silver} válidos | {n_quarantine} em quarantine")

    con.close()


if __name__ == "__main__":
    print("=== Silver ===")
    run()
