"""Exact port of Road / Sensor / Car from src/core/{road,sensor,car}.js.

Units: pixels, speed px/frame at dt=1. Same polygon math, same move
formulas, same stall logic (stallSeconds*60 frames), same sensor mapping
(0 if null else 1-offset) and same control timing (sensor sets controls
for the NEXT frame).
"""
import math

from . import config as C
from .network import NeuralNetwork
from .utils import (
    lerp,
    poly_bounds,
    polys_intersect_fast,
    seg_offset,
)


# Cached unit-ray directions for the common case (angle == 0, which holds
# whenever can_rotate is False — the default: cars only move laterally).
# Keyed by (ray_count, ray_spread) so config changes are picked up.
_RAY_DIR_CACHE = {}


def _ray_dirs(ray_count, ray_spread):
    key = (ray_count, ray_spread)
    dirs = _RAY_DIR_CACHE.get(key)
    if dirs is None:
        dirs = []
        for i in range(ray_count):
            t = 0.5 if ray_count == 1 else i / (ray_count - 1)
            a = lerp(ray_spread / 2, -ray_spread / 2, t)
            dirs.append((math.sin(a), math.cos(a)))
        _RAY_DIR_CACHE[key] = dirs
    return dirs


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
            ((self.left, self.top), (self.left, self.bottom)),
            ((self.right, self.top), (self.right, self.bottom)),
        ]
        # precomputed bounds for the two vertical borders (exact reject)
        self.border_bounds = [
            (self.left, self.left, self.top, self.bottom),
            (self.right, self.right, self.top, self.bottom),
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
        (ax, ay), (bx, by) = ray
        best_t = None
        best_x = best_y = 0.0
        # road borders first (same order as the exact port: borders, then traffic)
        for border in road_borders:
            (cx, cy), (dx, dy) = border
            t = seg_offset(ax, ay, bx, by, cx, cy, dx, dy)
            if t is not None and (best_t is None or t < best_t):
                best_t = t
                best_x = ax + (bx - ax) * t
                best_y = ay + (by - ay) * t
        # perf: only nearby traffic can intersect a 150px ray (exact: far ones miss)
        cx0, cy0 = self.car.x, self.car.y
        rl = self.ray_length + 60
        for t in traffic:
            # bounding pre-check (~exact, generous margin)
            if abs(t.y - cy0) > rl:
                continue
            if abs(t.x - cx0) > rl:
                continue
            poly = t.polygon
            if not poly:
                continue
            n = len(poly)
            for j in range(n):
                cx, cy = poly[j]
                dx, dy = poly[(j + 1) % n]
                t = seg_offset(ax, ay, bx, by, cx, cy, dx, dy)
                # strict < keeps first-min wins, same as the exact port
                if t is not None and (best_t is None or t < best_t):
                    best_t = t
                    best_x = ax + (bx - ax) * t
                    best_y = ay + (by - ay) * t
        if best_t is None:
            return None
        return (best_x, best_y, best_t)

    def _cast_rays(self):
        n = self.ray_count
        length = self.ray_length
        x, y = self.car.x, self.car.y
        angle = self.car.angle
        rays = []
        if angle == 0.0:
            # fast path: cached direction vectors, no sin/cos per ray
            for sina, cosa in _ray_dirs(n, self.ray_spread):
                rays.append(((x, y), (x - sina * length, y - cosa * length)))
        else:
            for i in range(n):
                t = 0.5 if n == 1 else i / (n - 1)
                ray_angle = lerp(self.ray_spread / 2, -self.ray_spread / 2, t) + angle
                rays.append(((x, y), (x - math.sin(ray_angle) * length,
                                      y - math.cos(ray_angle) * length)))
        self.rays = rays


class Car:
    def __init__(self, x, y, width, height, control_type, max_speed=None, init_brain=True):
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
            if init_brain:
                self.brain = NeuralNetwork(
                    [self.sensor.ray_count, C.NETWORK["hidden_size"], C.NETWORK["output_size"]]
                )
        # controls: dict to mirror JS Controls fields
        self.controls = {"forward": False, "reverse": False, "left": False, "right": False}
        if control_type == "DUMMY":
            self.controls["forward"] = True
        self.polygon = self._create_polygon()
        self._poly_bounds = poly_bounds(self.polygon)

    def update(self, road_borders, traffic, dt=1.0):
        if self.damaged:
            # Damaged cars can no longer move or affect others; skipping the
            # sensor + network pass is pure speedup (controls are dead anyway).
            return
        self._move(dt)
        self.polygon = self._create_polygon()
        self._poly_bounds = poly_bounds(self.polygon)
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
            offsets = [0 if s is None else 1 - s[2] for s in self.sensor.readings]
            outputs = NeuralNetwork.feed_forward(offsets, self.brain)
            if self.use_brain:
                self.controls["forward"] = bool(outputs[0])
                self.controls["left"] = bool(outputs[1])
                self.controls["right"] = bool(outputs[2])
                self.controls["reverse"] = bool(outputs[3])

    def _assess_damage(self, road_borders, traffic):
        b1 = self._poly_bounds
        for border in road_borders:
            # borders are 2-point segments; bounds computed inline (cheap)
            (bx1, by1), (bx2, by2) = border
            b2 = (bx1, bx2, by1, by2) if bx1 <= bx2 else (bx2, bx1, by1, by2)
            if b2[2] > b2[3]:
                b2 = (b2[0], b2[1], b2[3], b2[2])
            if polys_intersect_fast(self.polygon, b1, border, b2):
                return True
        for t in traffic:
            tp = t.polygon
            if tp and polys_intersect_fast(self.polygon, b1, tp, t._poly_bounds):
                return True
        return False

    def _create_polygon(self):
        rad = math.hypot(self.width, self.height) / 2
        alpha = math.atan2(self.width, self.height)
        # (x, y) tuples — same coordinates as the old dict form, but faster.
        return [
            (self.x - math.sin(self.angle - alpha) * rad,
             self.y - math.cos(self.angle - alpha) * rad),
            (self.x - math.sin(self.angle + alpha) * rad,
             self.y - math.cos(self.angle + alpha) * rad),
            (self.x - math.sin(math.pi + self.angle - alpha) * rad,
             self.y - math.cos(math.pi + self.angle - alpha) * rad),
            (self.x - math.sin(math.pi + self.angle + alpha) * rad,
             self.y - math.cos(math.pi + self.angle + alpha) * rad),
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
