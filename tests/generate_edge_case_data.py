"""Gera rides_dirty_test.csv com casos de borda propositais para testar a pipeline.

Cada bloco de linhas cobre uma categoria de problema diferente, identificada
pelo campo ride_id (faixa 9001+) para não colidir com dados reais.
"""

import csv
import os

OUTPUT_PATH = "tests/data/rides.csv"

HEADER = ["ride_id", "client_id", "vehicle_id", "start_time", "end_time", "distance_km", "fare"]

# Uma linha limpa de referência para contrastar com os casos sujos
CLEAN_BASE = {
    "ride_id": 9000,
    "client_id": 1,
    "vehicle_id": 1,
    "start_time": "2026-07-01 10:00:00",
    "end_time": "2026-07-01 11:00:00",
    "distance_km": 10.0,
    "fare": 25.0,
}

edge_cases = [
    # --- referência limpa ---
    {**CLEAN_BASE, "ride_id": 9000},

    # --- valores extremos ---
    # distance_km acima do limite da regra drop (>= 0) mas abaixo do warn (<=5000): válido
    {**CLEAN_BASE, "ride_id": 9001, "distance_km": 4999.99, "fare": 9999.98},
    # distance_km exatamente no limite do warn
    {**CLEAN_BASE, "ride_id": 9002, "distance_km": 5000.0, "fare": 10000.0},
    # distance_km acima do limite do warn — deve gerar warn na quarantine
    {**CLEAN_BASE, "ride_id": 9003, "distance_km": 5001.0, "fare": 10002.0},
    # fare acima do limite do warn
    {**CLEAN_BASE, "ride_id": 9004, "distance_km": 10.0, "fare": 100001.0},

    # --- inconsistências entre colunas (drop) ---
    # end_time antes de start_time
    {**CLEAN_BASE, "ride_id": 9010, "start_time": "2026-07-01 11:00:00", "end_time": "2026-07-01 10:00:00"},
    # end_time igual a start_time (duração zero)
    {**CLEAN_BASE, "ride_id": 9011, "start_time": "2026-07-01 10:00:00", "end_time": "2026-07-01 10:00:00"},
    # distância zero com tarifa positiva (warn)
    {**CLEAN_BASE, "ride_id": 9012, "distance_km": 0.0, "fare": 15.0},
    # distância positiva com tarifa zero (warn)
    {**CLEAN_BASE, "ride_id": 9013, "distance_km": 10.0, "fare": 0.0},

    # --- nulos em colunas obrigatórias (drop) ---
    {**CLEAN_BASE, "ride_id": 9020, "client_id": ""},
    {**CLEAN_BASE, "ride_id": 9021, "vehicle_id": ""},
    {**CLEAN_BASE, "ride_id": 9022, "start_time": ""},
    {**CLEAN_BASE, "ride_id": 9023, "end_time": ""},
    {**CLEAN_BASE, "ride_id": 9024, "distance_km": ""},
    {**CLEAN_BASE, "ride_id": 9025, "fare": ""},

    # --- duplicatas de ride_id ---
    # mesmo ride_id 9030 repetido três vezes com dados diferentes
    {**CLEAN_BASE, "ride_id": 9030, "distance_km": 5.0, "fare": 10.0},
    {**CLEAN_BASE, "ride_id": 9030, "distance_km": 8.0, "fare": 20.0},
    {**CLEAN_BASE, "ride_id": 9030, "distance_km": 12.0, "fare": 30.0},

    # --- tipos inesperados simulados via string no CSV ---
    # distance_km como texto — DuckDB tentará converter; se falhar, vira NULL (drop)
    {**CLEAN_BASE, "ride_id": 9040, "distance_km": "dez quilometros", "fare": 25.0},
    # fare como booleano textual
    {**CLEAN_BASE, "ride_id": 9041, "distance_km": 10.0, "fare": "true"},
    # ride_id como float (pode ser aceito ou rejeitado dependendo do parser)
    {**CLEAN_BASE, "ride_id": "9042.5", "distance_km": 10.0, "fare": 25.0},
    # client_id negativo (viola a regra drop client_id > 0)
    {**CLEAN_BASE, "ride_id": 9043, "client_id": -1},

    # --- datas malformadas ---
    # formato de data inválido
    {**CLEAN_BASE, "ride_id": 9050, "start_time": "01/07/2026 10:00", "end_time": "01/07/2026 11:00"},
    # data implausível anterior a 2000 (warn)
    {**CLEAN_BASE, "ride_id": 9051, "start_time": "1999-12-31 23:59:00", "end_time": "2000-01-01 00:59:00"},
]


def write_dirty_csv(rows: list[dict], path: str):
    """Escreve os casos de borda em um CSV, preservando valores vazios como nulos.

    Args:
        rows: lista de dicts representando cada linha.
        path: caminho de saída do arquivo CSV.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    write_dirty_csv(edge_cases, OUTPUT_PATH)
    print(f"Gerado: {OUTPUT_PATH} com {len(edge_cases)} linhas ({len(edge_cases) - 1} casos de borda + 1 referência limpa)")

    # imprime resumo por categoria
    categories = {
        "referência limpa":         [r for r in edge_cases if r["ride_id"] == 9000],
        "valores extremos":         [r for r in edge_cases if str(r["ride_id"]).startswith("900") and r["ride_id"] != 9000],
        "inconsistências colunas":  [r for r in edge_cases if str(r["ride_id"]).startswith("901")],
        "nulos obrigatórios":       [r for r in edge_cases if str(r["ride_id"]).startswith("902")],
        "duplicatas ride_id":       [r for r in edge_cases if r["ride_id"] == 9030],
        "tipos inesperados":        [r for r in edge_cases if str(r["ride_id"]).startswith("904")],
        "datas malformadas":        [r for r in edge_cases if str(r["ride_id"]).startswith("905")],
    }
    for category, rows in categories.items():
        print(f"  {category}: {len(rows)} linha(s)")
