# mobility-data-lab

Laboratório de dados de mobilidade urbana. O projeto gera datasets sintéticos e realistas de clientes, veículos e corridas para uso em análises, experimentos e pipelines de dados.

## Estrutura de pastas

```
mobility-data-lab/
├── data/               # CSVs gerados pelo script
│   ├── clients.csv
│   ├── vehicles.csv
│   └── rides.csv
├── src/
│   └── generate_data.py  # Script principal de geração
├── docs/               # Documentação adicional
├── requirements.txt
└── README.md
```

## Tabelas geradas

### clients

Dados cadastrais de clientes.

| Coluna        | Tipo    | Descrição                              |
|---------------|---------|----------------------------------------|
| client_id     | int     | Identificador único do cliente         |
| name          | string  | Nome completo (faker pt_BR)            |
| city          | string  | Cidade de cadastro                     |
| signup_date   | date    | Data de cadastro (até 2 anos atrás)    |
| is_active     | bool    | Status da conta (75% ativo)            |

### vehicles

Frota de veículos disponíveis.

| Coluna      | Tipo   | Descrição                                   |
|-------------|--------|---------------------------------------------|
| vehicle_id  | int    | Identificador único do veículo              |
| type        | string | Tipo: `car`, `bike` ou `scooter`            |
| plate       | string | Placa (faker pt_BR)                         |
| year        | int    | Ano de fabricação (2015–2026)               |

### rides

Histórico de corridas realizadas.

| Coluna       | Tipo     | Descrição                                          |
|--------------|----------|----------------------------------------------------|
| ride_id      | int      | Identificador único da corrida                     |
| client_id    | int      | FK → clients.client_id                             |
| vehicle_id   | int      | FK → vehicles.vehicle_id                           |
| start_time   | datetime | Início da corrida (últimos 90 dias)                |
| end_time     | datetime | Fim da corrida (start_time + duração)              |
| distance_km  | float    | Distância percorrida em km (0,5–30 km)             |
| fare         | float    | Tarifa em R$ (distância × multiplicador 1,5–3,0)  |

## Como rodar

### Pré-requisitos

- Python 3.9+
- Instalar dependências:

```bash
pip install -r requirements.txt
```

### Gerando os dados

```bash
python src/generate_data.py
```

Os arquivos `clients.csv`, `vehicles.csv` e `rides.csv` serão criados na pasta `data/`.

Os volumes padrão são **200 clientes**, **50 veículos** e **2.000 corridas**. Para alterar, edite as constantes `N_CLIENTS`, `N_VEHICLES` e `N_RIDES` no topo de [src/generate_data.py](src/generate_data.py).
