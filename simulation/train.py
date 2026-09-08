"""Headless training loop — port of the evolution + benchmark flow in main.js.

- Training episodes use random (infinite) traffic, dt=1.0, same end conditions.
- Every --benchmark-every generations the NEW population (like JS) is tested
  on fixed traffic_1 for --benchmark-seconds, logging:
  generation,averageScore,bestScore,bestDistance,bestCarsPassed,bestTimeAlive
  (same header/rounding as BenchmarkStore).
- Exports best-so-far brain to models/ as JS-loadable JSON.
- Progress: tqdm bar over generations with live best/avg/steps + ETA.
- Checkpoints: every --checkpoint-every generations a JSON file with train
  scores, test scores and model weights is written to checkpoints/ (and CSVs
  are flushed incrementally, so a crash loses nothing). Resume with --resume.

Usage:
  python -m simulation.train --generations 30 --population 100
  python -m simulation.train --generations 50 --population 50 --seed 12345 --benchmark-every 5
  python -m simulation.train --generations 100 --population 100 --run-dir simulation/run1 --jobs 8
  python -m simulation.train --resume simulation/run1/checkpoints/checkpoint_gen20.json --generations 100
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
from simulation.simulate import run_episode, run_fixed_parallel

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - tqdm is in requirements.txt
    tqdm = None

CSV_HEADER = "generation,averageScore,bestScore,bestDistance,bestCarsPassed,bestTimeAlive"
TRAIN_LOG_HEADER = "generation,train_best,train_avg,train_worst,bestPassed,totalTraffic,fullPass,streak"


def _summarize_fixed(results):
    """Aggregate per-brain fixed-traffic results into a benchmark row dict."""
    scores = [r["score"] for r in results]
    best_idx = max(range(len(results)), key=lambda i: scores[i])
    best = results[best_idx]
    avg = sum(scores) / len(scores) if scores else 0
    return {
        "averageScore": int(round(avg)),
        "bestScore": int(round(scores[best_idx])),
        "bestDistance": int(round(best["distance"])),
        "bestCarsPassed": int(best["cars_passed"]),
        "bestTimeAlive": round(best["time_alive"], 1),
    }


def run_benchmark(brains, lane_count, seconds, pattern_id="1", jobs=1, end_on_full_pass=False):
    """TEST-ONLY evaluation on fixed traffic. Never used for selection/mutation.

    Brains are cloned inside run_episode (deep copies); with jobs>1 each brain
    is evaluated in its own process. Scores are only logged — evo fitness is
    untouched. The parent RNG sequence is identical for any job count.
    """
    max_steps = int(seconds * 60) if seconds and seconds > 0 else 0  # 0 = no time limit
    if jobs and jobs > 1:
        results = run_fixed_parallel(brains, lane_count, max_steps, 1.0,
                                     pattern_id, jobs, end_on_full_pass)
        return _summarize_fixed(results)
    res = run_episode(brains, traffic_choice=str(pattern_id), lane_count=lane_count,
                      max_steps=max_steps, dt=1.0, end_on_full_pass=end_on_full_pass)
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


def write_checkpoint(path, generation, evo, train_entry, bench, arch, config_snapshot,
                     extra=None):
    """Checkpoint file every N generations: scores + model data for resume."""
    best = evo.get_best_so_far()
    if best is None:
        best = {"brain": evo.get_best_genome().brain, "fitness": evo.get_best_genome().fitness}
    payload = {
        "generation": generation,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "architecture": list(arch),
        "train": {
            "best": round(train_entry["best"], 1),
            "avg": round(train_entry["avg"], 1),
            "worst": round(train_entry["worst"], 1),
        },
        "test": bench,  # None when no benchmark ran this generation
        "best_so_far": {
            "fitness": round(best["fitness"], 1),
            "generation": generation,
        },
        "brain": best["brain"].to_json(),
        "rng_state": rng_mod.get_state(),
        "evo": evo.to_json(),  # full population so --resume continues exactly
        "config": config_snapshot,
    }
    if extra:
        payload["fixed_map"] = extra
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, path)
    return path


def load_checkpoint(path):
    with open(path, "r") as f:
        return json.load(f)


def _open_append_csv(path, header):
    """Open a CSV for incremental logging; write header only if new/empty."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    f = open(path, "a", newline="")
    if is_new:
        f.write(header + "\n")
        f.flush()
    return f


def main():
    ap = argparse.ArgumentParser(description="Headless evolutionary training (JS port)")
    ap.add_argument("--generations", type=int, default=30,
                    help="total generations to reach (used as resume target with --resume)")
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
                    help="TRAINING traffic: 'random' (default, infinite) or a fixed pattern id "
                         "like '1' to train on data/traffic/<N> lane/traffic_<id>.json only.")
    ap.add_argument("--test-traffic", type=str, default="1",
                    help="TEST-ONLY fixed pattern id (e.g. '1' for 3-lane traffic_1.json). Never used for evolution.")
    ap.add_argument("--end-on-full-pass", action="store_true",
                    help="end the generation early as soon as any car overtakes ALL traffic cars "
                         "(fixed-map mode: move to next generation, no time limit needed)")
    ap.add_argument("--full-pass-streak-stop", type=int, default=0,
                    help="stop training early after N CONSECUTIVE generations where the best car "
                         "overtakes all traffic cars (0 disables, e.g. 5 = stop after 5 in a row)")
    ap.add_argument("--no-pass-seconds", type=float, default=None,
                    help="override anti-stall no-pass kill window in seconds (0 disables). "
                         "Default: keep config value.")
    ap.add_argument("--stall-seconds", type=float, default=None,
                    help="override stall kill window in seconds (0 disables). "
                         "Default: keep config value.")
    ap.add_argument("--run-dir", type=str, default=None,
                    help="If set, store weights + test results here (e.g. simulation/run_100gen_3lane). "
                         "Overrides --out-csv/--models-dir.")
    ap.add_argument("--out-csv", type=str, default="simulation/benchmark_scores_py.csv")
    ap.add_argument("--models-dir", type=str, default="simulation/models")
    ap.add_argument("--max-steps", type=int, default=10000,
                    help="fail-safe cap per training episode (frames). 0 = NO time limit: "
                         "generation ends only when all cars damaged / maxDistance / full-pass.")
    ap.add_argument("--checkpoint-every", type=int, default=5,
                    help="write a score+model checkpoint JSON every N generations (0 disables)")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel workers for the fixed-traffic TEST benchmark only "
                         "(training stays single-process to preserve exact RNG order)")
    ap.add_argument("--resume", type=str, default=None,
                    help="resume from a checkpoints/checkpoint_genN.json file")
    ap.add_argument("--no-progress", action="store_true",
                    help="disable the tqdm progress bar (plain log lines only)")
    ap.add_argument("--quiet", action="store_true",
                    help="only show the progress bar, hide per-generation log lines")
    args = ap.parse_args()

    # Train/test separation: random=training, fixed=test. Fixed-map training is
    # allowed explicitly (overtake-based mode) but flagged so results aren't
    # confused with random-trained runs.
    train_traffic_raw = str(args.train_traffic).strip().lower()
    training_on_fixed = train_traffic_raw != "random"
    if str(args.test_traffic).strip().lower() == "random":
        raise SystemExit("Refusing to test on random traffic: --test-traffic must be a fixed "
                         "pattern id like '1'.")
    if training_on_fixed and train_traffic_raw == str(args.test_traffic).strip().lower():
        print(f"NOTE: training directly on fixed test map '{args.train_traffic}' "
              f"({args.lane_count}-lane). Scores are map-specific, not general driving.")

    # apply overrides to shared config (mirrors training panel)
    C.EVOLUTION["mutation_rate"] = args.mutation_rate
    C.EVOLUTION["elitism_count"] = args.elitism
    C.EVOLUTION["benchmark_every"] = args.benchmark_every
    C.EVOLUTION["benchmark_seconds"] = args.benchmark_seconds
    C.EVOLUTION["max_distance"] = args.max_distance
    if args.no_pass_seconds is not None:
        C.EVOLUTION["no_pass_seconds"] = args.no_pass_seconds
    if args.stall_seconds is not None:
        C.EVOLUTION["stall_seconds"] = args.stall_seconds
    C.NETWORK["mutation_amount"] = args.mutation_rate
    C.ROAD["lane_count"] = args.lane_count
    C.CAR["max_speed"] = args.max_speed

    # run-dir layout: weights/ + checkpoints/ + test_results.csv + train_log.csv + config.json
    if args.run_dir:
        run_dir = args.run_dir if os.path.isabs(args.run_dir) else os.path.abspath(args.run_dir)
        weights_dir = os.path.join(run_dir, "weights")
        os.makedirs(weights_dir, exist_ok=True)
        args.models_dir = weights_dir
        args.out_csv = os.path.join(run_dir, "test_results.csv")
        train_log_csv = os.path.join(run_dir, "train_log.csv")
        config_path = os.path.join(run_dir, "config.json")
        ckpt_dir = os.path.join(run_dir, "checkpoints")
    else:
        train_log_csv = None
        config_path = None
        models_abs = args.models_dir if os.path.isabs(args.models_dir) \
            else os.path.abspath(args.models_dir)
        ckpt_dir = os.path.join(models_abs, "checkpoints")

    arch = [C.SENSOR["ray_count"], C.NETWORK["hidden_size"], C.NETWORK["output_size"]]
    config_snapshot = {
        "generations": args.generations,
        "population": args.population,
        "mutation_rate": args.mutation_rate,
        "elitism": args.elitism,
        "seed": args.seed,
        "lane_count": args.lane_count,
        "max_speed": args.max_speed,
        "train_traffic": str(args.train_traffic),
        "train_traffic_file": (f"data/traffic/{args.lane_count} lane/traffic_{args.train_traffic}.json"
                               if training_on_fixed else "procedural-random"),
        "test_traffic": str(args.test_traffic),
        "test_traffic_file": f"data/traffic/{args.lane_count} lane/traffic_{args.test_traffic}.json",
        "benchmark_every": args.benchmark_every,
        "benchmark_seconds": args.benchmark_seconds,
        "max_steps": args.max_steps,
        "end_on_full_pass": bool(args.end_on_full_pass),
        "full_pass_streak_stop": int(args.full_pass_streak_stop),
        "no_pass_seconds": C.EVOLUTION["no_pass_seconds"],
        "stall_seconds": C.EVOLUTION["stall_seconds"],
        "jobs": args.jobs,
        "architecture": arch,
        "note": ("Fixed-map training: evolution directly on the test map; "
                 "generation ends on full overtake, training stops after N consecutive full passes."
                 if training_on_fixed else
                 "TEST scores never feed back into evolution; best model selected on TRAIN fitness only."),
    }

    # --- init or resume -----------------------------------------------------
    start_gen = 1
    if args.resume:
        ckpt = load_checkpoint(args.resume)
        saved_cfg = ckpt.get("config", {})
        for k in ("lane_count", "max_speed", "mutation_rate", "elitism",
                  "benchmark_seconds", "seed"):
            if k in saved_cfg and saved_cfg[k] != config_snapshot.get(k):
                print(f"WARNING: checkpoint {k}={saved_cfg[k]} differs from "
                      f"current {k}={config_snapshot.get(k)}; using checkpoint value.")
        for k in ("lane_count", "max_speed", "mutation_rate", "elitism",
                  "benchmark_seconds", "seed"):
            if k in saved_cfg:
                config_snapshot[k] = saved_cfg[k]
        C.EVOLUTION["mutation_rate"] = config_snapshot["mutation_rate"]
        C.EVOLUTION["elitism_count"] = config_snapshot["elitism"]
        C.EVOLUTION["benchmark_seconds"] = config_snapshot["benchmark_seconds"]
        C.ROAD["lane_count"] = config_snapshot["lane_count"]
        C.CAR["max_speed"] = config_snapshot["max_speed"]
        args.lane_count = config_snapshot["lane_count"]
        args.max_speed = config_snapshot["max_speed"]
        args.seed = config_snapshot["seed"]
        arch = list(ckpt.get("architecture", arch))
        evo = Evolution.from_json(ckpt["evo"])
        rng_mod.set_state(ckpt["rng_state"])
        start_gen = int(ckpt["generation"]) + 1
        print(f"Resumed from {args.resume}: continuing at generation {start_gen}")
    else:
        rng_mod.set_seed(args.seed)
        evo = Evolution(arch)
        evo.create_population(args.population)

    if start_gen > args.generations:
        raise SystemExit(f"Checkpoint is already at generation {start_gen - 1} "
                         f"(>= --generations {args.generations}); nothing to do.")

    # --- progress + log setup ----------------------------------------------
    use_bar = tqdm is not None and not args.no_progress
    pbar = tqdm(total=args.generations, initial=start_gen - 1, unit="gen",
                desc="Training", disable=not use_bar) if use_bar else None

    def log(msg):
        if args.quiet and use_bar:
            return
        if pbar is not None:
            pbar.write(msg)
        else:
            print(msg, flush=True)

    # --- output files (incremental: flushed every generation) ---------------
    out_csv = args.out_csv
    if not os.path.isabs(out_csv):
        out_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), out_csv) \
            if not out_csv.startswith("simulation/") else os.path.abspath(out_csv)
    test_f = _open_append_csv(out_csv, CSV_HEADER)
    train_f = _open_append_csv(train_log_csv, TRAIN_LOG_HEADER) if train_log_csv else None

    t0 = time.time()
    train_desc = (f"fixed map '{args.train_traffic}' ({args.lane_count}-lane, overtake mode)"
                  if training_on_fixed else "random (evolution)")
    log(f"Training gens {start_gen}..{args.generations} x {args.population} cars, "
        f"seed={args.seed}, arch={arch}")
    if training_on_fixed:
        log(f"TRAIN traffic=fixed pattern '{args.train_traffic}' ({train_desc}) | "
            f"TEST traffic=fixed pattern '{args.test_traffic}'")
        if args.max_steps and args.max_steps > 0:
            log(f"WARNING: --max-steps {args.max_steps} caps fixed-map episodes; "
                f"use --max-steps 0 for no time limit.")
        log(f"STOP RULES: end generation when any car overtakes ALL traffic cars "
            f"(--end-on-full-pass={args.end_on_full_pass}); "
            f"stop training after {args.full_pass_streak_stop} consecutive full-pass gens "
            f"(0=disabled). no_pass={C.EVOLUTION['no_pass_seconds']}s "
            f"stall={C.EVOLUTION['stall_seconds']}s max_steps="
            f"{args.max_steps if args.max_steps > 0 else 'UNLIMITED (fail-safe 200k steps)'}")
    else:
        log(f"TRAIN traffic=random (evolution) | TEST traffic=fixed pattern '{args.test_traffic}' "
            f"({args.lane_count}-lane, test-only, never used for selection)")
    log(f"Car maxSpeed={args.max_speed} laneCount={args.lane_count} "
        f"jobs={args.jobs} checkpoint_every={args.checkpoint_every}")
    if config_path:
        with open(config_path, "w") as cf:
            json.dump(config_snapshot, cf, indent=2)

    best_so_far_fit = None
    _best = evo.get_best_so_far()
    if _best is not None:
        best_so_far_fit = _best["fitness"]

    test_rows = 0
    full_pass_streak = 0
    stopped_early = False
    try:
        for gen in range(start_gen, args.generations + 1):
            # TRAINING episode — fitness from here drives evolution.
            # Random mode: infinite traffic. Fixed mode: test map only.
            res = run_episode([g.brain for g in evo.population], traffic_choice=str(args.train_traffic),
                              lane_count=args.lane_count, max_steps=args.max_steps, dt=1.0,
                              end_on_full_pass=bool(args.end_on_full_pass))
            for g, f in zip(evo.population, res["fitnesses"]):
                evo.set_fitness(g, f.calculate_score())
            # overtake stats for this generation (fixed-map stopping rules)
            total_traffic = int(res.get("total_traffic", 0) or 0)
            best_passed = max((f.cars_passed for f in res["fitnesses"]), default=0)
            full_pass = bool(total_traffic > 0 and best_passed >= total_traffic)
            if args.end_on_full_pass and total_traffic > 0:
                full_pass_streak = full_pass_streak + 1 if full_pass else 0
            finished = evo.generation
            evo.next_generation()

            lg = evo.log[-1]
            if train_f is not None:
                train_f.write(f"{finished},{lg['best']:.0f},{lg['avg']:.0f},{lg['worst']:.0f},"
                              f"{best_passed},{total_traffic},{int(full_pass)},{full_pass_streak}\n")
                train_f.flush()
            msg = (f"Gen {finished}: best={lg['best']:.0f} avg={lg['avg']:.0f} "
                   f"worst={lg['worst']:.0f} steps={res['steps']} "
                   f"passed={best_passed}" + (f"/{total_traffic}" if total_traffic > 0 else "") +
                   f"{' FULL-PASS' if full_pass else ''}"
                   f"{f' streak={full_pass_streak}' if args.full_pass_streak_stop > 0 else ''} "
                   f"({time.time()-t0:.1f}s)")
            bench = None
            if args.benchmark_every > 0 and finished % args.benchmark_every == 0:
                # TEST-ONLY: scores logged, never written back to evo fitness.
                # Skipped automatically when training directly on the same map
                # (train == test) unless forced — train log already IS the benchmark.
                if training_on_fixed and train_traffic_raw == str(args.test_traffic).strip().lower():
                    log(msg + " | (benchmark skipped: training on same fixed map)")
                    bench = None
                else:
                    bench = run_benchmark([g.brain for g in evo.population],
                                          args.lane_count, args.benchmark_seconds,
                                          pattern_id=args.test_traffic, jobs=args.jobs)
                    test_f.write(f"{finished},{bench['averageScore']},{bench['bestScore']},"
                                 f"{bench['bestDistance']},{bench['bestCarsPassed']},"
                                 f"{bench['bestTimeAlive']}\n")
                    test_f.flush()
                    test_rows += 1
                    msg += (f" | TEST avg={bench['averageScore']} best={bench['bestScore']} "
                            f"dist={bench['bestDistance']} passed={bench['bestCarsPassed']} "
                            f"t={bench['bestTimeAlive']}")
                    log(msg)
            else:
                log(msg)
            if pbar is not None:
                postfix = {"best": f"{lg['best']:.0f}", "avg": f"{lg['avg']:.0f}",
                           "steps": res["steps"],
                           "pass": f"{best_passed}/{total_traffic}" if total_traffic > 0 else best_passed}
                if bench is not None:
                    postfix["test"] = bench["bestScore"]
                pbar.set_postfix(postfix)
                pbar.update(1)

            # best-so-far snapshot (model data, updated on improvement)
            cur = evo.get_best_so_far()
            if cur is not None and (best_so_far_fit is None or cur["fitness"] > best_so_far_fit):
                best_so_far_fit = cur["fitness"]
                export_brain(cur["brain"], cur["fitness"], finished, args.models_dir,
                             name="best_so_far.json")

            # periodic checkpoint: scores + model data every N generations
            if args.checkpoint_every > 0 and (
                    finished % args.checkpoint_every == 0 or finished == args.generations):
                ckpt_path = os.path.join(ckpt_dir, f"checkpoint_gen{finished}.json")
                write_checkpoint(ckpt_path, finished, evo, lg, bench, arch, config_snapshot,
                                 extra={"bestPassed": best_passed, "totalTraffic": total_traffic,
                                        "fullPass": full_pass, "streak": full_pass_streak})
                log(f"  checkpoint -> {ckpt_path}")

            # fixed-map early stop: N consecutive generations overtaking everything
            if args.full_pass_streak_stop > 0 and full_pass_streak >= args.full_pass_streak_stop:
                stopped_early = True
                # ensure a checkpoint at the stopping generation
                if args.checkpoint_every > 0:
                    ckpt_path = os.path.join(ckpt_dir, f"checkpoint_gen{finished}.json")
                    write_checkpoint(ckpt_path, finished, evo, lg, bench, arch, config_snapshot,
                                     extra={"bestPassed": best_passed, "totalTraffic": total_traffic,
                                            "fullPass": full_pass, "streak": full_pass_streak,
                                            "stoppedEarly": True})
                    log(f"  checkpoint -> {ckpt_path}")
                log(f"STOPPING EARLY at gen {finished}: {full_pass_streak} consecutive "
                    f"full-pass generations (best overtook all {total_traffic} cars).")
                if pbar is not None:
                    pbar.update(args.generations - finished)
                break
    finally:
        test_f.close()
        if train_f is not None:
            train_f.close()
        if pbar is not None:
            pbar.close()

    # count rows for the summary (CSVs were flushed incrementally)
    with open(out_csv) as f:
        total_test_rows = max(0, sum(1 for _ in f) - 1)
    print(f"TEST rows in {out_csv}: {total_test_rows} (this run added {test_rows})")
    if train_log_csv:
        print(f"TRAIN log -> {train_log_csv}")
    if stopped_early:
        print(f"STOPPED EARLY: {full_pass_streak} consecutive full-pass generations "
              f"(overtake-all streak rule).")

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
