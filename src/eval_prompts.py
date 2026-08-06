import anthropic
import json
import time
import re
import duckdb

client = anthropic.Anthropic()

# duas versões do mesmo prompt, testando se instruções mais diretivas mudam o resultado
PROMPT_V1 = """Aqui está o schema da tabela:
{schema}

Exemplo do formato esperado (few-shot):
{{"column": "distance_km", "rule": "distance_km >= 0", "reason": "distância não pode ser negativa"}}

A "rule" deve ser sempre uma expressão SQL booleana válida e executável (compatível com
uma cláusula WHERE), nunca uma descrição em texto livre. Uma regra por linha — não combine
múltiplas constraints numa única regra.

Responda APENAS com uma lista JSON de regras, no mesmo formato do exemplo."""

PROMPT_V2 = """Aqui está o schema da tabela:
{schema}

Exemplo do formato esperado (few-shot):
{{"column": "distance_km", "rule": "distance_km >= 0", "reason": "distância não pode ser negativa"}}

Pense em pelo menos 2 regras por coluna: uma de integridade básica (NOT NULL, tipo válido)
e uma de domínio de negócio (valores plausíveis para o contexto). Cada regra deve ser uma
linha separada no JSON, não combine múltiplas constraints numa única regra.

A "rule" deve ser sempre uma expressão SQL booleana válida e executável (compatível com
uma cláusula WHERE), nunca uma descrição em texto livre.

Responda APENAS com uma lista JSON de regras, no mesmo formato do exemplo."""

SCHEMA = """Tabela: vehicles
- vehicle_id: int
- type: string (car, bike, scooter)
- plate: string
- year: int"""


def extract_json_array(text: str) -> str:
    """Extrai o array JSON de dentro de uma resposta de texto, ignorando
    qualquer preâmbulo, markdown ou texto após o JSON.
    """
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("Nenhum JSON encontrado na resposta")
    return match.group(0)

def is_executable_rule(rule: str) -> bool:
    """Testa se a regra é uma expressão SQL válida, executando-a contra uma
    tabela de exemplo com as colunas reais do schema testado.

    Args:
        rule: string da regra a validar.

    Returns:
        True se a expressão roda sem erro contra a tabela, False caso contrário.
    """
    con = duckdb.connect()
    # cria uma tabela com o schema real, para que nomes de coluna referenciados
    # pela regra existam de verdade durante o teste
    con.execute("""
        CREATE TABLE _test_vehicles (
            vehicle_id INTEGER,
            type VARCHAR,
            plate VARCHAR,
            year INTEGER
        )
    """)
    con.execute("INSERT INTO _test_vehicles VALUES (1, 'car', 'ABC1234', 2020)")
    try:
        con.execute(f"SELECT 1 FROM _test_vehicles WHERE {rule}")
        return True
    except Exception:
        return False

def run_and_score(prompt_template: str, schema: str) -> dict:
    prompt = prompt_template.format(schema=schema)

    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start

    output = response.content[0].text.strip()
    try:
        rules = json.loads(extract_json_array(output))
    except (json.JSONDecodeError, ValueError) as e:
        # não esconde o erro — expõe pra você saber que o parsing falhou, não que o modelo "não gerou nada"
        print(f"  ⚠️  Falha ao parsear output: {e}")
        print(f"  Output bruto (primeiros 200 chars): {repr(output[:200])}")
        rules = []

    executable_rules = 0
    for r in rules:
        if is_executable_rule(r["rule"]):
            executable_rules += 1
    
    columns_covered = len(set(r.get("column") for r in rules)) if rules else 0

    return {
        "n_rules": len(rules),
        "columns_covered": columns_covered,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "elapsed_seconds": round(elapsed, 2),
        "rules": rules,
        "executable_rules": executable_rules,
    }

if __name__ == "__main__":
    for name, prompt in [("V1 (simples)", PROMPT_V1), ("V2 (com diretriz de cobertura)", PROMPT_V2)]:
        print(f"\n=== {name} ===")
        # roda 2 vezes cada versão, pra ver também a variação entre execuções da mesma versão
        for i in range(2):
            metrics = run_and_score(prompt, SCHEMA)
            print(f"  Execução {i+1}: {metrics}, indent=2, ensure_ascii=False)")
            #print(f"  Regras geradas: {json.dumps(metrics['rules'], indent=2, ensure_ascii=False)}")