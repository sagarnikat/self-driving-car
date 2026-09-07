const carCanvas = document.getElementById("carCanvas");
carCanvas.width= CONFIG.sim.carCanvasWidth;

const networkCanvas = document.getElementById("networkCanvas");
networkCanvas.width= CONFIG.sim.networkCanvasWidth;

const carCtx = carCanvas.getContext("2d");
const networkCtx = networkCanvas.getContext("2d");

const road = new Road(carCanvas.width/2,carCanvas.width*CONFIG.road.widthFactor);

let traffic = [];
let trafficGenerator = null;

const n = CONFIG.sim.defaultCarCount;
let cars = [];
let fitnesses = [];
let bestcar =null;

let currentCarConfig = { mode: "AI", count: n };
let currentTrafficChoice = "random";
let last = 0;

let evolution = null;

let trainingState = "stopped"; // "running" | "paused" | "stopped" | "complete"
let targetGenerations = 0; // 0 = run forever
let animFrameId = null;
let restarting = false;

let benchmarking = false;
let benchmarkCars = [];
let benchmarkFitnesses = [];
let benchmarkTraffic = [];
let benchmarkStartTime = 0;
let benchmarkSecondsElapsed = 0;
let benchmarkGen = 0;
let benchmarkThenComplete = false;

function brainArchitecture() {
    return [CONFIG.sensor.rayCount, CONFIG.network.hiddenSize, CONFIG.network.outputSize];
}

function ensurePopulation(count) {
    if (!evolution || evolution.population.length !== count) {
        SeededRandom.setSeed(CONFIG.evolution.seed);
        evolution = new Evolution(brainArchitecture());
        const savedRaw = localStorage.getItem("bestBrain");
        if (savedRaw) {
            const saved = JSON.parse(savedRaw);
            evolution.seedPopulation(count, NeuralNetwork.fromJSON(saved));
        } else {
            evolution.createPopulation(count);
        }
    }
    return evolution.population;
}

function resetToStart() {
    for (let i = 0; i < cars.length; i++) {
        cars[i].x = road.getLaneCenter(CONFIG.car.startLane);
        cars[i].y = CONFIG.car.startY;
        cars[i].speed = 0;
        cars[i].angle = 0;
        cars[i].damaged = false;
    }
    for (let i = 0; i < fitnesses.length; i++) {
        fitnesses[i] = new Fitness(cars[i], traffic);
    }
    bestcar = cars[0];
}

function startSimulation(selectedCars) {
    cars = selectedCars;
    fitnesses = cars.map(car => new Fitness(car, traffic));
    bestcar = cars[0];
}

function startLoop() {
    if (trainingState === "running" && !animFrameId) {
        last = 0;
        animFrameId = requestAnimationFrame(animate);
    }
}

function pauseTraining() {
    if (trainingState === "paused") return;
    trainingState = "paused";
    if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
    }
    if (trainingControls) trainingControls.refresh();
}

function stopTraining() {
    trainingState = "stopped";
    if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
    }
    if (trainingControls) trainingControls.refresh();
}

function startTraining() {
    if (trainingState === "running") return;
    const wasStopped = trainingState === "stopped" || trainingState === "complete";
    trainingState = "running";
    if (wasStopped) {
        evolution = null;
        restarting = false;
        reloadCars();
    }
    startLoop();
    if (trainingControls) trainingControls.refresh();
}

function resumeRunning() {
    trainingState = "running";
    startLoop();
    if (trainingControls) trainingControls.refresh();
}

function resumeCompletedRun() {
    trainingState = "running";
    targetGenerations = 0;
    restarting = false;
    reloadCars();
    startLoop();
    if (trainingControls) trainingControls.refresh();
}

function setTrafficFromResult(result) {
    trafficGenerator = result.generator || null;
    traffic = result.generator ? result.generator.getCars() : (result.cars || []);
}

let activeModelName = null;

function loadBrain(network) {
    localStorage.setItem("bestBrain", JSON.stringify(network));
    evolution = null;
    restarting = false;
    startSimulation(generateCars(currentCarConfig));
    resumeRunning();
}

function save() {
    if(!bestcar) return;
    const fitness = fitnesses.find(f => f.car === bestcar) || null;
    const score = fitness ? fitness.calculateScore() : 0;
    const name = activeModelName || bestModelName();
    const generation = evolution ? evolution.generation : null;
    ModelManager.saveModel(name, bestcar.brain, score, generation);
    activeModelName = null;
    alert(`Model "${name}" saved (score ${score.toFixed(0)})${generation != null ? `, Gen ${generation}` : ""}!`);
}

function discard() {
    localStorage.removeItem("bestBrain");
}

function bestModelName() {
    return "model_" + new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
}

async function reloadTraffic(choice) {
    currentTrafficChoice = choice;
    setTrafficFromResult(await loadTraffic(CONFIG.road.laneCount, choice));
    resetToStart();
}

function reloadCars() {
    startSimulation(generateCars(currentCarConfig));
}

function generationFinished() {
    if (currentCarConfig.mode !== "AI") return false;
    if (cars.length === 0) return true;
    if (cars.every(c => c.damaged)) return true;

    const bestFitness = fitnesses.find(f => f.car === bestcar);
    if (bestFitness && bestFitness.getDistance() >= CONFIG.evolution.maxDistance) {
        return true;
    }
    return false;
}

function endGeneration() {
    const count = Math.min(evolution.population.length, cars.length);
    for (let i = 0; i < count; i++) {
        evolution.setFitness(evolution.population[i], fitnesses[i].calculateScore());
    }

    const finishedGen = evolution.generation;
    evolution.nextGeneration();
    autosave();

    if (CONFIG.evolution.benchmarkEvery > 0 &&
        finishedGen % CONFIG.evolution.benchmarkEvery === 0) {
        benchmarkThenComplete = targetGenerations > 0 && finishedGen >= targetGenerations;
        benchmarkGen = finishedGen;
        startBenchmark();
        return;
    }

    if (targetGenerations > 0 && finishedGen >= targetGenerations) {
        trainingState = "complete";
        saveExperiment().catch((e) => console.warn("Final save failed:", e));
        if (trainingControls) trainingControls.refresh();
        restarting = false;
        return;
    }

    restartGeneration();
}

function startBenchmark() {
    restarting = true;
    (async () => {
        const result = await loadTraffic(CONFIG.road.laneCount, "1");
        const benchmarkTrafficCars = result.generator ? result.generator.getCars() : (result.cars || []);
        const brains = evolution.population.map(g => g.brain);
        benchmarkCars = brains.map((brain) => {
            const car = new Car(
                road.getLaneCenter(CONFIG.car.startLane),
                CONFIG.car.startY,
                CONFIG.car.width,
                CONFIG.car.height,
                "AI",
                CONFIG.car.maxSpeed
            );
            car.brain = NeuralNetwork.fromJSON(brain.toJSON());
            return car;
        });
        benchmarkFitnesses = benchmarkCars.map(car => new Fitness(car, benchmarkTrafficCars));

        benchmarkTraffic = benchmarkTrafficCars;
        benchmarkStartTime = Date.now();
        benchmarkSecondsElapsed = 0;
        benchmarking = true;

        traffic = benchmarkTraffic;
        cars = benchmarkCars;
        fitnesses = benchmarkFitnesses;
        trafficGenerator = null;
        last = 0;
    })();
}

function finishBenchmark() {
    let total = 0;
    let bestFit = benchmarkFitnesses[0];
    for (const f of benchmarkFitnesses) {
        const s = f.calculateScore();
        total += s;
        if (s > bestFit.calculateScore()) bestFit = f;
    }

    const entry = {
        generation: benchmarkGen,
        averageScore: Math.round(total / benchmarkFitnesses.length),
        bestScore: Math.round(bestFit.calculateScore()),
        bestDistance: Math.round(bestFit.getDistance()),
        bestCarsPassed: bestFit.carsPassed,
        bestTimeAlive: parseFloat(bestFit.getTimeAlive().toFixed(1))
    };
    BenchmarkStore.addEntry(entry);
    console.log(`Benchmark Gen ${benchmarkGen}: average ${entry.averageScore} / best ${entry.bestScore}`);

    benchmarking = false;
    benchmarkCars = [];
    benchmarkFitnesses = [];
    benchmarkTraffic = [];

    if (benchmarkThenComplete) {
        benchmarkThenComplete = false;
        trainingState = "complete";
        saveExperiment().catch((e) => console.warn("Final save failed:", e));
        if (trainingControls) trainingControls.refresh();
        return;
    }
    restartGeneration();
}

function downloadBenchmarkCSV() {
    BenchmarkStore.downloadCSV();
}

function autosave() {
    if (CONFIG.evolution.autosaveEvery > 0 &&
        evolution.generation % CONFIG.evolution.autosaveEvery === 0) {
        saveExperiment().catch((e) => console.warn("Autosave failed:", e));
    }
}

function buildExperiment() {
    return {
        type: "experiment",
        savedAt: new Date().toISOString(),
        seed: CONFIG.evolution.seed,
        config: {
            mode: currentCarConfig.mode,
            count: currentCarConfig.count,
            trafficChoice: currentTrafficChoice,
            elitismCount: CONFIG.evolution.elitismCount,
            mutationRate: CONFIG.evolution.mutationRate,
            maxDistance: CONFIG.evolution.maxDistance,
            targetGenerations: targetGenerations
        },
        evolution: evolution ? evolution.toJSON() : null
    };
}

function saveExperiment() {
    if (!evolution) return Promise.reject(new Error("No experiment running"));
    return ExperimentStore.save(buildExperiment());
}

function saveCheckpoint() {
    saveExperiment().then(() => {
        const bestFitness = evolution.getBestSoFar();
        const perf = bestFitness ? bestFitness.fitness.toFixed(0) : "-";
        alert(`Checkpoint saved (Gen ${evolution.generation}, best so far ${perf}).`);
    }).catch((e) => {
        alert("Failed to save checkpoint: " + e.message);
    });
}

function resumeExperiment(exp) {
    if (!exp || !exp.evolution) return false;
    const seed = exp.seed != null ? exp.seed : CONFIG.evolution.seed;
    SeededRandom.setSeed(seed);
    CONFIG.evolution.seed = seed;
    evolution = Evolution.fromJSON(exp.evolution);
    if (exp.config) {
        currentCarConfig = {
            mode: exp.config.mode || "AI",
            count: exp.config.count || n
        };
        currentTrafficChoice = exp.config.trafficChoice || "random";
        CONFIG.evolution.elitismCount = exp.config.elitismCount != null ? exp.config.elitismCount : CONFIG.evolution.elitismCount;
        CONFIG.evolution.mutationRate = exp.config.mutationRate != null ? exp.config.mutationRate : CONFIG.evolution.mutationRate;
        CONFIG.evolution.maxDistance = exp.config.maxDistance != null ? exp.config.maxDistance : CONFIG.evolution.maxDistance;
        targetGenerations = exp.config.targetGenerations || 0;
    }
    syncControlPanel();
    refreshTrainingControls();
    return true;
}

function syncControlPanel() {
    if (!controlPanel) return;
    if (controlPanel.trafficSelect) controlPanel.trafficSelect.value = currentTrafficChoice;
    if (controlPanel.modeSelect) controlPanel.modeSelect.value = currentCarConfig.mode;
    if (controlPanel.countInput) controlPanel.countInput.value = String(currentCarConfig.count);
    refreshTrainingControls();
}

function promptResume(saved, onResume, onStartNew) {
    const overlay = document.createElement("div");
    overlay.id = "resumeOverlay";
    const panel = document.createElement("div");
    panel.id = "resumePanel";

    const title = document.createElement("h3");
    title.textContent = "Saved experiment found";

    const desc = document.createElement("p");
    const gen = saved.evolution ? saved.evolution.generation : 1;
    const lastLog = saved.evolution && saved.evolution.log.length
        ? saved.evolution.log[saved.evolution.log.length - 1]
        : null;
    const best = lastLog ? lastLog.best.toFixed(0) : "—";
    const savedTime = saved.savedAt ? `\nSaved: ${new Date(saved.savedAt).toLocaleString()}` : "";
    desc.textContent = `Resume training from Gen ${gen}${savedTime}\nLast best score: ${best}`;
    desc.style.whiteSpace = "pre-line";

    const btns = document.createElement("div");
    btns.className = "resumeBtns";

    const resumeBtn = document.createElement("button");
    resumeBtn.className = "resumeBtn";
    resumeBtn.textContent = "Resume";
    resumeBtn.addEventListener("click", () => { overlay.remove(); onResume(); });

    const newBtn = document.createElement("button");
    newBtn.className = "newBtn";
    newBtn.textContent = "Start new";
    newBtn.addEventListener("click", () => { overlay.remove(); onStartNew(); });

    btns.appendChild(resumeBtn);
    btns.appendChild(newBtn);
    panel.appendChild(title);
    panel.appendChild(desc);
    panel.appendChild(btns);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    return overlay;
}

async function restartGeneration() {
    try {
        setTrafficFromResult(await loadTraffic(CONFIG.road.laneCount, currentTrafficChoice));
    } finally {
        reloadCars();
        restarting = false;
    }
}

const controlPanel = createControlPanel(async (choice) => {
    await reloadTraffic(choice);
}, (config) => {
    currentCarConfig = config;
    reloadCars();
});

function applyTrainingConfig(change) {
    if (change.generations !== undefined) {
        targetGenerations = Math.max(0, change.generations | 0);
    }
    if (change.population !== undefined) {
        currentCarConfig.count = Math.max(1, Math.min(500, change.population | 0));
        syncControlPanel();
    }
    if (change.mutationRate !== undefined) {
        CONFIG.evolution.mutationRate = Math.max(0, Math.min(1, change.mutationRate));
    }
}

function getTrainingState() {
    return {
        state: trainingState,
        generations: targetGenerations,
        population: currentCarConfig.count,
        mutationRate: CONFIG.evolution.mutationRate
    };
}

let trainingControls = null;

function setupTrainingControls() {
    trainingControls = createTrainingControls(
        () => {
            if (trainingState === "complete") {
                resumeCompletedRun();
            } else {
                startTraining();
            }
        },
        () => pauseTraining(),
        () => stopTraining(),
        applyTrainingConfig,
        getTrainingState
    );
}

function refreshTrainingControls() {
    if (trainingControls) trainingControls.refresh();
}

const DEFAULT_CAR_CONFIG = { ...CONFIG.car };

createSettingsPanel(() => {
    reloadCars();
}, () => {
    CONFIG.car = { ...DEFAULT_CAR_CONFIG };
    reloadCars();
});

setupTrainingControls();

createModelManagerUI((brain, name) => {
    activeModelName = name;
    loadBrain(brain);
}, (name) => {
    const fitness = fitnesses.find(f => f.car === bestcar) || null;
    const score = fitness ? fitness.calculateScore() : 0;
    const generation = evolution ? evolution.generation : null;
    ModelManager.saveModel(name, bestcar.brain, score, generation);
});

(async function init() {
    const saved = await ExperimentStore.load();
    if (saved && saved.type === "experiment") {
        promptResume(saved, async () => {
            if (resumeExperiment(saved)) {
                setTrafficFromResult(await loadTraffic(CONFIG.road.laneCount, currentTrafficChoice));
                startSimulation(generateCars(currentCarConfig));
                resumeRunning();
            } else {
                startDefault();
            }
        }, () => {
            ExperimentStore.clear();
            startDefault();
        });
    } else {
        startDefault();
    }
})();

async function startDefault() {
    setTrafficFromResult(await loadTraffic(CONFIG.road.laneCount, currentTrafficChoice));
    startTraining();
}

function generateCars(config) {
    const cars = [];
    if (config.mode === "KEYS") {
        cars.push(new Car(road.getLaneCenter(CONFIG.car.startLane), CONFIG.car.startY, CONFIG.car.width, CONFIG.car.height, "KEYS", CONFIG.car.maxSpeed));
        return cars;
    }
    const count = config.count > 0 ? config.count : n;
    const pop = ensurePopulation(count);
    for (let i = 0; i < count; i++) {
        const car = new Car(road.getLaneCenter(CONFIG.car.startLane), CONFIG.car.startY, CONFIG.car.width, CONFIG.car.height, "AI", CONFIG.car.maxSpeed);
        car.brain = NeuralNetwork.fromJSON(pop[i % pop.length].brain.toJSON());
        cars.push(car);
    }
    return cars;
}

function benchmarkAverage() {
    if (benchmarkFitnesses.length === 0) return 0;
    let total = 0;
    for (const f of benchmarkFitnesses) total += f.calculateScore();
    return total / benchmarkFitnesses.length;
}

function animate(time){
    animFrameId = null;

    let dt = (time - last) / 16.67;
    if(last === 0 || dt <= 0 || dt > 3) dt = 1;
    last = time;

    for(let i =0;i<traffic.length;i++){
        traffic[i].update(road.borders,[],dt);
    }
    for(let i =0;i<cars.length;i++){
        cars[i].update(road.borders,traffic,dt);
        for (let j = 0; j < fitnesses.length; j++) {
            fitnesses[j].update();
        }
        const fit = fitnesses.find(f => f.car === cars[i]);
        if (fit) fit.checkNoPass(dt);
    }

    if (benchmarking) {
        benchmarkSecondsElapsed = (Date.now() - benchmarkStartTime) / 1000;
        if (benchmarkSecondsElapsed >= CONFIG.evolution.benchmarkSeconds ||
            cars.length === 0 || cars.every(c => c.damaged)) {
            finishBenchmark();
        }
    }

    bestcar = fitnesses.reduce((best, f, i) => {
        return f.getDistance() > fitnesses[best].getDistance() ? i : best;
    }, 0);
    bestcar = cars[bestcar];

    if (trafficGenerator) {
        trafficGenerator.update(bestcar.y);
        traffic = trafficGenerator.getCars();
    }

    carCanvas.height= window.innerHeight;
    networkCanvas.height= window.innerHeight;

    carCtx.save();
    carCtx.translate(0,-bestcar.y+carCanvas.height*0.7);

    road.draw(carCtx);

    for(let i =0;i<traffic.length;i++){
        traffic[i].draw(carCtx,"red");
    }

    carCtx.globalAlpha=0.2;
    for(let i =0;i<cars.length;i++){
        cars[i].draw(carCtx,"blue");
    }
    carCtx.globalAlpha=1;
    bestcar.draw(carCtx,"blue",true);

    carCtx.restore();

    const bestFitness = fitnesses.find(f => f.car === bestcar);
    const gen = evolution ? evolution.generation : "-";
    const genStats = evolution ? evolution.getLog()[evolution.getLog().length - 1] : null;
    const bestEver = evolution && evolution.getBestSoFar() ? evolution.getBestSoFar().fitness : null;
    document.getElementById("scoreboard").innerHTML = benchmarking
        ? `⏱ Benchmark (traffic_1) — Gen ${benchmarkGen}<br>` +
          `Timer: ${benchmarkSecondsElapsed.toFixed(1)} / ${CONFIG.evolution.benchmarkSeconds}s<br>` +
          `Best: ${bestFitness.calculateScore().toFixed(0)}<br>` +
          `Avg: ${benchmarkAverage().toFixed(0)}<br>` +
          `Speed: ${Math.abs(bestcar.speed).toFixed(1)}<br>` +
          `Dist: ${bestFitness.getDistance().toFixed(0)}<br>` +
          `Passed: ${bestFitness.carsPassed}`
        : `Gen: ${gen}${targetGenerations > 0 ? ` / ${targetGenerations}` : ""}<br>` +
          `${genStats ? `Prev best: ${genStats.best.toFixed(0)}<br>` : ""}` +
          `${bestEver != null ? `Best ever: ${bestEver.toFixed(0)}<br>` : ""}` +
          `Score: ${bestFitness.calculateScore().toFixed(0)}<br>` +
          `Speed: ${Math.abs(bestcar.speed).toFixed(1)}<br>` +
          `Dist: ${bestFitness.getDistance().toFixed(0)}<br>` +
          `Passed: ${bestFitness.carsPassed}<br>` +
          `Time: ${bestFitness.getTimeAlive().toFixed(1)}s`;

    networkCtx.lineDashOffset=-time/50;
    Visualizer.drawNetwork(networkCtx,bestcar.brain);

    if (!benchmarking && generationFinished() && !restarting) {
        restarting = true;
        endGeneration();
    }

    if (trainingState === "running") {
        animFrameId = requestAnimationFrame(animate);
    }
}
