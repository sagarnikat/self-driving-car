# Self-Driving Car AI Trainer

A browser-based (vanilla JavaScript + HTML5 Canvas) evolutionary trainer that teaches
a small neural network to drive a car down a multi-lane road while avoiding traffic.
Each car has ray sensors that feed a neural network, and a simple genetic algorithm
evolves the network over generations.

## Features

- **Neural network driving** — each car has 7 ray sensors feeding a configurable
  `7 → 10 → 4` network that outputs `forward / left / right / reverse`.
- **Evolutionary loop** — a population of `NeuralNetwork`s is ranked by fitness each
  generation: the top genomes are kept unchanged (elitism), the rest are recombined
  (crossover) and mutated to form the next generation.
- **Reproducible training** — a fixed random seed drives the whole run, so the same
  seed reproduces the same traffic, population, and mutations.
- **Generation log** — each generation's best / average / worst score is recorded in
  memory and shown in the live stats.
- **Persistence & resume** — the full experiment state (config, seed, population, log,
  best model so far) is autosaved every N generations and can be saved manually with
  a checkpoint button. On page load you can **resume training from any saved checkpoint**
  or start fresh.
- **Traffic modes** — choose between random (infinite) traffic or 5 fixed benchmark
  layouts.
- **Car modes** — run an AI population (configurable count) or a single keyboard-driven
  user car.
- **Live stats** — generation, score, speed, distance, cars passed, and time alive for
  the best car.
- **Brain persistence** — save / discard / download the best brain.

## How to run

Because the traffic patterns are loaded from local JSON files via `fetch`, you should
serve the folder over HTTP rather than opening `index.html` directly.

Using Python:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

Using Node's built-in server (Node 18+):

```bash
npx serve .
```

## Controls

| Control | Effect |
|---------|--------|
| **Traffic** dropdown | Select random (infinite) or one of 5 fixed patterns (1–5) |
| **Cars / mode** dropdown | `AI` = train a population, `User (keyboard)` = drive with arrow keys |
| **AI count** input | Number of AI cars to evolve (AI mode only) |
| **📑** button | Save the best brain to `localStorage` |
| **🗑️** button | Discard the saved brain |
| **⬇️** button | Download the best brain as JSON |
| **📌** button | Save a training checkpoint (experiment state) |
| **Arrow keys** | Drive in User mode |

## Code layout

| File | Purpose |
|------|---------|
| `index.html` | Page structure, canvas elements, script loading |
| `main.js` | Main loop, car generation, best-car selection, generation loop, drawing, resume UI |
| `car.js` | `Car` class — movement, sensors, brain inference, collision |
| `sensor.js` | `Sensor` class — ray casting against road and traffic |
| `network.js` | `NeuralNetwork` class — configurable feed-forward, mutate, serialize |
| `evolution.js` | `Evolution` — population, selection, elitism, crossover, mutation, seed RNG |
| `experimentStore.js` | Checkpoint persistence (IndexedDB, with `localStorage` fallback) |
| `road.js` | `Road` class — lanes, borders, lane-center lookup |
| `controls.js` | `Controls` class — keyboard / AI / dummy input |
| `utils.js` | Helpers (`lerp`, `polysIntersect`, …) |
| `visualizer.js` | Draws the neural-network graph on the side canvas |
| `fitness.js` | `Fitness` — per-car distance, cars passed, time alive, score |
| `trafficLoader.js` | Loads traffic JSON patterns + builds the control-panel UI |
| `style.css` | Global styles and fixed overlays (panel, scoreboard) |
| `data/traffic/` | Fixed benchmark traffic layouts (`traffic_1.json` … `traffic_5.json`) |

## Training & checkpoints

Training runs in generations. Each generation starts a fresh run of the whole
population; when every car is damaged (or the best car passes
`CONFIG.evolution.maxDistance`), the generation ends and scores are recorded.

The next generation is built by `evolution.js`:

1. **Rank** the population by fitness (best → worst).
2. **Elitism** — copy the best `N` genomes into the next generation unchanged.
3. **Crossover** — pair up parents (tournament selection) and recombine their neural
   networks one level at a time.
4. **Mutation** — perturb every non-elite child's weights/biases.

The whole run is driven by a seeded PRNG (`CONFIG.evolution.seed`), so the same seed
reproduces the same traffic, initial population, and mutations.

Experiment state — seed, config, the full current population, the generation log, and
the best model so far — is persisted:

- **Autosave** every `CONFIG.evolution.autosaveEvery` generations (5 by default).
- **Manual checkpoint** via the **📌** button.
- On page load, if a checkpoint exists, a dialog offers **Resume from Gen X** (restores
  the population and continues evolving) or **Start new**.

Checkpoints live in IndexedDB (`self-driving-car` database, `experiments` store) and
fall back to `localStorage` in environments without IndexedDB.

### Data format

Traffic JSON files use a flat structure:

```json
{
  "laneCount": 4,
  "carWidth": 30,
  "carHeight": 50,
  "cars": [
    { "lane": 0, "y": -200, "speed": 2.0 },
    { "lane": 2, "y": -200, "speed": 2.0 }
  ]
}
```

- `laneCount` — number of lanes (road uses `road.getLaneCenter(lane)`).
- `cars[]` — each entry places a dummy (non-colliding AI) traffic car. `y` is negative
  (ahead of the spawn point at `y = 100`), `speed` sets its forward speed.

## Random traffic

The random (infinite) mode is generated procedurally rather than from files:

- Rows of traffic appear every **300px**, leaving gaps you can drive through.
- Each row places **0–2 cars** on random lanes (a third of the time a row is empty,
  giving a free lane to overtake).
- Cars move at **speed 2**.
- Rows are generated ahead of the player and removed once they fall behind, so traffic
  is effectively endless without loading hundreds of objects (keeping FPS stable).

## Score / fitness

Each car's fitness is tracked by `fitness.js`:

- `distance` — forward progress from the start line.
- `carsPassed` — how many traffic cars it overtook (counted once per car).
- `timeAlive` — seconds alive (frozen once the car is damaged).
- `score` — `distance + carsPassed × 200 + timeAlive × 10`.

The **best car** (which the camera follows and whose brain is drawn/evolved) is the one
with the **highest distance**.
