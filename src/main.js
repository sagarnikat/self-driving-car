const carCanvas = document.getElementById("carCanvas");
carCanvas.width= CONFIG.sim.carCanvasWidth;

const networkCanvas = document.getElementById("networkCanvas");
networkCanvas.width= CONFIG.sim.networkCanvasWidth;

const carCtx = carCanvas.getContext("2d");
const networkCtx = networkCanvas.getContext("2d");

const road = new Road(carCanvas.width/2,carCanvas.width*CONFIG.road.widthFactor);

let traffic = [];

const n = CONFIG.sim.defaultCarCount;
let cars = [];
let fitnesses = [];
let bestcar =null;

let currentCarConfig = { mode: "AI", count: n };
let animStarted = false;

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
    if(localStorage.getItem("bestBrain")){
        for(let i = 0; i < cars.length; i++){
            if(cars[i].useBrain){
                cars[i].brain = JSON.parse(localStorage.getItem("bestBrain"));
                if(i != 0){
                    NeuralNetwork.mutate(cars[i].brain, CONFIG.network.mutationAmount);
                }
            }
        }
    }
    if (!animStarted) {
        animStarted = true;
        animate();
    }
}

async function reloadTraffic(choice) {
    traffic = await loadTraffic(CONFIG.road.laneCount, choice);
    resetToStart();
}

function reloadCars() {
    startSimulation(generateCars(currentCarConfig));
}

const controlPanel = createControlPanel(async (choice) => {
    await reloadTraffic(choice);
}, (config) => {
    currentCarConfig = config;
    reloadCars();
});

(async function init() {
    traffic = await loadTraffic(CONFIG.road.laneCount, "random");
    startSimulation(generateCars(currentCarConfig));
})();

function save(){
    localStorage.setItem("bestBrain",
        JSON.stringify(bestcar.brain));
}

function discard(){
    localStorage.removeItem("bestBrain");
}

function generateCars(config) {
    const cars = [];
    if (config.mode === "KEYS") {
        cars.push(new Car(road.getLaneCenter(CONFIG.car.startLane), CONFIG.car.startY, CONFIG.car.width, CONFIG.car.height, "KEYS", CONFIG.car.maxSpeed));
        return cars;
    }
    const count = config.count > 0 ? config.count : n;
    for (let i = 0; i < count; i++) {
        cars.push(new Car(road.getLaneCenter(CONFIG.car.startLane), CONFIG.car.startY, CONFIG.car.width, CONFIG.car.height, "AI", CONFIG.car.maxSpeed));
    }
    return cars;
}

function animate(time){
    for(let i =0;i<traffic.length;i++){
        traffic[i].update(road.borders,[]);
    }
    for(let i =0;i<cars.length;i++){
        cars[i].update(road.borders,traffic);
        for (let j = 0; j < fitnesses.length; j++) {
            fitnesses[j].update();
        }
    }

    bestcar = fitnesses.reduce((best, f, i) => {
        return f.getDistance() > fitnesses[best].getDistance() ? i : best;
    }, 0);
    bestcar = cars[bestcar];

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
    document.getElementById("scoreboard").innerHTML =
        `Score: ${bestFitness.calculateScore().toFixed(0)}<br>` +
        `Speed: ${Math.abs(bestcar.speed).toFixed(1)}<br>` +
        `Dist: ${bestFitness.getDistance().toFixed(0)}<br>` +
        `Passed: ${bestFitness.carsPassed}<br>` +
        `Time: ${bestFitness.getTimeAlive().toFixed(1)}s`;

    networkCtx.lineDashOffset=-time/50;
    Visualizer.drawNetwork(networkCtx,bestcar.brain);
    requestAnimationFrame(animate);
}
