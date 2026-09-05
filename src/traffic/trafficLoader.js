const TRAFFIC_DIR = CONFIG.traffic.dataDir;

async function fetchTrafficPattern(patternId) {
    const res = await fetch(`${TRAFFIC_DIR}/traffic_${patternId}.json`);
    if (!res.ok) throw new Error(`Traffic pattern ${patternId} not found`);
    return res.json();
}

function randomCars(laneCount, count = CONFIG.traffic.randomDefaultCount) {
    const cars = [];
    let y = 100;

    for (let row = 0; row < count; row++) {
        y -= CONFIG.traffic.randomRowSpacing;

        const occupied = Math.random() < CONFIG.traffic.singleCarChance ? 1 : 2;

        const lanes = [];
        while (lanes.length < occupied) {
            const lane = Math.floor(Math.random() * laneCount);
            if (!lanes.includes(lane)) lanes.push(lane);
        }

        for (let k = 0; k < lanes.length; k++) {
            const speed = Math.random() < CONFIG.traffic.fasterCarChance ? CONFIG.traffic.fasterSpeed : CONFIG.traffic.defaultSpeed;
            cars.push({
                lane: lanes[k],
                y: y + Math.random() * 80,
                speed: speed
            });
        }
    }

    return cars;
}

const trafficCache = {};

class RandomTrafficCar extends Car {
    constructor(lane, y, width, height, speed, laneCount) {
        super(lane, y, width, height, "DUMMY", speed);
        this.laneCount = laneCount;
        this.polygon = this.#buildPolygon();
    }

    #buildPolygon() {
        const points = [];
        const rad = Math.hypot(this.width, this.height) / 2;
        const alpha = Math.atan2(this.width, this.height);
        points.push({
            x: this.x - Math.sin(this.angle - alpha) * rad,
            y: this.y - Math.cos(this.angle - alpha) * rad
        });
        points.push({
            x: this.x - Math.sin(this.angle + alpha) * rad,
            y: this.y - Math.cos(this.angle + alpha) * rad
        });
        points.push({
            x: this.x - Math.sin(Math.PI + this.angle - alpha) * rad,
            y: this.y - Math.cos(Math.PI + this.angle - alpha) * rad
        });
        points.push({
            x: this.x - Math.sin(Math.PI + this.angle + alpha) * rad,
            y: this.y - Math.cos(Math.PI + this.angle + alpha) * rad
        });
        return points;
    }

    inView() {
        const root = typeof bestcar !== "undefined" ? bestcar : null;
        return root && Math.abs(this.y - root.y) < CONFIG.traffic.viewDistance;
    }

    update(roadBorders, traffic) {
        const root = typeof bestcar !== "undefined" ? bestcar : null;
        if (!root) return;

        if (this.y > root.y + CONFIG.traffic.recycleBehindOffset) {
            this.y = root.y - CONFIG.traffic.recycleAheadMin - Math.random() * CONFIG.traffic.recycleAheadRandom;
            this.x = road.getLaneCenter(Math.floor(Math.random() * this.laneCount));
            this.speed = Math.random() < CONFIG.traffic.fasterCarChance ? CONFIG.traffic.fasterSpeed : CONFIG.traffic.defaultSpeed;
            this.angle = 0;
            this.damaged = false;
            this.polygon = this.#buildPolygon();
            return;
        }

        if (!this.inView()) return;

        const nearbyTraffic = traffic.filter(c => Math.abs(c.y - this.y) < CONFIG.traffic.nearbyDistance);
        super.update(roadBorders, nearbyTraffic);
    }

    draw(ctx, color, drawsensors = false) {
        if (!this.inView()) return;
        super.draw(ctx, color, drawsensors);
    }
}

function makeTrafficCars(data, cars, cull = false, laneCount = CONFIG.road.laneCount) {
    return cars.map(car => {
        if (cull) {
            return new RandomTrafficCar(
                road.getLaneCenter(car.lane),
                car.y,
                data.carWidth,
                data.carHeight,
                car.speed,
                laneCount
            );
        }
        return new Car(
            road.getLaneCenter(car.lane),
            car.y,
            data.carWidth,
            data.carHeight,
            "DUMMY",
            car.speed
        );
    });
}

async function loadTraffic(carLaneCount = CONFIG.road.laneCount, choice = "1") {
    const trimmed = String(choice || "").trim().toLowerCase();
    let data;
    let cars;

    if (trimmed === "random") {
        data = { laneCount: carLaneCount, carWidth: CONFIG.traffic.defaultCarWidth, carHeight: CONFIG.traffic.defaultCarHeight };
        cars = randomCars(carLaneCount);
        return makeTrafficCars(data, cars, true, carLaneCount);
    } else {
        const id = parseInt(trimmed, 10);
        if (isNaN(id) || id < 1 || id > 5) {
            console.error(`Invalid pattern '${choice}'`);
            return [];
        }
        if (!trafficCache[id]) {
            trafficCache[id] = await fetchTrafficPattern(id);
        }
        data = trafficCache[id];
        cars = data.cars;
    }

    return makeTrafficCars(data, cars);
}

function createControlPanel(onTraffic, onCar) {
    const panel = document.createElement("div");
    panel.id = "controlpanel";
    panel.style.cssText = [
        "position:fixed;top:10px;left:10px;z-index:100;font-family:Arial",
        "background:rgba(0,0,0,0.75);padding:10px 12px;border-radius:8px;color:white"
    ].join(";");

    const row = (labelText) => {
        const r = document.createElement("div");
        r.style.cssText = "display:flex;align-items:center;gap:8px;margin:4px 0;";
        const label = document.createElement("span");
        label.textContent = labelText;
        label.style.cssText = "white-space:nowrap;";
        r.appendChild(label);
        return { r, label };
    };

    const tr = row("Traffic:");
    const trafficSel = document.createElement("select");
    trafficSel.id = "patternSelect";
    const topts = [
        ["random", "Random (infinite)"],
        ["1", "Traffic 1 (easy)"],
        ["2", "Traffic 2 (easy-mid)"],
        ["3", "Traffic 3 (mid)"],
        ["4", "Traffic 4 (hard)"],
        ["5", "Traffic 5 (all 12 turns)"]
    ];
    for (const [v, t] of topts) {
        const o = document.createElement("option");
        o.value = v;
        o.textContent = t;
        trafficSel.appendChild(o);
    }
    trafficSel.value = "random";
    trafficSel.onchange = () => onTraffic(trafficSel.value);
    tr.r.appendChild(trafficSel);

    const cr = row("Cars:");
    const modeSel = document.createElement("select");
    modeSel.id = "carMode";
    modeSel.appendChild(new Option("AI", "AI"));
    modeSel.appendChild(new Option("User (keyboard)", "KEYS"));
    modeSel.value = "AI";

    const countInput = document.createElement("input");
    countInput.id = "aiCount";
    countInput.type = "number";
    countInput.min = "1";
    countInput.max = "500";
    countInput.value = String(CONFIG.sim.defaultCarCount);
    countInput.style.width = "60px";
    countInput.style.display = "inline-block";

    cr.r.appendChild(modeSel);
    cr.r.appendChild(countInput);

    const fireCar = () => onCar({
        mode: modeSel.value,
        count: modeSel.value === "AI" ? Math.max(1, parseInt(countInput.value, 10) || CONFIG.sim.defaultCarCount) : 1
    });

    modeSel.onchange = () => {
        countInput.style.display = modeSel.value === "AI" ? "inline-block" : "none";
        fireCar();
    };
    countInput.onchange = fireCar;

    panel.appendChild(tr.r);
    panel.appendChild(cr.r);
    document.body.appendChild(panel);

    return {
        trafficSelect: trafficSel,
        modeSelect: modeSel,
        countInput: countInput,
        hasRoot: true
    };
}
