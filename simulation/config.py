"""Mirror of config/config.js — single source of truth for the Python headless port.

All numbers, units and defaults match the JS exactly so fitness and
physics behave identically. dt is normalised: 1.0 == one 60fps frame
(JS: dt = (time-last)/16.67, clamped to 1).
"""
import math

CAR = {
    "width": 30,
    "height": 50,
    "acceleration": 0.2,
    "max_speed": 7,
    "friction": 0.05,
    "can_rotate": False,
    "turn_angle": 0.02,
    "lateral_speed": 2,
    "start_lane": 1,
    "start_y": 100,
}

ROAD = {
    "lane_count": 3,
    "width_factor": 0.9,
    "infinity": 1000000,
    # headless canvas width used to derive road geometry (JS: carCanvas.width=200)
    "car_canvas_width": 200,
}

SENSOR = {
    "ray_count": 7,
    "ray_length": 150,
    "ray_spread": math.pi / 2,
}

NETWORK = {
    "hidden_size": 10,
    "output_size": 4,
    "mutation_amount": 0.1,
}

EVOLUTION = {
    "elitism_count": 2,
    "mutation_rate": 0.1,
    "seed": 12345,
    "max_distance": 8000,
    "autosave_every": 5,
    "stall_seconds": 5,
    "no_pass_seconds": 10,
    "benchmark_every": 5,
    "benchmark_seconds": 30,
}

SIM = {
    "default_car_count": 100,
}

FITNESS = {
    "passed_bonus": 200,
    "time_alive_multiplier": 10,
}

TRAFFIC = {
    "row_spacing": 300,
    "max_cars_per_row": 3,
    "initial_rows": 10,
    "generate_ahead_rows": 5,
    "remove_behind_offset": 500,
    "view_distance": 500,
    "nearby_distance": 300,
    "default_car_width": 30,
    "default_car_height": 50,
    "default_speed": 2,
}


def brain_architecture():
    return [SENSOR["ray_count"], NETWORK["hidden_size"], NETWORK["output_size"]]
