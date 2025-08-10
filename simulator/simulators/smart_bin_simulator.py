from .base import BaseSimulator
import random

class SmartBinSimulator(BaseSimulator):
    def __init__(self):
        super().__init__("smart_bin", "smartcity/sensors/smart_bin")
        self.locations = ["Market Square", "Central Park", "Bus Stop 12", "Main Street Corner"]

    def generate_payload(self):
        location = random.choice(self.locations)
        fill_level = round(random.uniform(0, 100), 2)
        status = "needs_collection" if fill_level > 85 else "ok"

        return {
            "location": location,
            "fill_level_percent": fill_level,
            "status": status,
        }

if __name__ == "__main__":
    simulator = SmartBinSimulator()
    simulator.run()
