const TRAFFIC_DIR = CONFIG.traffic.dataDir;

async function fetchTrafficPattern(patternId) {
    const res = await fetch(`${TRAFFIC_DIR}/traffic_${patternId}.json`);
    if (!res.ok) throw new Error(`Traffic pattern ${patternId} not found`);
    return res.json();
}

class RandomTrafficCar extends Car {
    constructor(x, y, width, height, speed, laneCount) {
        super(x, y, width, height, "DUMMY", speed);
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

    update(roadBorders, traffic, dt) {
        const nearbyTraffic = traffic.filter(c => Math.abs(c.y - this.y) < CONFIG.traffic.nearbyDistance);
        super.update(roadBorders, nearbyTraffic, dt);
    }

    draw(ctx, color, drawsensors = false) {
        if (!this.inView()) return;
        super.draw(ctx, color, drawsensors);
    }
}

class TrafficGenerator {
    constructor(laneCount) {
        this.laneCount = laneCount;
        this.cars = [];

        let rowY = CONFIG.car.startY;
        for (let i = 0; i < CONFIG.traffic.initialRows; i++) {
            rowY -= CONFIG.traffic.rowSpacing;
            this.generateRow(rowY);
        }
    }

    generateRow(rowY) {
        const maxCars = Math.min(CONFIG.traffic.maxCarsPerRow, this.laneCount - 1);
        const carCount = Math.floor(Math.random() * (maxCars + 1));

        const usedLanes = [];
        while (usedLanes.length < carCount) {
            const lane = Math.floor(Math.random() * this.laneCount);
            if (!usedLanes.includes(lane)) usedLanes.push(lane);
        }

        for (const lane of usedLanes) {
            this.cars.push(new RandomTrafficCar(
                road.getLaneCenter(lane),
                rowY,
                CONFIG.traffic.defaultCarWidth,
                CONFIG.traffic.defaultCarHeight,
                CONFIG.traffic.defaultSpeed,
                this.laneCount
            ));
        }
    }

    update(bestCarY) {
        for (let i = this.cars.length - 1; i >= 0; i--) {
            if (this.cars[i].y >= bestCarY + CONFIG.traffic.removeBehindOffset) {
                this.cars.splice(i, 1);
            }
        }

        let furthestY = bestCarY;
        if (this.cars.length > 0) {
            furthestY = this.cars[0].y;
            for (const c of this.cars) {
                if (c.y < furthestY) furthestY = c.y;
            }
        }

        while (bestCarY - furthestY < CONFIG.traffic.generateAheadRows * CONFIG.traffic.rowSpacing) {
            furthestY -= CONFIG.traffic.rowSpacing;
            this.generateRow(furthestY);
        }
    }

    reset() {
        this.cars = [];
        let rowY = CONFIG.car.startY;
        for (let i = 0; i < CONFIG.traffic.initialRows; i++) {
            rowY -= CONFIG.traffic.rowSpacing;
            this.generateRow(rowY);
        }
    }

    getCars() {
        return this.cars;
    }
}

const trafficCache = {};

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

    if (trimmed === "random") {
        return { generator: new TrafficGenerator(carLaneCount) };
    }

    const id = parseInt(trimmed, 10);
    if (isNaN(id) || id < 1 || id > 5) {
        console.error(`Invalid pattern '${choice}'`);
        return { cars: [] };
    }
    if (!trafficCache[id]) {
        trafficCache[id] = await fetchTrafficPattern(id);
    }
    const data = trafficCache[id];
    return { cars: makeTrafficCars(data, data.cars) };
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
