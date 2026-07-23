import dlt

# Expectations geradas a partir de docs/quality_rules_rides.json
EXPECTATIONS = {
    "ride_id_valid": "ride_id IS NOT NULL",  # identificador da corrida não pode ser nulo
    "ride_id_valid": "ride_id > 0",  # identificador da corrida deve ser um valor positivo
    "client_id_valid": "client_id IS NOT NULL",  # identificador do cliente não pode ser nulo
    "client_id_valid": "client_id > 0",  # identificador do cliente deve ser um valor positivo
    "vehicle_id_valid": "vehicle_id IS NOT NULL",  # identificador do veículo não pode ser nulo
    "vehicle_id_valid": "vehicle_id > 0",  # identificador do veículo deve ser um valor positivo
    "start_time_valid": "start_time IS NOT NULL",  # horário de início da corrida não pode ser nulo
    "end_time_valid": "end_time IS NOT NULL",  # horário de término da corrida não pode ser nulo
    "end_time_valid": "end_time > start_time",  # horário de término deve ser posterior ao horário de início
    "start_time_valid": "start_time >= '2000-01-01'",  # horário de início não deve ser uma data implausível anterior ao ano 2000
    "end_time_valid": "end_time <= current_timestamp()",  # horário de término não pode ser uma data futura
    "distance_km_valid": "distance_km IS NOT NULL",  # distância percorrida não pode ser nula
    "distance_km_valid": "distance_km >= 0",  # distância não pode ser negativa
    "distance_km_valid": "distance_km <= 5000",  # distância acima de 5000 km é implausível para uma única corrida
    "fare_valid": "fare IS NOT NULL",  # valor da tarifa não pode ser nulo
    "fare_valid": "fare >= 0",  # valor da tarifa não pode ser negativo
    "fare_valid": "fare <= 100000",  # valor da tarifa acima de 100000 é implausível e pode indicar erro de entrada
    "distance_km_valid": "NOT (distance_km = 0 AND fare > 0)",  # corrida com distância zero não deveria gerar tarifa positiva
    "distance_km_valid": "NOT (distance_km > 0 AND fare = 0)",  # corrida com distância percorrida não deveria ter tarifa zero
}

@dlt.table(name="rides_validated")
@dlt.expect_all(EXPECTATIONS)
def rides_validated():
    return dlt.read("rides_bronze")