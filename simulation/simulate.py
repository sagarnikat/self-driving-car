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
from .network import NeuralNetwork as NN
from .traffic import TrafficGenerator, load_fixed_pattern


def build_road(lane_count=None):
    lane_count = lane_count or C.ROAD["lane_count"]
    w = C.ROAD["car_canvas_width"] * C.ROAD["width_factor"]
    return Road(C.ROAD["car_canvas_width"] / 2, w, lane_count)


def _resolve_traffic(traffic_choice, lane_count, road, benchmark_mode):
    """Returns (traffic, generator). Fixed patterns are static; random uses a generator."""
    if str(traffic_choice).strip().lower() == "random":
        # benchmark never uses random; caller passes a fixed pattern instead
        generator = TrafficGenerator(lane_count, road)
        return generator.get_cars(), generator
    try:
        pid = int(str(traffic_choice).strip())
    except ValueError:
        pid = 1
    return load_fixed_pattern(lane_count, pid, road), None


def _make_ai_cars(brains, road, init_brain=True):
    cars = []
    for b in brains:
        car = Car(
            road.get_lane_center(C.CAR["start_lane"]),
            C.CAR["start_y"],
            C.CAR["width"],
            C.CAR["height"],
            "AI",
            C.CAR["max_speed"],
            init_brain=init_brain,
        )
        # deep-assign brain so episode mutations never leak
        car.brain = NN.from_json(b.to_json())
        cars.append(car)
    return cars


def run_episode(brains, traffic_choice="random", lane_count=None, max_steps=10000, dt=1.0,
                benchmark_mode=False, end_on_full_pass=False):
    """brains: list of NeuralNetwork (used in order). Returns dict with cars/fitnesses/steps."""
    lane_count = lane_count or C.ROAD["lane_count"]
    road = build_road(lane_count)
    traffic, generator = _resolve_traffic(traffic_choice, lane_count, road, benchmark_mode)

    cars = _make_ai_cars(brains, road)

    fitnesses = [Fitness(c) for c in cars]
    # Fitness needs live traffic view; we pass current list each step.

    start_y = C.CAR["start_y"]
    max_dist = C.EVOLUTION["max_distance"]
    borders = road.borders
    n = len(cars)
    ys = [c.y for c in cars]
    alive = list(range(n))

    # Fixed-map full-pass target: number of traffic cars to overtake.
    # For random traffic the set changes over time, so this mode is only
    # meaningful for fixed patterns (static list).
    full_pass_target = len(traffic) if end_on_full_pass and generator is None else 0

    # max_steps <= 0 means "no time limit": run until all damaged /
    # max_distance / full-pass. Keep a huge fail-safe cap so a bug or a
    # car cruising forever on an empty road can't hang training.
    if max_steps is None or max_steps <= 0:
        step_cap = 200000
    else:
        step_cap = max_steps

    steps = 0
    for step in range(step_cap):
        steps = step + 1
        for t in list(traffic):
            t.update(borders, [], dt)
        still_alive = []
        for i in alive:
            car = cars[i]
            car.update(borders, traffic, dt)
            fitnesses[i].update(traffic)
            fitnesses[i].check_no_pass(dt)
            ys[i] = car.y
            if not car.damaged:
                still_alive.append(i)
        alive = still_alive

        # best car = max distance (first-wins on ties, like max() in the old code)
        best_dist = -1.0
        best_y = start_y
        for i in range(n):
            d = start_y - ys[i]
            if d < 0:
                d = 0
            if d > best_dist:
                best_dist = d
                best_y = ys[i]

        if generator is not None:
            generator.update(best_y)
            traffic = generator.get_cars()

        # generation end conditions (mirrors generationFinished)
        if not alive:
            break
        if best_dist >= max_dist:
            break
        # fixed-map mode: move to next generation as soon as any car has
        # overtaken every traffic car (no time limit needed).
        if full_pass_target > 0 and any(f.cars_passed >= full_pass_target for f in fitnesses):
            break
    total_traffic = full_pass_target  # 0 when not in full-pass mode (no fixed target)
    return {"cars": cars, "fitnesses": fitnesses, "steps": steps, "road": road, "traffic": traffic,
            "total_traffic": total_traffic}


# ---------------------------------------------------------------------------
# Parallel evaluation for FIXED-traffic (test-only) episodes.
#
# Fixed-traffic cars never depend on AI cars and AI cars never interact with
# each other, so each brain can be evaluated in its own process. Random
# (training) traffic stays single-process: it is coupled through the shared
# generator and the global seeded RNG order must be preserved exactly.
# ---------------------------------------------------------------------------

def draws_for_architecture(arch):
    """Number of seeded_random() draws Level._randomize makes for `arch`."""
    total = 0
    for k in range(len(arch) - 1):
        total += arch[k] * arch[k + 1] + arch[k + 1]  # weights row-major + biases
    return total


def _eval_one_fixed(job):
    """Worker: evaluate a single brain on fixed traffic. Top-level for pickling."""
    brain_json, lane_count, max_steps, dt, pattern_id, end_on_full_pass = job
    # Late imports so the worker doesn't need the parent's RNG state.
    from . import rng as rng_mod  # noqa: F401  (imported for parity; no draws here)
    from .car import Car as _Car
    from .fitness import Fitness as _Fitness
    from .network import NeuralNetwork as _NN
    from .traffic import load_fixed_pattern as _load, TrafficGenerator as _TG  # noqa: F401

    road = build_road(lane_count)
    traffic = _load(lane_count, pattern_id, road)
    brain = _NN.from_json(brain_json)
    car = _Car(
        road.get_lane_center(C.CAR["start_lane"]),
        C.CAR["start_y"],
        C.CAR["width"],
        C.CAR["height"],
        "AI",
        C.CAR["max_speed"],
        init_brain=False,  # brain assigned below; avoids RNG draws in the worker
    )
    car.brain = brain
    fit = _Fitness(car)
    borders = road.borders
    start_y = C.CAR["start_y"]
    max_dist = C.EVOLUTION["max_distance"]
    full_pass_target = len(traffic) if end_on_full_pass else 0
    step_cap = 200000 if (max_steps is None or max_steps <= 0) else max_steps
    steps = 0
    for step in range(step_cap):
        steps = step + 1
        for t in list(traffic):
            t.update(borders, [], dt)
        car.update(borders, traffic, dt)
        fit.update(traffic)
        fit.check_no_pass(dt)
        if car.damaged:
            break
        if fit.get_distance() >= max_dist:
            break
        if full_pass_target > 0 and fit.cars_passed >= full_pass_target:
            break
    return {
        "score": fit.calculate_score(),
        "distance": fit.get_distance(),
        "cars_passed": fit.cars_passed,
        "time_alive": fit.get_time_alive(),
    }


def run_fixed_parallel(brains, lane_count, max_steps, dt, pattern_id, jobs, end_on_full_pass=False):
    """Evaluate brains on fixed traffic across `jobs` processes.

    Returns a list of result dicts in input order. Keeps the parent's global
    RNG sequence identical to a sequential run by advancing it past the
    throwaway brain draws that sequential Car() construction would consume.
    """
    import concurrent.futures as cf
    import multiprocessing as mp

    from . import rng as rng_mod

    brain_jsons = [b.to_json() for b in brains]
    if brain_jsons:
        # Mirror the throwaway draws sequential Car() construction consumes:
        # one fresh NeuralNetwork([ray_count, hidden, output]) per car.
        arch = [C.SENSOR["ray_count"], C.NETWORK["hidden_size"], C.NETWORK["output_size"]]
        for _ in range(len(brain_jsons) * draws_for_architecture(arch)):
            rng_mod.seeded_random()

    try:
        pid = int(str(pattern_id).strip())
    except ValueError:
        pid = 1
    jobs_list = [(bj, lane_count, max_steps, dt, pid, end_on_full_pass) for bj in brain_jsons]
    try:
        ctx = mp.get_context("fork")
    except (AttributeError, ValueError):
        ctx = None
    if ctx is not None:
        executor = cf.ProcessPoolExecutor(max_workers=jobs, mp_context=ctx)
    else:  # pragma: no cover - non-fork platforms
        executor = cf.ProcessPoolExecutor(max_workers=jobs)
    with executor:
        return list(executor.map(_eval_one_fixed, jobs_list))
