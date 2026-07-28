import anthropic
import duckdb
import json

client = anthropic.Anthropic()

# conecta ao DuckDB e carrega os CSVs como tabelas, disponíveis para o agente consultar
con = duckdb.connect()
con.execute("CREATE TABLE clients AS SELECT * FROM read_csv_auto('data/clients.csv')")
con.execute("CREATE TABLE vehicles AS SELECT * FROM read_csv_auto('data/vehicles.csv')")
con.execute("CREATE TABLE rides AS SELECT * FROM read_csv_auto('data/rides.csv')")

def get_full_schema() -> str:
    """Monta a descrição textual do schema real de todas as tabelas.

    Returns:
        String com nome de cada tabela e suas colunas/tipos, para dar
        contexto real ao modelo antes dele escrever qualquer SQL.
    """
    schema_parts = []
    for table in ["clients", "vehicles", "rides"]:
        columns = con.execute(f"DESCRIBE {table}").fetchall()
        cols_desc = ", ".join([f"{col} ({dtype})" for col, dtype, *_ in columns])
        schema_parts.append(f"- {table}: {cols_desc}")
    return "\n".join(schema_parts)

# schema é calculado uma vez e reutilizado — evita o modelo "chutar" nomes de coluna
SCHEMA_CONTEXT = get_full_schema()

# system prompt agora carrega o schema real, então o modelo já escreve SQL correto de primeira
SYSTEM_PROMPT = f"""Você é um agente de dados com acesso a um banco DuckDB.
As tabelas disponíveis e suas colunas reais são:

{SCHEMA_CONTEXT}

Sempre use os nomes de coluna exatamente como descritos acima."""

TOOLS = [
    {
        "name": "run_sql_query",
        "description": "Executa uma query SQL de leitura (SELECT) contra as tabelas "
                        "clients, vehicles e rides, e retorna o resultado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query SQL a ser executada"}
            },
            "required": ["query"],
        },
    }
]

def run_sql_query(query: str) -> str:
    """Executa a query no DuckDB de forma segura, com trava contra escrita."""
    forbidden = ["insert", "update", "delete", "drop", "alter", "create"]
    if any(word in query.lower() for word in forbidden):
        return "Erro: apenas queries de leitura (SELECT) são permitidas."
    try:
        result = con.execute(query).fetchdf()
        return result.to_string(index=False)
    except Exception as e:
        return f"Erro ao executar query: {e}"


def ask_agent(question: str, max_iterations: int = 5) -> str:
    """Envia a pergunta ao modelo, deixando ele decidir se e quando consultar o SQL.

    Args:
        question: pergunta em linguagem natural sobre os dados.
        max_iterations: limite de voltas do loop, para evitar custo/tempo excessivo
            em casos onde o modelo fica tentando sem convergir.

    Returns:
        Resposta final do agente, após o loop de tool use.
    """
    messages = [{"role": "user", "content": question}]

    for _ in range(max_iterations): #better than while True to avoid infinite loops (and infinite cost)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use": #if the model didn't decide to use a tool, we can return the answer and stop the loop
            return response.content[0].text

        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "tool_use": #if the model decided to use a tool, we execute it and add the result to the messages for the next iteration
                print(f"  [agente decidiu rodar SQL]: {block.input['query']}")
                result = run_sql_query(block.input["query"])
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }],
                })

    return "Não consegui responder dentro do limite de tentativas."


if __name__ == "__main__":
    perguntas = [
        "Quantos clientes ativos existem?",
        "Qual o tipo de veículo mais usado nas corridas?",
    ]

    for q in perguntas:
        print(f"\nPergunta: {q}")
        print(f"Resposta: {ask_agent(q)}")