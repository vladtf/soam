from .base import BaseSimulator
import random

class AirQualitySimulator(BaseSimulator):
    def __init__(self):
        super().__init__("air_quality_monitor", "smartcity/sensors/air_quality")
        self.locations = ["City Center", "Industrial Park", "Residential Area", "Parkside"]

    def generate_payload(self):
        location = random.choice(self.locations)
        
        if location == "Industrial Park":
            co = round(random.uniform(5.0, 15.0), 2) # ppm
            no2 = round(random.uniform(0.1, 0.5), 2) # ppm
            pm25 = round(random.uniform(20.0, 50.0), 2) # µg/m³
        else:
            co = round(random.uniform(0.1, 5.0), 2)
            no2 = round(random.uniform(0.01, 0.2), 2)
            pm25 = round(random.uniform(5.0, 25.0), 2)

        return {
            "location": location,
            "carbon_monoxide_ppm": co,
            "nitrogen_dioxide_ppm": no2,
            "particulate_matter_2_5_ug_m3": pm25,
        }

if __name__ == "__main__":
    simulator = AirQualitySimulator()
    simulator.run()
