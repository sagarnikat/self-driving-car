"""Headless episode runner — mirrors src/main.js animate() without rendering.

Step order per frame (dt=1.0 fixed == 60fps):
 1. traffic cars update (road.borders, [], dt)
 2. AI cars update (road.borders, traffic, dt)
 3. fitness.update + check_no_pass per car
 4. best car = max distance; generator.update(best.y) for random traffic
End when all damaged or best distance >= max_distance or max_steps.
"""
from . import config as C
from .car import Car, Road
from .fitness import Fitness
from .traffic import TrafficGenerator, load_fixed_pattern


def build_road(lane_count=None):
    lane_count = lane_count or C.ROAD["lane_count"]
    w = C.ROAD["car_canvas_width"] * C.ROAD["width_factor"]
    return Road(C.ROAD["car_canvas_width"] / 2, w, lane_count)


def run_episode(brains, traffic_choice="random", lane_count=None, max_steps=10000, dt=1.0,
                benchmark_mode=False):
    """brains: list of NeuralNetwork (used in order). Returns dict with cars/fitnesses/steps."""
    lane_count = lane_count or C.ROAD["lane_count"]
    road = build_road(lane_count)

    if str(traffic_choice).strip().lower() == "random" and not benchmark_mode:
        generator = TrafficGenerator(lane_count, road)
        traffic = generator.get_cars()
    elif str(traffic_choice).strip().lower() == "random" and benchmark_mode:
        # benchmark never uses random; caller passes fixed pattern instead
        generator = TrafficGenerator(lane_count, road)
        traffic = generator.get_cars()
    else:
        generator = None
        try:
            pid = int(str(traffic_choice).strip())
        except ValueError:
            pid = 1
        traffic = load_fixed_pattern(lane_count, pid, road)

    cars = []
    for b in brains:
        car = Car(
            road.get_lane_center(C.CAR["start_lane"]),
            C.CAR["start_y"],
            C.CAR["width"],
            C.CAR["height"],
            "AI",
            C.CAR["max_speed"],
        )
        # deep-assign brain so episode mutations never leak
        from .network import NeuralNetwork as NN
        car.brain = NN.from_json(b.to_json())
        cars.append(car)

    fitnesses = [Fitness(c) for c in cars]
    # Fitness needs live traffic view; we pass current list each step.

    steps = 0
    for step in range(max_steps):
        steps = step + 1
        for t in list(traffic):
            t.update(road.borders, [], dt)
        for i, car in enumerate(cars):
            car.update(road.borders, traffic, dt)
            fitnesses[i].update(traffic)
            fitnesses[i].check_no_pass(dt)

        if cars:
            best = max(fitnesses, key=lambda f: f.get_distance())
            best_y = best.car.y
        else:
            break

        if generator is not None:
            generator.update(best_y)
            traffic = generator.get_cars()

        # generation end conditions (mirrors generationFinished)
        if cars and all(c.damaged for c in cars):
            break
        if best.get_distance() >= C.EVOLUTION["max_distance"]:
            break
        # benchmark timeout handled by caller via max_steps
    return {"cars": cars, "fitnesses": fitnesses, "steps": steps, "road": road, "traffic": traffic}
