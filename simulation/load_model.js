// Example loader: import a Python-exported model into the existing JS classes.
// The Python exporter writes simulation/models/best_model_genN.json:
//   { name, architecture, brain: {architecture, levels:[...]}, fitness, generation }
// and a bare variant best_model_genN.brain.json:
//   { architecture, levels:[...] }
// Both work with NeuralNetwork.fromJSON (src/ai/network.js).
//
// Works with either the ModelManager wrapper or the bare brain file.

async function loadPythonModel(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch model: ${url}`);
  const data = await res.json();
  // Accept both {brain:{...}} wrapper and bare {architecture,levels} file.
  const brainJson = data.brain || data;
  const nn = NeuralNetwork.fromJSON(brainJson);
  return nn;
}

// Example: drive one car with the imported brain, or seed a whole population.
async function exampleUse() {
  const brain = await loadPythonModel("simulation/models/best_model_gen30.json");

  // Single-car inference (sensor readings -> [forward,left,right,reverse]):
  // const readings = car.sensor.readings.map(s => (s == null ? 0 : 1 - s.offset));
  // const outputs = NeuralNetwork.feedForward(readings, brain);

  // Seed evolution from the imported brain (keeps best intact, mutates rest):
  // evolution.seedPopulation(100, brain);

  return brain;
}

// Node / test usage:
// const fs = require("fs");
// const brainJson = JSON.parse(fs.readFileSync("simulation/models/best_model_gen30.brain.json", "utf8"));
// const nn = NeuralNetwork.fromJSON(brainJson);
