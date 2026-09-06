const carCanvas = document.getElementById("carCanvas");
carCanvas.width = CONFIG.sim.carCanvasWidth;

const networkCanvas = document.getElementById("networkCanvas");
networkCanvas.width = CONFIG.sim.networkCanvasWidth;

const carCtx = carCanvas.getContext("2d");
const networkCtx = networkCanvas.getContext("2d");

const road = new Road(carCanvas.width / 2, carCanvas.width * CONFIG.road.widthFactor);

let traffic = [];
let trafficGenerator = null;

let car = null;
let animStarted = false;

function resetToStart() {
    car.x = road.getLaneCenter(CONFIG.car.startLane);
    car.y = CONFIG.car.startY;
    car.speed = 0;
    car.angle = 0;
    car.damaged = false;
}

function setTrafficFromResult(result) {
    trafficGenerator = result.generator || null;
    traffic = result.generator ? result.generator.getCars() : (result.cars || []);
}

(async function init() {
    car = new Car(road.getLaneCenter(CONFIG.car.startLane), CONFIG.car.startY, CONFIG.car.width, CONFIG.car.height, "KEYS", CONFIG.car.maxSpeed);
    setTrafficFromResult(await loadTraffic(CONFIG.road.laneCount, "random"));
    resetToStart();
    animStarted = true;
    animate();
})();

function animate(time) {
    car.update(road.borders, traffic);

    if (trafficGenerator) {
        trafficGenerator.update(car.y);
        traffic = trafficGenerator.getCars();
    }

    carCanvas.height = window.innerHeight;
    networkCanvas.height = window.innerHeight;

    carCtx.save();
    carCtx.translate(0, -car.y + carCanvas.height * 0.7);

    road.draw(carCtx);

    for (let i = 0; i < traffic.length; i++) {
        traffic[i].draw(carCtx, "red");
    }

    car.draw(carCtx, "blue", true);

    carCtx.restore();

    document.getElementById("scoreboard").innerHTML =
        `Speed: ${Math.abs(car.speed).toFixed(1)}`;

    requestAnimationFrame(animate);
}