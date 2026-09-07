"""Port of src/ai/fitness.js — headless sim-time version.

JS uses Date.now() wall-clock for timeAlive. Headless runs faster than
real time, so we use simulated time: steps_alive / 60 (dt=1 == 1/60s).
Scoring is otherwise identical:
  damaged -> distance + carsPassed*passedBonus
  alive   -> distance + carsPassed*passedBonus + timeAlive*10
Distance = 100 - car.y (clamped >= 0). Best car = max distance.
noPass kill after noPassSeconds*60 frames without passing.
"""
from . import config as C


class Fitness:
    def __init__(self, car):
        self.car = car
        self.cars_passed = 0
        self.counted = set()
        self.last_y = car.y
        self.no_pass_timer = 0.0
        self.steps_alive = 0
        self.death_step = None

    def update(self, traffic):
        if self.car.damaged:
            if self.death_step is None:
                self.death_step = self.steps_alive
            return
        current_y = self.car.y
        for t in traffic:
            key = id(t)
            if key in self.counted:
                continue
            if self.last_y > t.y and current_y <= t.y:
                self.cars_passed += 1
                self.counted.add(key)
                self.no_pass_timer = 0
        self.last_y = current_y
        self.steps_alive += 1

    def check_no_pass(self, dt=1.0):
        if self.car.damaged or not self.car.use_brain:
            return
        if C.EVOLUTION["no_pass_seconds"] <= 0:
            return
        self.no_pass_timer += dt
        if self.no_pass_timer >= C.EVOLUTION["no_pass_seconds"] * 60:
            self.car.damaged = True

    def get_distance(self):
        dist = C.CAR["start_y"] - self.car.y
        return dist if dist >= 0 else 0

    def get_time_alive(self):
        end = self.death_step if self.death_step is not None else self.steps_alive
        return end / 60.0

    def calculate_score(self):
        distance = self.get_distance()
        bonus = self.cars_passed * C.FITNESS["passed_bonus"]
        if self.car.damaged:
            return distance + bonus
        return distance + bonus + self.get_time_alive() * C.FITNESS["time_alive_multiplier"]
