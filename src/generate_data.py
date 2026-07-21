import random
from datetime import datetime, timedelta
from faker import Faker
import pandas as pd

fake = Faker("pt_BR")
random.seed(42)
Faker.seed(42)

N_CLIENTS = 200
N_VEHICLES = 50
N_RIDES = 2000


def generate_clients(n=N_CLIENTS):
    return pd.DataFrame([
        {
            "client_id": i + 1,
            "name": fake.name(),
            "city": fake.city(),
            "signup_date": fake.date_between(start_date="-2y", end_date="today"),
            "is_active": random.choice([True, True, True, False]),
        }
        for i in range(n)
    ])


def generate_vehicles(n=N_VEHICLES):
    vehicle_types = ["car", "bike", "scooter"]
    return pd.DataFrame([
        {
            "vehicle_id": i + 1,
            "type": random.choice(vehicle_types),
            "plate": fake.license_plate(),
            "year": random.randint(2015, 2026),
        }
        for i in range(n)
    ])


def generate_rides(n=N_RIDES, n_clients=N_CLIENTS, n_vehicles=N_VEHICLES):
    rides = []
    for i in range(n):
        start_time = fake.date_time_between(start_date="-90d", end_date="now")
        duration_min = random.randint(5, 60)
        distance_km = round(random.uniform(0.5, 30.0), 2)

        rides.append({
            "ride_id": i + 1,
            "client_id": random.randint(1, n_clients),
            "vehicle_id": random.randint(1, n_vehicles),
            "start_time": start_time,
            "end_time": start_time + timedelta(minutes=duration_min),
            "distance_km": distance_km,
            "fare": round(distance_km * random.uniform(1.5, 3.0), 2),
        })
    return pd.DataFrame(rides)


if __name__ == "__main__":
    clients = generate_clients()
    vehicles = generate_vehicles()
    rides = generate_rides()

    clients.to_csv("data/clients.csv", index=False)
    vehicles.to_csv("data/vehicles.csv", index=False)
    rides.to_csv("data/rides.csv", index=False)

    print(f"Gerado: {len(clients)} clients, {len(vehicles)} vehicles, {len(rides)} rides")