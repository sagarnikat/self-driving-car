"""Port of src/traffic/trafficLoader.js (headless, no DOM).

- RandomTrafficCar: DUMMY car, polygon prebuilt, update filters nearby (exact).
- TrafficGenerator: same row logic/order, driven by seeded RNG.
- load_fixed_pattern / make_traffic_cars: load data/traffic/<N> lane/traffic_K.json.
"""
import json
import math
import os

from . import config as C
from . import rng as rng_mod
from .car import Car, Road


class RandomTrafficCar(Car):
    def __init__(self, x, y, width, height, speed, lane_count=3):
        super().__init__(x, y, width, height, "DUMMY", speed)
        self.lane_count = lane_count
        self.polygon = self._create_polygon()

    def update(self, road_borders, traffic, dt=1.0):
        nearby = [c for c in traffic if abs(c.y - self.y) < C.TRAFFIC["nearby_distance"]]
        super().update(road_borders, nearby, dt)


class TrafficGenerator:
    def __init__(self, lane_count, road):
        self.lane_count = lane_count
        self.road = road
        self.cars = []
        row_y = C.CAR["start_y"]
        for _ in range(C.TRAFFIC["initial_rows"]):
            row_y -= C.TRAFFIC["row_spacing"]
            self.generate_row(row_y)

    def generate_row(self, row_y):
        max_cars = min(C.TRAFFIC["max_cars_per_row"], self.lane_count - 1)
        rnd = rng_mod.seeded_random
        car_count = math.floor(rnd() * (max_cars + 1))
        used = []
        while len(used) < car_count:
            lane = math.floor(rnd() * self.lane_count)
            if lane not in used:
                used.append(lane)
        for lane in used:
            self.cars.append(
                RandomTrafficCar(
                    self.road.get_lane_center(lane),
                    row_y,
                    C.TRAFFIC["default_car_width"],
                    C.TRAFFIC["default_car_height"],
                    C.TRAFFIC["default_speed"],
                    self.lane_count,
                )
            )

    def update(self, best_car_y):
        self.cars = [c for c in self.cars if c.y < best_car_y + C.TRAFFIC["remove_behind_offset"]]
        furthest = best_car_y
        if self.cars:
            furthest = min(c.y for c in self.cars)
        while best_car_y - furthest < C.TRAFFIC["generate_ahead_rows"] * C.TRAFFIC["row_spacing"]:
            furthest -= C.TRAFFIC["row_spacing"]
            self.generate_row(furthest)

    def get_cars(self):
        return self.cars


def repo_root():
    # simulation/ is a child of the repo root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pattern_path(lane_count, pattern_id):
    return os.path.join(repo_root(), "data", "traffic", f"{lane_count} lane", f"traffic_{pattern_id}.json")


def make_traffic_cars(data, road, lane_count):
    out = []
    for entry in data.get("cars", []):
        out.append(
            Car(
                road.get_lane_center(entry["lane"]),
                entry["y"],
                data.get("carWidth", C.TRAFFIC["default_car_width"]),
                data.get("carHeight", C.TRAFFIC["default_car_height"]),
                "DUMMY",
                entry.get("speed", C.TRAFFIC["default_speed"]),
            )
        )
        out[-1].polygon = out[-1]._create_polygon()
    return out


def load_fixed_pattern(lane_count, pattern_id, road):
    with open(pattern_path(lane_count, pattern_id), "r") as f:
        data = json.load(f)
    return make_traffic_cars(data, road, lane_count)
