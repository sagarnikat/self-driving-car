"""Headless training loop — port of the evolution + benchmark flow in main.js.

- Training episodes use random (infinite) traffic, dt=1.0, same end conditions.
- Every --benchmark-every generations the NEW population (like JS) is tested
  on fixed traffic_1 for --benchmark-seconds, logging:
  generation,averageScore,bestScore,bestDistance,bestCarsPassed,bestTimeAlive
  (same header/rounding as BenchmarkStore).
- Exports best-so-far brain to models/ as JS-loadable JSON.

Usage:
  python -m simulation.train --generations 30 --population 100
  python -m simulation.train --generations 50 --population 50 --seed 12345 --benchmark-every 5
"""
import argparse
import csv
import json
import os
import sys
import time

# allow `python simulation/train.py` as well as `python -m simulation.train`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation import config as C
from simulation import rng as rng_mod
from simulation.evolution import Evolution
from simulation.network import NeuralNetwork
from simulation.simulate import run_episode

CSV_HEADER = "generation,averageScore,bestScore,bestDistance,bestCarsPassed,bestTimeAlive"


def run_benchmark(brains, lane_count, seconds, pattern_id="1"):
    """TEST-ONLY evaluation on fixed traffic. Never used for selection/mutation.

    Takes deep copies via run_episode (brains are cloned inside), scores are
    only logged to CSV — evo fitness is untouched.
    """
    max_steps = int(seconds * 60)  # dt=1 -> 60 steps/sec
    res = run_episode(brains, traffic_choice=str(pattern_id), lane_count=lane_count,
                      max_steps=max_steps, dt=1.0)
    fitnesses = res["fitnesses"]
    scores = [f.calculate_score() for f in fitnesses]
    best_idx = max(range(len(fitnesses)), key=lambda i: scores[i])
    best = fitnesses[best_idx]
    avg = sum(scores) / len(scores) if scores else 0
    return {
        "averageScore": int(round(avg)),
        "bestScore": int(round(scores[best_idx])),
        "bestDistance": int(round(best.get_distance())),
        "bestCarsPassed": int(best.cars_passed),
        "bestTimeAlive": round(best.get_time_alive(), 1),
    }


def export_brain(brain, fitness, generation, out_dir, name=None):
    os.makedirs(out_dir, exist_ok=True)
    if name is None:
        name = f"best_model_gen{generation}.json"
    path = os.path.join(out_dir, name)
    payload = {
        "name": os.path.splitext(name)[0],
        "architecture": list(brain.architecture),
        "brain": brain.to_json(),
        "fitness": int(round(fitness)),
        "generation": generation,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    # also write bare brain (architecture+levels) for direct NeuralNetwork.fromJSON
    bare_path = os.path.join(out_dir, os.path.splitext(name)[0] + ".brain.json")
    with open(bare_path, "w") as f:
        json.dump(brain.to_json(), f, indent=2)
    return path, bare_path


def main():
    ap = argparse.ArgumentParser(description="Headless evolutionary training (JS port)")
    ap.add_argument("--generations", type=int, default=30)
    ap.add_argument("--population", type=int, default=C.SIM["default_car_count"])
    ap.add_argument("--mutation-rate", type=float, default=C.EVOLUTION["mutation_rate"])
    ap.add_argument("--elitism", type=int, default=C.EVOLUTION["elitism_count"])
    ap.add_argument("--seed", type=int, default=C.EVOLUTION["seed"])
    ap.add_argument("--benchmark-every", type=int, default=C.EVOLUTION["benchmark_every"])
    ap.add_argument("--benchmark-seconds", type=float, default=C.EVOLUTION["benchmark_seconds"])
    ap.add_argument("--max-distance", type=float, default=C.EVOLUTION["max_distance"])
    ap.add_argument("--lane-count", type=int, default=C.ROAD["lane_count"])
    ap.add_argument("--max-speed", type=float, default=C.CAR["max_speed"],
                    help="AI car maxSpeed (px/frame); JS default 7")
    ap.add_argument("--train-traffic", type=str, default="random",
                    help="TRAINING traffic only. Must stay 'random' to avoid training on test data.")
    ap.add_argument("--test-traffic", type=str, default="1",
                    help="TEST-ONLY fixed pattern id (e.g. '1' for 3-lane traffic_1.json). Never used for evolution.")
    ap.add_argument("--run-dir", type=str, default=None,
                    help="If set, store weights + test results here (e.g. simulation/run_100gen_3lane). "
                         "Overrides --out-csv/--models-dir.")
    ap.add_argument("--out-csv", type=str, default="simulation/benchmark_scores_py.csv")
    ap.add_argument("--models-dir", type=str, default="simulation/models")
    ap.add_argument("--max-steps", type=int, default=10000,
                    help="fail-safe cap per training episode (frames)")
    args = ap.parse_args()

    # Strict train/test separation guard
    if str(args.train_traffic).strip().lower() != "random":
        raise SystemExit("Refusing to train on fixed traffic: --train-traffic must be 'random' "
                         "(test pattern is test-only).")
    if str(args.test_traffic).strip().lower() == "random":
        raise SystemExit("Refusing to test on random traffic: --test-traffic must be a fixed "
                         "pattern id like '1'.")

    # apply overrides to shared config (mirrors training panel)
    C.EVOLUTION["mutation_rate"] = args.mutation_rate
    C.EVOLUTION["elitism_count"] = args.elitism
    C.EVOLUTION["benchmark_every"] = args.benchmark_every
    C.EVOLUTION["benchmark_seconds"] = args.benchmark_seconds
    C.EVOLUTION["max_distance"] = args.max_distance
    C.NETWORK["mutation_amount"] = args.mutation_rate
    C.ROAD["lane_count"] = args.lane_count
    C.CAR["max_speed"] = args.max_speed

    # run-dir layout: weights/ + test_results.csv + train_log.csv + config.json
    if args.run_dir:
        run_dir = args.run_dir if os.path.isabs(args.run_dir) else os.path.abspath(args.run_dir)
        weights_dir = os.path.join(run_dir, "weights")
        os.makedirs(weights_dir, exist_ok=True)
        args.models_dir = weights_dir
        args.out_csv = os.path.join(run_dir, "test_results.csv")
        train_log_csv = os.path.join(run_dir, "train_log.csv")
        config_path = os.path.join(run_dir, "config.json")
    else:
        train_log_csv = None
        config_path = None

    rng_mod.set_seed(args.seed)
    arch = [C.SENSOR["ray_count"], C.NETWORK["hidden_size"], C.NETWORK["output_size"]]
    evo = Evolution(arch)
    evo.create_population(args.population)

    rows = []
    t0 = time.time()
    print(f"Training {args.generations} gens x {args.population} cars, seed={args.seed}, arch={arch}")
    print(f"TRAIN traffic=random (evolution) | TEST traffic=fixed pattern '{args.test_traffic}' "
          f"({args.lane_count}-lane, test-only, never used for selection)")
    print(f"Car maxSpeed={args.max_speed} laneCount={args.lane_count}")
    if config_path:
        with open(config_path, "w") as cf:
            json.dump({
                "generations": args.generations,
                "population": args.population,
                "mutation_rate": args.mutation_rate,
                "elitism": args.elitism,
                "seed": args.seed,
                "lane_count": args.lane_count,
                "max_speed": args.max_speed,
                "train_traffic": "random",
                "test_traffic": str(args.test_traffic),
                "test_traffic_file": f"data/traffic/{args.lane_count} lane/traffic_{args.test_traffic}.json",
                "benchmark_every": args.benchmark_every,
                "benchmark_seconds": args.benchmark_seconds,
                "architecture": arch,
                "note": "TEST scores never feed back into evolution; best model selected on TRAIN fitness only.",
            }, cf, indent=2)
    for gen in range(1, args.generations + 1):
        # TRAINING episode on random traffic ONLY — fitness from here drives evolution.
        res = run_episode([g.brain for g in evo.population], traffic_choice="random",
                          lane_count=args.lane_count, max_steps=args.max_steps, dt=1.0)
        for g, f in zip(evo.population, res["fitnesses"]):
            evo.set_fitness(g, f.calculate_score())
        finished = evo.generation
        evo.next_generation()

        lg = evo.log[-1]
        print(f"Gen {finished}: best={lg['best']:.0f} avg={lg['avg']:.0f} worst={lg['worst']:.0f} "
              f"steps={res['steps']} ({time.time()-t0:.1f}s)", flush=True)

        if args.benchmark_every > 0 and finished % args.benchmark_every == 0:
            # TEST-ONLY: scores logged, never written back to evo fitness.
            bench = run_benchmark([g.brain for g in evo.population],
                                  args.lane_count, args.benchmark_seconds,
                                  pattern_id=args.test_traffic)
            row = {"generation": finished, **bench}
            rows.append(row)
            print(f"  TEST Gen {finished} (fixed {args.lane_count}-lane traffic_{args.test_traffic}, "
                  f"test-only): avg={bench['averageScore']} best={bench['bestScore']} "
                  f"dist={bench['bestDistance']} passed={bench['bestCarsPassed']} t={bench['bestTimeAlive']}",
                  flush=True)

    # write CSV (same format as BenchmarkStore)
    out_csv = args.out_csv
    if not os.path.isabs(out_csv):
        out_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), out_csv) \
            if not out_csv.startswith("simulation/") else os.path.abspath(out_csv)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        f.write(CSV_HEADER + "\n")
        for r in rows:
            f.write(f"{r['generation']},{r['averageScore']},{r['bestScore']},"
                    f"{r['bestDistance']},{r['bestCarsPassed']},{r['bestTimeAlive']}\n")
    print(f"Wrote {len(rows)} TEST rows -> {out_csv}")

    # write per-generation TRAIN log (random traffic, drives evolution)
    if train_log_csv:
        with open(train_log_csv, "w", newline="") as f:
            f.write("generation,train_best,train_avg,train_worst\n")
            for e in evo.get_log():
                f.write(f"{e['generation']},{e['best']:.0f},{e['avg']:.0f},{e['worst']:.0f}\n")
        print(f"Wrote {len(evo.get_log())} TRAIN rows -> {train_log_csv}")

    # export best-so-far (selected on TRAIN fitness only, never test fitness)
    best = evo.get_best_so_far()
    if best is None:
        best = {"brain": evo.get_best_genome().brain, "fitness": evo.get_best_genome().fitness}
    models_dir = args.models_dir
    if not os.path.isabs(models_dir):
        models_dir = os.path.abspath(models_dir)
    full, bare = export_brain(best["brain"], best["fitness"], evo.generation - 1, models_dir,
                              name=f"best_model_gen{evo.generation - 1}_max{str(args.max_speed).replace('.', 'p')}_{args.lane_count}lane.json")
    print(f"Best TRAIN fitness {best['fitness']:.0f} -> {full}\nBare brain -> {bare}")
    print("Load in JS with: const nn = NeuralNetwork.fromJSON(brainJson.brain || brainJson); "
          "(see simulation/load_model.js)")


if __name__ == "__main__":
    main()
