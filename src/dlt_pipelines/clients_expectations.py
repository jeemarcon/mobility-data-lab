import dlt

# Expectations geradas a partir de docs/quality_rules_clients.json
EXPECTATIONS = {
    "client_id_valid": "client_id IS NOT NULL",  # identificador do cliente não pode ser nulo
    "client_id_valid": "client_id > 0",  # identificador do cliente deve ser um valor positivo
    "name_valid": "name IS NOT NULL",  # nome do cliente não pode ser nulo
    "name_valid": "LENGTH(TRIM(name)) > 0",  # nome do cliente não pode ser uma string vazia ou apenas espaços
    "name_valid": "LENGTH(name) <= 255",  # nome do cliente não deve exceder o tamanho razoável de um VARCHAR
    "city_valid": "city IS NOT NULL",  # cidade do cliente não pode ser nula
    "city_valid": "LENGTH(TRIM(city)) > 0",  # cidade do cliente não pode ser uma string vazia ou apenas espaços
    "city_valid": "LENGTH(city) <= 100",  # nome de cidade não deve exceder tamanho razoável
    "signup_date_valid": "signup_date IS NOT NULL",  # data de cadastro não pode ser nula
    "signup_date_valid": "signup_date >= '2000-01-01'",  # data de cadastro não deve ser anterior a um limite mínimo razoável de operação do negócio
    "signup_date_valid": "signup_date <= CURRENT_DATE()",  # data de cadastro não pode ser uma data futura
    "is_active_valid": "is_active IS NOT NULL",  # flag de cliente ativo não pode ser nula, deve ser explicitamente verdadeiro ou falso
}

@dlt.table(name="clients_validated")
@dlt.expect_all(EXPECTATIONS)
def clients_validated():
    return dlt.read("clients_bronze")