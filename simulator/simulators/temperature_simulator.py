from .base import BaseSimulator
import random
from datetime import datetime

class TemperatureSimulator(BaseSimulator):
    def __init__(self):
        super().__init__("temp_sensor", "smartcity/sensors/temperature")

    def generate_payload(self):
        current_hour = datetime.now().hour
        if 0 <= current_hour < 6:
            base_temp = random.uniform(5.0, 15.0)
            humidity = random.uniform(60, 90)
        elif 6 <= current_hour < 12:
            base_temp = random.uniform(15.0, 25.0)
            humidity = random.uniform(50, 80)
        elif 12 <= current_hour < 18:
            base_temp = random.uniform(25.0, 35.0)
            humidity = random.uniform(30, 60)
        else: # 18 to 24
            base_temp = random.uniform(15.0, 25.0)
            humidity = random.uniform(50, 80)

        return {
            "temperature": round(base_temp + random.uniform(-1, 1), 2),
            "humidity": round(humidity + random.uniform(-5, 5), 2),
        }

if __name__ == "__main__":
    simulator = TemperatureSimulator()
    simulator.run()
