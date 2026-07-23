import dlt

# Expectations geradas a partir de docs/quality_rules_vehicles.json
EXPECTATIONS = {
    "vehicle_id_valid": "vehicle_id IS NOT NULL",  # identificador do veículo não pode ser nulo
    "vehicle_id_valid": "vehicle_id > 0",  # identificador do veículo deve ser um valor positivo
    "type_valid": "type IS NOT NULL",  # tipo do veículo não pode ser nulo
    "type_valid": "type IN ('car', 'truck', 'motorcycle', 'bus', 'van', 'SUV', 'pickup')",  # tipo do veículo deve pertencer a um conjunto de valores válidos conhecidos
    "plate_valid": "plate IS NOT NULL",  # placa do veículo não pode ser nula
    "plate_valid": "LENGTH(plate) >= 4",  # placa do veículo deve ter ao menos 4 caracteres para ser válida
    "plate_valid": "plate NOT LIKE '% %'",  # placa do veículo não deve conter espaços em branco
    "year_valid": "year IS NOT NULL",  # ano do veículo não pode ser nulo
    "year_valid": "year >= 1886",  # ano do veículo não pode ser anterior ao primeiro automóvel da história (1886)
    "year_valid": "year <= YEAR(CURRENT_DATE())",  # ano do veículo não pode ser maior que o ano corrente
}

@dlt.table(name="vehicles_validated")
@dlt.expect_all(EXPECTATIONS)
def vehicles_validated():
    return dlt.read("vehicles_bronze")