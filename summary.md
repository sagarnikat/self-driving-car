# Self-Driving Car AI Trainer — Project Summary

> Purpose of this file: give an AI assistant everything it needs to understand,
> modify, and extend this project without reading every source file first.

## 1. What this project is

A neuroevolution trainer for a top-down 2D driving game. Small feed-forward neural
networks learn to steer a car down a multi-lane road while avoiding traffic. Two
frontends share the same logic:

- **Browser app (JS):** interactive training with live canvas rendering
  (`index.html` + `src/`). Serve over HTTP, open in browser.
- **Headless trainer (Python):** fast, exact port of the JS logic for bulk training
  on CPU (`simulation/`). Exports models that load back into the browser.

Both evolve a population of networks with a genetic algorithm and score them with
the same fitness function.

## 2. Core concepts (both frontends)

### 2.1 Coordinate system and units

- Pixels. Canvas/road is 200px wide (`sim.carCanvasWidth`), road width = 200 × 0.9.
- **y decreases forward** (cars drive toward negative y). Spawn: lane 1, `y = 100`.
- `distance = 100 - car.y` (clamped ≥ 0).
- `dt = 1.0` ≡ one 60fps frame. JS computes `dt = (time-last)/16.67` clamped to
  `[0, 3]` (and forced to 1 on first/invalid frame); Python always uses `dt=1.0`.
- Speeds are px/frame: AI `maxSpeed = 7`, traffic speed `2`, lateral speed `2`,
  acceleration `0.2`, friction `0.05`.

### 2.2 Car physics (`src/core/car.js`, `simulation/car.py`)

- Car types: `"AI"` (sensor + brain), `"KEYS"` (browser keyboard driving),
  `"DUMMY"` (traffic: drives straight, `forward=true`, no sensor/brain).
- Per frame: move (accel/friction/clamp) → rebuild 4-point polygon → collision
  check (road borders + traffic polygons via segment intersection) → stall check
  (AI with `speed <= 0` for `stallSeconds × 60` frames is marked damaged).
- Steering: `canRotate` is **false**, so cars never rotate (`angle` stays 0);
  left/right move the car laterally at `lateralSpeed`.
- Sensor inference sets controls for the **next** frame.

### 2.3 Sensors (`src/core/sensor.js`)

- 7 rays (`rayCount`), length 150px, spread 90° (`raySpread = π/2`), cast from car
  center fanning forward.
- Each ray returns the nearest intersection with road borders or traffic polygons,
  or `null`. Network input per ray: `0` if null else `1 - offset`.

### 2.4 Neural network (`src/ai/network.js`, `simulation/network.py`)

- Architecture `[7, 10, 4]` (7 sensors → 10 hidden → 4 outputs:
  forward / left / right / reverse).
- `weights[input][output]` (rows = inputs). Binary step activation:
  `output = (Σ input·weight > bias) ? 1 : 0` (strictly greater).
- Random init uniform in `[-1, 1]` (weights row-major, then biases).
- Mutation: `lerp(old, rand·2−1, amount)` for every bias then every weight.
- Serialization: `toJSON/fromJSON` → `{architecture, levels:[{inputCount,
  outputCount, biases, weights}]}`. Python is byte-compatible with JS.
- Python uses NumPy for the forward pass (identical math).

### 2.5 Evolution (`src/ai/evolution.js`, `simulation/evolution.py`)

- `Genome {brain, fitness}`. `createPopulation(n)` (gen 1) or
  `seedPopulation(n, brain)` (genome 0 intact, rest mutated — used when loading a
  saved model to continue training).
- Each generation: rank by fitness → **elitism** (top N copied unchanged,
  `elitismCount = 2`) → fill rest via **tournament selection (k=3)** +
  **per-level crossover** (each level copied wholly from parent A or B, p=0.5) +
  mutation of every non-elite child.
- Tracks `log [{generation, best, avg, worst}]`, `bestGenome`, `bestSoFar`.
- Reproducibility: all randomness flows through a seeded **mulberry32** PRNG
  (`SeededRandom` in JS overrides `Math.random`; `simulation/rng.py` in Python,
  default seed `12345`). Same seed ⇒ same traffic, population, mutations.

### 2.6 Fitness (`src/ai/fitness.js`, `simulation/fitness.py`)

- `distance` = forward progress; `carsPassed` = overtaken traffic cars (a traffic
  car counts once, when the AI's y crosses from behind to ahead of it);
  `timeAlive` = seconds alive (frozen at damage; JS uses wall clock, Python uses
  simulated `steps/60`).
- `score = distance + carsPassed × 200 + (damaged ? 0 : timeAlive × 10)`.
- **Best car = max distance** (camera follows it; its brain is visualized/evolved).
- Generation ends when all cars damaged, or best distance ≥ `maxDistance` (8000),
  or `max_steps` cap (Python fail-safe, default 10000).
- Anti-stall: AI killed after `noPassSeconds × 60` frames (10s) without passing.

### 2.7 Traffic

- **Random (training only):** procedural infinite traffic. Rows every 300px,
  0–2 cars per row on random lanes (`maxCarsPerRow = 3`, capped at lanes−1),
  speed 2. Generator spawns 10 rows ahead initially, adds rows to stay 5 rows
  ahead of the best car, removes cars 500px behind it.
- **Fixed (test only):** JSON patterns in `data/traffic/<N> lane/traffic_<K>.json`:
  `{laneCount, carWidth, carHeight, cars:[{lane, y, speed}]}` with `y` negative
  (ahead of spawn). 3-lane has only `traffic_1.json`; 4-lane has 1–5.
- **Strict train/test separation:** evolution/fitness selection NEVER uses fixed
  traffic; benchmarks NEVER feed back into evolution. `train.py` refuses
  `--train-traffic != random` and `--test-traffic == random`.

## 3. Browser app (JS)

Serve the repo root (`python3 -m http.server 8000`) and open `http://localhost:8000`
(fetch requires HTTP; `index.html` directly won't load traffic JSON).

### 3.1 File map

| File | Role |
|---|---|
| `index.html` | Canvases (`carCanvas`, `networkCanvas`), buttons, script load order |
| `config/config.js` | `CONFIG` — single source of truth (see §4) |
| `src/main.js` | Game loop `animate()`, generation/benchmark orchestration, scoreboard, resume dialog |
| `src/core/car.js` / `sensor.js` / `road.js` / `controls.js` / `utils.js` | Car, rays, road geometry + lane centers, keyboard/AI/dummy input, `lerp`/`getIntersection`/`polysIntersect` |
| `src/ai/network.js` / `evolution.js` / `fitness.js` | Network, GA, scoring |
| `src/ai/modelManager.js` + `src/ui/modelManagerUI.js` | Named models in `localStorage` (`savedModels`): save/load/export/import/delete |
| `src/ai/benchmarkStore.js` | Benchmark history in `localStorage` + CSV download (`benchmark_scores.csv`) |
| `src/ai/experimentStore.js` | Experiment checkpoints: IndexedDB (`self-driving-car` DB, `experiments` store, `latest` record), `localStorage` fallback |
| `src/traffic/trafficLoader.js` | `loadTraffic()` (random generator vs fixed JSON + cache), control panel UI |
| `src/ui/trainingControls.js` | 🏁 panel: Start/Pause/Stop, generation target, population, mutation rate |
| `src/ui/settings.js` | ⚙ car-physics settings panel |
| `src/ui/visualizer.js` | Network graph drawn on `networkCanvas` |
| `style.css` | Overlays (panel, scoreboard, dialogs) |
| `test/` | Standalone single-car harness (`test/main.js` + `test/index.html`) |
| `assets/` | Car sprites (visual only) |
| `data/models/` | Example exported model JSON |

### 3.2 Runtime flow (`src/main.js`)

1. `init()`: load experiment checkpoint → offer **Resume** vs **Start new**.
2. `animate()` per frame: update traffic → update AI cars → update fitness +
   `checkNoPass` → pick best car (max distance) → `generator.update(bestcar.y)` →
   draw road/traffic/cars/network → update scoreboard → `endGeneration()` when done.
3. `endGeneration()`: assign fitness → `nextGeneration()` → autosave → every
   `benchmarkEvery` gens test the NEW population on fixed `traffic_1` for
   `benchmarkSeconds` (wall-clock), log `{generation, averageScore, bestScore,
   bestDistance, bestCarsPassed, bestTimeAlive}` → resume training. Benchmark uses
   real time (`Date.now()`), so it is wall-clock, not frame-exact.
4. Checkpoints (seed, config, full population, log, bestSoFar): autosave every
   `autosaveEvery` (5) gens + 📌 manual button + final save on completion.

## 4. Config reference (`config/config.js`, mirrored in `simulation/config.py`)

`car`: width 30, height 50, acceleration 0.2, maxSpeed 7, friction 0.05,
canRotate false, turnAngle 0.02, lateralSpeed 2, startLane 1, startY 100.
`road`: laneCount 3, widthFactor 0.9, infinity 1000000.
`sensor`: rayCount 7, rayLength 150, raySpread π/2.
`network`: hiddenSize 10, outputSize 4, mutationAmount 0.1.
`evolution`: elitismCount 2, mutationRate 0.1, seed 12345, maxDistance 8000,
autosaveEvery 5, stallSeconds 5, noPassSeconds 10, benchmarkEvery 5,
benchmarkSeconds 30.
`sim`: defaultCarCount 100, carCanvasWidth 200, networkCanvasWidth 300.
`fitness`: passedBonus 200, timeAliveMultiplier 10.
`traffic`: rowSpacing 300, maxCarsPerRow 3, initialRows 10, generateAheadRows 5,
removeBehindOffset 500, viewDistance 500, nearbyDistance 300, default size
30×50, defaultSpeed 2.

## 5. Headless Python trainer (`simulation/`)

Exact port of the JS (same numbers/units/RNG); ~40x optimized (tuple geometry,
AABB rejects, cached rays, dead-car skipping) with verified identical scores.

| Module | Role |
|---|---|
| `train.py` | CLI training loop (progress bar, checkpoints, CSVs, model export, resume) |
| `simulate.py` | `run_episode()` (mirrors `animate()` without rendering) + `run_fixed_parallel()` (multiprocess fixed-traffic eval) |
| `car.py` / `network.py` / `evolution.py` / `fitness.py` / `traffic.py` / `rng.py` / `utils.py` | Ports of the JS counterparts |
| `config.py` | Mirror of `config/config.js` (Python side source of truth) |
| `load_model.js` | Snippet showing how the browser imports a Python-exported model |
| `requirements.txt` | `numpy>=1.24`, `tqdm>=4.60` |
| `models/` | Default export dir (`best_model_genN.json` + `.brain.json` bare variant) |

### 5.1 CLI (`python -m simulation.train`)

Key flags: `--generations` (default 30), `--population` (default 100),
`--mutation-rate`, `--elitism`, `--seed`, `--benchmark-every` (5),
`--benchmark-seconds` (30), `--max-distance`, `--lane-count`, `--max-speed`,
`--train-traffic` (must be `random`), `--test-traffic` (fixed id, default `1`),
`--run-dir` (self-contained run folder), `--out-csv`, `--models-dir`,
`--max-steps` (10000), `--checkpoint-every` (5, 0 disables),
`--jobs N` (parallel workers for the TEST benchmark only), `--resume <ckpt>`,
`--no-progress`, `--quiet`.

Examples:

```bash
python -m simulation.train --generations 30 --population 100
python -m simulation.train --generations 100 --population 100 --run-dir simulation/run1 --jobs 8
python -m simulation.train --resume simulation/run1/checkpoints/checkpoint_gen20.json --generations 100
```

### 5.2 Run outputs (`--run-dir <dir>`)

- `config.json` — run configuration snapshot.
- `test_results.csv` — `generation,averageScore,bestScore,bestDistance,bestCarsPassed,bestTimeAlive`
  (same format as the browser CSV; flushed incrementally every benchmark).
- `train_log.csv` — `generation,train_best,train_avg,train_worst` (flushed every gen).
- `weights/best_model_gen<N>_max<M>_<L>lane.json` (+ `.brain.json` bare) — final best-so-far;
  `weights/best_so_far.json` (+`.brain.json`) — updated on every improvement.
- `checkpoints/checkpoint_gen<N>.json` — every N gens: train/test scores, best
  brain + architecture, RNG state, full evolution state (resume needs this), config.
- Model JSON shapes: wrapper `{name, architecture, brain:{...}, fitness, generation}`
  and bare `{architecture, levels}`; both load via
  `NeuralNetwork.fromJSON(brainJson.brain || brainJson)`.

### 5.3 Parallelism / determinism notes

- Training episodes are single-process (shared random-traffic generator + global
  RNG order must be preserved).
- Fixed-traffic benchmark is embarrassingly parallel (`--jobs N`); parent RNG is
  advanced past the same throwaway draws so results and RNG state are identical
  for any job count (fork-based; falls back to default context elsewhere).

## 6. Data files

- `benchmark_scores_sp5/6/7.csv` (repo root): browser benchmark histories at
  different max speeds. `simulation/benchmark_scores_py.csv`: default Python CSV.
- `simulation/run_100gen_max7_3lane/`: example completed run
  (`config.json`, `console.log`, `test_results.csv`, `train_log.csv`, `weights/`).

## 7. Typical workflows

1. **Train headless, visualize in browser:** run `train.py` with `--run-dir` →
   copy `weights/best_*.brain.json` where the served page can fetch it (or import
   via 🧠 panel) → `NeuralNetwork.fromJSON(...)` → drive or `seedPopulation()`.
2. **Resume training:** browser offers it automatically from IndexedDB; Python
   uses `--resume <checkpoint> --generations <total>`.
3. **Evaluate fairly:** compare TEST rows (`test_results.csv`, fixed traffic);
   TRAIN rows reflect the random traffic that drove selection — never select on test.
4. **Tune:** population size, mutation rate/amount, `maxSpeed`, lane count,
   `maxDistance`, stall/no-pass timeouts (all in `config/config.js` ↔
   `simulation/config.py` — keep the two in sync when changing physics).

## 8. Invariants an AI editor must preserve

1. **Train/test separation** — fixed traffic is test-only; random traffic is
   train-only. Never let benchmark scores influence selection/mutation.
2. **Seeded RNG order** — all stochastic choices (population init, traffic rows,
   tournament picks, crossover coin flips, mutation noise) must consume
   `seeded_random()` in the same order, or reproducibility breaks. New RNG draws
   inside hot loops change every downstream generation.
3. **Physics parity JS↔Python** — same constants, same formulas/edge cases
   (`>` not `>=` in step activation, tie-breaking first-wins for best car,
   `dt=1` per frame). Verify with same-seed score comparisons after touching
   `car.py`/`sensor`/`network.py`/`fitness.py`/`traffic.py`/`utils.py`.
4. **`canRotate: false`** — angle stays 0; several Python fast paths rely on it.
5. **Brain JSON compatibility** — keep `{architecture, levels[]}` shapes stable;
   both the wrapper and bare files must load in `NeuralNetwork.fromJSON`.
6. **Config mirrors** — `config/config.js` and `simulation/config.py` must match;
   the trainer CLI overrides both consistently at startup.
