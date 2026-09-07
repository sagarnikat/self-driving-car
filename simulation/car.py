"""Exact port of Road / Sensor / Car from src/core/{road,sensor,car}.js.

Units: pixels, speed px/frame at dt=1. Same polygon math, same move
formulas, same stall logic (stallSeconds*60 frames), same sensor mapping
(0 if null else 1-offset) and same control timing (sensor sets controls
for the NEXT frame).
"""
import math

from . import config as C
from .network import NeuralNetwork
from .utils import lerp, polys_intersect, get_intersection


class Road:
    def __init__(self, x=None, width=None, lane_count=None):
        if x is None:
            x = C.ROAD["car_canvas_width"] / 2
        if width is None:
            width = C.ROAD["car_canvas_width"] * C.ROAD["width_factor"]
        if lane_count is None:
            lane_count = C.ROAD["lane_count"]
        self.x = x
        self.width = width
        self.lane_count = lane_count
        self.left = x - width / 2
        self.right = x + width / 2
        inf = C.ROAD["infinity"]
        self.top = -inf
        self.bottom = inf
        self.borders = [
            ({"x": self.left, "y": self.top}, {"x": self.left, "y": self.bottom}),
            ({"x": self.right, "y": self.top}, {"x": self.right, "y": self.bottom}),
        ]

    def get_lane_center(self, lane_index):
        line_width = self.width / self.lane_count
        return self.left + line_width / 2 + min(lane_index, self.lane_count - 1) * line_width


class Sensor:
    def __init__(self, car):
        self.car = car
        self.ray_count = C.SENSOR["ray_count"]
        self.ray_length = C.SENSOR["ray_length"]
        self.ray_spread = C.SENSOR["ray_spread"]
        self.rays = []
        self.readings = []

    def update(self, road_borders, traffic):
        self._cast_rays()
        self.readings = []
        for ray in self.rays:
            self.readings.append(self._get_reading(ray, road_borders, traffic))

    def _get_reading(self, ray, road_borders, traffic):
        touches = []
        for border in road_borders:
            touch = get_intersection(ray[0], ray[1], border[0], border[1])
            if touch:
                touches.append(touch)
        # perf: only nearby traffic can intersect a 150px ray (exact: far ones miss)
        cx, cy = self.car.x, self.car.y
        for t in traffic:
            # bounding pre-check (~exact, generous margin)
            if abs(t.y - cy) > self.ray_length + 60:
                continue
            if abs(t.x - cx) > self.ray_length + 60:
                continue
            poly = t.polygon
            if not poly:
                continue
            for j in range(len(poly)):
                v = get_intersection(ray[0], ray[1], poly[j], poly[(j + 1) % len(poly)])
                if v:
                    touches.append(v)
        if not touches:
            return None
        min_offset = min(e["offset"] for e in touches)
        for e in touches:
            if e["offset"] == min_offset:
                return e
        return touches[0]

    def _cast_rays(self):
        self.rays = []
        for i in range(self.ray_count):
            t = 0.5 if self.ray_count == 1 else i / (self.ray_count - 1)
            ray_angle = lerp(self.ray_spread / 2, -self.ray_spread / 2, t) + self.car.angle
            start = {"x": self.car.x, "y": self.car.y}
            end = {
                "x": self.car.x - math.sin(ray_angle) * self.ray_length,
                "y": self.car.y - math.cos(ray_angle) * self.ray_length,
            }
            self.rays.append((start, end))


class Car:
    def __init__(self, x, y, width, height, control_type, max_speed=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = 0.0
        self.acceleration = C.CAR["acceleration"]
        self.max_speed = max_speed if max_speed is not None else C.CAR["max_speed"]
        self.friction = C.CAR["friction"]
        self.angle = 0.0
        self.damaged = False
        self.can_rotate = C.CAR["can_rotate"]
        self.stall_timer = 0.0
        self.use_brain = control_type == "AI"
        self.control_type = control_type
        self.sensor = None
        self.brain = None
        if control_type != "DUMMY":
            self.sensor = Sensor(self)
            self.brain = NeuralNetwork(
                [self.sensor.ray_count, C.NETWORK["hidden_size"], C.NETWORK["output_size"]]
            )
        # controls: dict to mirror JS Controls fields
        self.controls = {"forward": False, "reverse": False, "left": False, "right": False}
        if control_type == "DUMMY":
            self.controls["forward"] = True
        self.polygon = self._create_polygon()

    def update(self, road_borders, traffic, dt=1.0):
        if not self.damaged:
            self._move(dt)
            self.polygon = self._create_polygon()
            self.damaged = self._assess_damage(road_borders, traffic)
            if not self.damaged and self.use_brain:
                if self.speed <= 0:
                    self.stall_timer += dt
                    if self.stall_timer >= C.EVOLUTION["stall_seconds"] * 60:
                        self.damaged = True
                else:
                    self.stall_timer = 0
        if self.sensor:
            self.sensor.update(road_borders, traffic)
            offsets = [0 if s is None else 1 - s["offset"] for s in self.sensor.readings]
            outputs = NeuralNetwork.feed_forward(offsets, self.brain)
            if self.use_brain:
                self.controls["forward"] = bool(outputs[0])
                self.controls["left"] = bool(outputs[1])
                self.controls["right"] = bool(outputs[2])
                self.controls["reverse"] = bool(outputs[3])

    def _assess_damage(self, road_borders, traffic):
        for border in road_borders:
            if polys_intersect(self.polygon, list(border)):
                return True
        for t in traffic:
            if t.polygon and polys_intersect(self.polygon, t.polygon):
                return True
        return False

    def _create_polygon(self):
        rad = math.hypot(self.width, self.height) / 2
        alpha = math.atan2(self.width, self.height)
        return [
            {"x": self.x - math.sin(self.angle - alpha) * rad,
             "y": self.y - math.cos(self.angle - alpha) * rad},
            {"x": self.x - math.sin(self.angle + alpha) * rad,
             "y": self.y - math.cos(self.angle + alpha) * rad},
            {"x": self.x - math.sin(math.pi + self.angle - alpha) * rad,
             "y": self.y - math.cos(math.pi + self.angle - alpha) * rad},
            {"x": self.x - math.sin(math.pi + self.angle + alpha) * rad,
             "y": self.y - math.cos(math.pi + self.angle + alpha) * rad},
        ]

    def _move(self, dt):
        if self.controls["forward"]:
            self.speed += self.acceleration * dt
        if self.controls["reverse"]:
            self.speed -= self.acceleration * dt
        if self.speed > self.max_speed:
            self.speed = self.max_speed
        if self.speed < -self.max_speed / 2:
            self.speed = -self.max_speed / 2
        if self.speed > 0:
            self.speed -= self.friction * dt
        if self.speed < 0:
            self.speed += self.friction * dt
        if abs(self.speed) < self.friction * dt:
            self.speed = 0

        self._handle_turn(dt)
        self.x -= math.sin(self.angle) * self.speed * dt
        self.y -= math.cos(self.angle) * self.speed * dt

    def _handle_turn(self, dt):
        if self.can_rotate and self.speed != 0:
            flip = 1 if self.speed > 0 else -1
            if self.controls["left"]:
                self.angle += C.CAR["turn_angle"] * flip * dt
            if self.controls["right"]:
                self.angle -= C.CAR["turn_angle"] * flip * dt
        else:
            if self.controls["left"]:
                self.x -= C.CAR["lateral_speed"] * dt
            if self.controls["right"]:
                self.x += C.CAR["lateral_speed"] * dt
