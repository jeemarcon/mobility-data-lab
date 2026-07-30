# mobility-data-lab

Laboratório de dados de mobilidade urbana. O projeto gera datasets sintéticos e realistas de clientes, veículos e corridas, e os processa por uma pipeline medallion (Bronze → Silver → Gold) usando DuckDB localmente.

## Estrutura de pastas

```
mobility-data-lab/
├── data/                        # CSVs de entrada e banco DuckDB gerado
│   ├── clients.csv
│   ├── vehicles.csv
│   ├── rides.csv
│   └── mobility.duckdb          # gerado pela pipeline (não versionado)
├── docs/                        # Regras de qualidade por tabela
│   ├── quality_rules_clients.json
│   ├── quality_rules_rides.json
│   └── quality_rules_vehicles.json
├── src/
│   ├── generate_data.py         # Geração dos dados sintéticos
│   ├── generate_quality_rules.py # Gera regras de qualidade via Claude API
│   ├── rules_to_dlt.py          # Converte regras JSON em código DLT
│   ├── pipeline/                # Pipeline medallion com DuckDB
│   │   ├── bronze.py
│   │   ├── silver.py
│   │   └── gold.py
│   └── dlt_pipelines/           # Expectations geradas para Delta Live Tables
│       ├── clients_expectations.py
│       ├── vehicles_expectations.py
│       └── rides_expectations.py
├── requirements.txt
└── README.md
```

## Tabelas de entrada

### clients

| Coluna        | Tipo    | Descrição                              |
|---------------|---------|----------------------------------------|
| client_id     | int     | Identificador único do cliente         |
| name          | string  | Nome completo (faker pt_BR)            |
| city          | string  | Cidade de cadastro                     |
| signup_date   | date    | Data de cadastro (até 2 anos atrás)    |
| is_active     | bool    | Status da conta (75% ativo)            |

### vehicles

| Coluna      | Tipo   | Descrição                                   |
|-------------|--------|---------------------------------------------|
| vehicle_id  | int    | Identificador único do veículo              |
| type        | string | Tipo: `car`, `bike` ou `scooter`            |
| plate       | string | Placa (faker pt_BR)                         |
| year        | int    | Ano de fabricação (2015–2026)               |

### rides

| Coluna       | Tipo     | Descrição                                          |
|--------------|----------|----------------------------------------------------|
| ride_id      | int      | Identificador único da corrida                     |
| client_id    | int      | FK → clients.client_id                             |
| vehicle_id   | int      | FK → vehicles.vehicle_id                           |
| start_time   | datetime | Início da corrida (últimos 90 dias)                |
| end_time     | datetime | Fim da corrida (start_time + duração)              |
| distance_km  | float    | Distância percorrida em km (0,5–30 km)             |
| fare         | float    | Tarifa em R$ (distância × multiplicador 1,5–3,0)  |

## Pipeline medallion

Os dados são processados em três camadas, todas persistidas como schemas dentro de `data/mobility.duckdb`.

### Bronze

Cópia fiel dos CSVs sem nenhuma transformação. Preserva todos os registros, incluindo os inválidos.

```
bronze.clients / bronze.vehicles / bronze.rides
```

### Silver

Aplica as regras de qualidade dos JSONs em `docs/`. Cada regra tem um campo `on_violation`:

| Valor  | Comportamento |
|--------|---------------|
| `drop` | Linha removida da silver e registrada na quarantine |
| `warn` | Linha permanece na silver, mas também registrada na quarantine |

A tabela `_quarantine` inclui a coluna `violated_rules` com a lista de regras violadas e suas severidades.

```
silver.clients / silver.clients_quarantine
silver.vehicles / silver.vehicles_quarantine
silver.rides / silver.rides_quarantine
```

### Gold

Tabelas agregadas prontas para análise, construídas exclusivamente a partir da silver.

| Tabela                      | Descrição                                              |
|-----------------------------|--------------------------------------------------------|
| `gold.revenue_by_client`    | Corridas, receita, ticket médio e distância por cliente |
| `gold.rides_by_vehicle_type`| Volume, receita e duração média por tipo de veículo    |

## Como rodar

### Pré-requisitos

```bash
pip install -r requirements.txt
```

### 1. Gerar os dados sintéticos

```bash
python src/generate_data.py
```

Cria `data/clients.csv`, `data/vehicles.csv` e `data/rides.csv` com 200 clientes, 50 veículos e 2.000 corridas. Para alterar os volumes, edite as constantes `N_CLIENTS`, `N_VEHICLES` e `N_RIDES` em [src/generate_data.py](src/generate_data.py).

### 2. Gerar regras de qualidade (requer chave da API Anthropic)

```bash
python src/generate_quality_rules.py
```

Lê os schemas dos CSVs via DuckDB e usa o Claude para propor regras de qualidade, salvas em `docs/quality_rules_*.json`.

### 3. Rodar a pipeline

```bash
python src/pipeline/bronze.py
python src/pipeline/silver.py
python src/pipeline/gold.py
```

Todas as camadas são persistidas em `data/mobility.duckdb`. Para inspecionar:

```python
import duckdb
con = duckdb.connect("data/mobility.duckdb")
con.execute("SELECT * FROM gold.revenue_by_client LIMIT 10").df()
```

### 4. Converter regras para DLT (opcional)

```bash
python src/rules_to_dlt.py
```

Gera os arquivos `src/dlt_pipelines/*_expectations.py` prontos para uso em pipelines Delta Live Tables.
