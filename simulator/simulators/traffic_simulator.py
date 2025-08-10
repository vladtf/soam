from .base import BaseSimulator
import random

class TrafficSimulator(BaseSimulator):
    def __init__(self):
        super().__init__("traffic_cam", "smartcity/sensors/traffic")
        self.road_segments = [
            "Main St & 1st Ave",
            "Oak St & 2nd Ave",
            "Highway 101 Exit 45",
            "Downtown Bridge"
        ]

    def generate_payload(self):
        segment = random.choice(self.road_segments)
        vehicle_count = random.randint(5, 200)
        avg_speed = round(random.uniform(10.0, 60.0), 2)
        
        if avg_speed < 20 and vehicle_count > 100:
            congestion_level = "high"
        elif avg_speed < 40 or vehicle_count > 50:
            congestion_level = "medium"
        else:
            congestion_level = "low"

        return {
            "road_segment": segment,
            "vehicle_count": vehicle_count,
            "average_speed_kph": avg_speed,
            "congestion_level": congestion_level,
        }

if __name__ == "__main__":
    simulator = TrafficSimulator()
    simulator.run()
