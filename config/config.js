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
        laneCount: 3,
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

    evolution: {
        elitismCount: 2,
        mutationRate: 0.1,
        seed: 12345,
        maxDistance: 8000,
        autosaveEvery: 5,
        stallSeconds: 5,
        noPassSeconds: 10,
        benchmarkEvery: 5,
        benchmarkSeconds: 30
    },

    sim: {
        defaultCarCount: 100,
        carCanvasWidth: 200,
        networkCanvasWidth: 300
    },

    fitness: {
        passedBonus: 200,
        timeAliveMultiplier: 10
    },

    traffic: {
        dataDir: "data/traffic",
        rowSpacing: 300,
        maxCarsPerRow: 3,
        initialRows: 10,
        generateAheadRows: 5,
        removeBehindOffset: 500,
        viewDistance: 500,
        nearbyDistance: 300,
        defaultCarWidth: 30,
        defaultCarHeight: 50,
        defaultSpeed: 2
    }
};
