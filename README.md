# Self-Driving Car AI Trainer

A browser-based (vanilla JavaScript + HTML5 Canvas) evolutionary trainer that teaches
a small neural network to drive a car down a multi-lane road while avoiding traffic.
Each car has ray sensors that feed a neural network, and a simple genetic algorithm
evolves the network over generations.

## Features

- **Neural network driving** — each car has 5 ray sensors feeding a `5 → 6 → 4` network
  that outputs `forward / left / right / reverse`.
- **Evolution** — a population of cars evolves; the best brain is saved to
  `localStorage` and used to seed the next generation (with mutation).
- **Traffic modes** — choose between random (infinite) traffic or 5 fixed benchmark
  layouts.
- **Car modes** — run an AI population (configurable count) or a single keyboard-driven
  user car.
- **Live stats** — score, speed, distance, cars passed, and time alive for the best car.
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
| **Arrow keys** | Drive in User mode |

## Code layout

| File | Purpose |
|------|---------|
| `index.html` | Page structure, canvas elements, script loading |
| `main.js` | Main loop, car generation, best-car selection, drawing |
| `car.js` | `Car` class — movement, sensors, brain inference, collision |
| `sensor.js` | `Sensor` class — ray casting against road and traffic |
| `network.js` | `NeuralNetwork` class — feed-forward, mutate, serialize |
| `road.js` | `Road` class — lanes, borders, lane-center lookup |
| `controls.js` | `Controls` class — keyboard / AI / dummy input |
| `utils.js` | Helpers (`lerp`, `polysIntersect`, …) |
| `visualizer.js` | Draws the neural-network graph on the side canvas |
| `fitness.js` | `Fitness` — per-car distance, cars passed, time alive, score |
| `trafficLoader.js` | Loads traffic JSON patterns + builds the control-panel UI |
| `style.css` | Global styles and fixed overlays (panel, scoreboard) |
| `data/traffic/` | Fixed benchmark traffic layouts (`traffic_1.json` … `traffic_5.json`) |

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
- **Mostly 2 lanes** are occupied per row (2 free); ~30% of the time only **1 lane**
  is occupied (3 free) for overtaking.
- Cars move at **speed 2**, with a **10% chance of speed 3**.
- Cars recycle to ahead of the player once passed, so traffic is effectively endless
  without loading hundreds of objects (keeping FPS stable).

## Score / fitness

Each car's fitness is tracked by `fitness.js`:

- `distance` — forward progress from the start line.
- `carsPassed` — how many traffic cars it overtook (counted once per car).
- `timeAlive` — seconds alive (frozen once the car is damaged).
- `score` — `distance + carsPassed × 200 + timeAlive × 10`.

The **best car** (which the camera follows and whose brain is drawn/evolved) is the one
with the **highest distance**.
