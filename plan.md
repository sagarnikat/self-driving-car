# Car AI Trainer — Build Plan

Goal (from the spec): train a network for N generations, save it, come back later,
load it with exact architecture/weights/biases, run it with no retraining, or
continue training from that point.

**Rule for every phase below: implement it yourself (or one small AI prompt per
phase), get it running, commit, THEN move to the next phase.** Never hand the
whole spec to a coding tool in one prompt — that's what broke things last time.

---

## Phase 0 — Stabilize (do this first)
- [ ] Confirm the reset project builds and the car still drives with the current
      5→6→4 network.
- [ ] Commit this as `working-baseline`.
- [ ] Read through your own `NeuralNetwork` code once, end to end, so you know
      what forward-pass and weights currently look like. Don't move on until you
      can explain it out loud.

## Phase 1 — Scoring & fixed benchmarks (spec §1, §7, §8)
- [ ] Add a score/fitness number per car (distance, cars passed, time alive).
- [ ] Hard-code 5 fixed traffic layouts (not random) for benchmarking.
- [ ] Write one function `runBenchmark(model)` that runs a model on all 5 and
      returns scores + average.
- [ ] Keep "training traffic" (random) and "benchmark traffic" (fixed) as two
      clearly separate code paths.

## Phase 2 — Configurable network + save/load (spec §1, §2, §3, §18, §19)
- [ ] Refactor `NeuralNetwork` so layer sizes are a constructor argument, not
      hard-coded (e.g. `new NeuralNetwork([5, 8, 4])`).
- [ ] Write `toJSON()` / `fromJSON()` on the network: architecture + weights +
      biases + activation function name.
- [ ] Save one model to a JSON file, reload the page, load that JSON back in,
      confirm the car drives identically without retraining.
      **This is the single most important milestone in the whole spec — get
      this rock-solid before anything else.**

## Phase 3 — Real evolutionary loop (spec §4, §5, §6)
- [ ] Population of genomes, each wrapping a `NeuralNetwork`.
- [ ] Fitness → rank → elitism (keep best N unchanged) → mutate the rest →
      next generation.
- [ ] Add a random seed so a training run is reproducible.
- [ ] Store each generation's best/avg/worst score in a simple array/log.

## Phase 4 — Persistence & resume (spec §9, §10, §11, §31, §32)
- [ ] Pick storage: localStorage is fine to start; move to IndexedDB only once
      you're saving full populations, not just one model.
- [ ] Save "experiment state" after each generation: config, seed, current
      population, best model so far.
- [ ] On page load, detect a saved experiment and offer "Resume from Gen X".
- [ ] Manual "Save Checkpoint" button + autosave every N generations.

## Phase 5 — Minimal UI to drive it (spec §13, §16, §17, §40)
- [ ] A small model list: name, generation, score, "Load" button.
- [ ] Training controls: Start / Pause / Stop, generations input, population
      input, mutation rate input.
- [ ] Show current generation + best score live while training.
- [ ] Skip charts/visualization for now — text numbers are enough at this stage.

## Phase 6 — Nice-to-haves (only after 1–5 work end to end)
- [ ] Model comparison view (spec §14)
- [ ] Live neuron/sensor visualization (spec §23, §24)
- [ ] Genetic diversity tracking (spec §28)
- [ ] Charts for score-vs-generation (spec §15)
- [ ] Import/export polish + versioned migrations (spec §19, §34)
- [ ] Fast/headless training mode for 100+ cars (spec §37, §38)

---

## Not doing yet
- C++ / WebAssembly rewrite of any function — the network is too small (5→6→4)
  for this to matter; see earlier discussion. Revisit only if you have a real,
  measured performance problem after Phase 6.
- The full module folder structure in spec §35 — reorganize into
  `game/`, `neural/`, `evolution/`, `training/`, `storage/`, `ui/` gradually,
  as each phase actually needs its own folder. Don't restructure everything
  up front.

## How to use this with an AI coding tool
When you get to a phase, prompt for *that phase only*, and paste in the
relevant chunk of your current code so the tool edits what's there instead of
guessing. After it responds, read the diff before accepting it — if you can't
explain what changed, ask it to explain, don't just apply it.
