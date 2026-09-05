const CONFIG = {
    car: {
        width: 30,
        height: 50,
        acceleration: 0.2,
        maxSpeed: 7,
        friction: 0.05,
        canRotate: false,
        turnAngle: 0.02,
        lateralSpeed: 2,
        startLane: 1,
        startY: 100
    },

    road: {
        laneCount: 4,
        widthFactor: 0.9,
        infinity: 1000000
    },

    sensor: {
        rayCount: 7,
        rayLength: 150,
        raySpread: Math.PI / 2
    },

    network: {
        hiddenSize: 10,
        outputSize: 4,
        mutationAmount: 0.1
    },

    sim: {
        defaultCarCount: 100,
        carCanvasWidth: 240,
        networkCanvasWidth: 300
    },

    fitness: {
        passedBonus: 200,
        timeAliveMultiplier: 10
    },

    traffic: {
        dataDir: "data/traffic",
        randomDefaultCount: 40,
        randomRowSpacing: 300,
        recycleBehindOffset: 300,
        recycleAheadMin: 1800,
        recycleAheadRandom: 400,
        viewDistance: 500,
        nearbyDistance: 300,
        fasterCarChance: 0.1,
        singleCarChance: 0.3,
        defaultCarWidth: 30,
        defaultCarHeight: 50,
        defaultSpeed: 2,
        fasterSpeed: 3
    }
};
