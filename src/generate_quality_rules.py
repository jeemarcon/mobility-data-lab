import anthropic
import json
import os
import glob
import duckdb

client = anthropic.Anthropic()

SYSTEM_PROMPT = """Você é uma engenheira de dados sênior especialista em qualidade de dados,
trabalhando com pipelines Delta Lake / DLT. Você recebe apenas a estrutura do schema
(nome e tipo de cada coluna) — isso é suficiente para propor regras de qualidade de dados,
não é necessário ver dados de exemplo. Responda sempre e apenas com o JSON solicitado,
sem nenhum texto de introdução ou explicação."""


def discover_tables(data_dir: str = "data") -> dict[str, str]:
    """Descobre tabelas automaticamente a partir dos arquivos CSV em data_dir.

    Args:
        data_dir: pasta onde os CSVs estão.

    Returns:
        Dicionário {nome_da_tabela: caminho_do_csv}.
    """
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    return {os.path.splitext(os.path.basename(f))[0]: f for f in csv_files}


def infer_schema(table_name: str, csv_path: str) -> str:
    """Infere o schema de uma tabela lendo o CSV com DuckDB.

    Args:
        table_name: nome da tabela.
        csv_path: caminho do CSV correspondente.

    Returns:
        Descrição textual do schema (nome da coluna + tipo inferido).
    """
    con = duckdb.connect()
    con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")
    columns = con.execute(f"DESCRIBE {table_name}").fetchall()
    con.close()

    lines = [f"Tabela: {table_name}"]
    lines += [f"- {col}: {dtype}" for col, dtype, *_ in columns]
    return "\n".join(lines)



def generate_rules_for_table(table_name: str, schema: str) -> list[dict]:
    """Gera regras de qualidade de dados para uma tabela a partir do seu schema."""

    user_prompt = f"""Aqui está o schema da tabela:
{schema}

Exemplo do formato esperado (few-shot):
{{"column": "distance_km", "rule": "distance_km >= 0", "reason": "distância não pode ser negativa"}}

Pense passo a passo sobre quais colunas podem ter valores inválidos, inconsistências
entre colunas, ou nulos indevidos.

Responda APENAS com uma lista JSON de regras, no mesmo formato do exemplo.
Não use blocos de código markdown, não use crases, não adicione texto antes ou depois do JSON.
Sua resposta deve começar diretamente com [ e terminar com ]."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0.0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    #print(f"  stop_reason: {response.stop_reason}")
    #print(f"  qtd de content blocks: {len(response.content)}")
    #print(f"  output bruto (repr): {repr(response.content[0].text)[:300]}")

    if response.stop_reason == "max_tokens":
        print(f"⚠️  {table_name}: resposta truncada — aumente max_tokens")

    output = response.content[0].text.strip()
    if output.startswith("```"):
        output = output.split("```")[1]
        if output.startswith("json"):
            output = output[4:]
        output = output.strip()

    return json.loads(output)


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)

    for table_name, csv_path in discover_tables().items():
        print(f"Gerando regras para: {table_name}")
        schema = infer_schema(table_name, csv_path) 
        rules = generate_rules_for_table(table_name, schema)

        output_path = f"docs/quality_rules_{table_name}.json"
        with open(output_path, "w") as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)

        print(f"  → {len(rules)} regras salvas em {output_path}")