import json
import glob
import os
import re


def sanitize_expectation_name(column: str, rule: str) -> str:
    """Gera um nome de expectation válido e legível a partir da coluna e regra.

    Args:
        column: nome da coluna alvo da regra.
        rule: expressão da regra (ex: "distance_km >= 0").

    Returns:
        Nome curto em snake_case para usar como identificador da expectation.
    """
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", column.lower())
    return f"{slug}_valid"


def rules_to_dlt_code(table_name: str, rules: list[dict]) -> str:
    """Converte uma lista de regras (column, rule, reason) em código Python
    usando a sintaxe @dlt.expect_all do Delta Live Tables.

    Args:
        table_name: nome da tabela alvo.
        rules: lista de dicts com chaves "column", "rule", "reason".

    Returns:
        Código Python pronto para colar num pipeline DLT.
    """
    expectations = {}
    for r in rules:
        name = sanitize_expectation_name(r["column"], r["rule"])
        # evita nomes duplicados quando há mais de uma regra pra mesma coluna
        base_name, i = name, 2
        while name in expectations:
            name = f"{base_name}_{i}"
            i += 1
        expectations[name] = r["rule"]

    lines = [
        "import dlt",
        "",
        f"# Expectations geradas a partir de docs/quality_rules_{table_name}.json",
        "EXPECTATIONS = {",
    ]
    for r in rules:
        name = sanitize_expectation_name(r["column"], r["rule"])
        lines.append(f'    "{name}": "{r["rule"]}",  # {r["reason"]}')
    lines.append("}")
    lines.append("")
    lines.append(f'@dlt.table(name="{table_name}_validated")')
    lines.append('@dlt.expect_all(EXPECTATIONS)')
    lines.append(f"def {table_name}_validated():")
    lines.append(f'    return dlt.read("{table_name}_bronze")')

    return "\n".join(lines)


if __name__ == "__main__":
    os.makedirs("src/dlt_pipelines", exist_ok=True)

    for rules_file in glob.glob("docs/quality_rules_*.json"):
        table_name = os.path.basename(rules_file).replace("quality_rules_", "").replace(".json", "")

        with open(rules_file) as f:
            rules = json.load(f)

        code = rules_to_dlt_code(table_name, rules)

        output_path = f"src/dlt_pipelines/{table_name}_expectations.py"
        with open(output_path, "w") as f:
            f.write(code)

        print(f"{table_name}: {len(rules)} expectations → {output_path}")