function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
        a |= 0;
        a = (a + 0x6D2B79F5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

const SeededRandom = (() => {
    let rand = Math.random;

    function setSeed(seed) {
        rand = mulberry32(seed);
        Math.random = rand;
    }

    function clear() {
        rand = Math.random;
        Math.random = rand;
    }

    return { setSeed, clear, next: () => rand() };
})();

class Genome {
    constructor(brain) {
        this.brain = brain;
        this.fitness = 0;
    }
}

class Evolution {
    constructor(architecture) {
        this.architecture = [...architecture];
        this.generation = 0;
        this.population = [];
        this.log = [];
        this.bestGenome = null;
        this.bestSoFar = null;
    }

    createPopulation(size) {
        this.population = [];
        for (let i = 0; i < size; i++) {
            this.population.push(new Genome(new NeuralNetwork(this.architecture)));
        }
        this.generation = 1;
        return this.population;
    }

    seedPopulation(size, sourceBrain) {
        this.population = [];
        for (let i = 0; i < size; i++) {
            const brain = NeuralNetwork.fromJSON(sourceBrain.toJSON());
            if (i > 0) {
                NeuralNetwork.mutate(brain, CONFIG.evolution.mutationRate);
            }
            this.population.push(new Genome(brain));
        }
        this.generation = 1;
        return this.population;
    }

    setFitness(genome, fitness) {
        genome.fitness = fitness;
    }

    getRanked() {
        return this.population.slice().sort((a, b) => b.fitness - a.fitness);
    }

    getBestGenome() {
        return this.getRanked()[0] || null;
    }

    nextGeneration() {
        const ranked = this.getRanked();
        this.bestGenome = ranked[0];

        if (ranked[0] && (!this.bestSoFar || ranked[0].fitness > this.bestSoFar.fitness)) {
            const g = new Genome(NeuralNetwork.fromJSON(ranked[0].brain.toJSON()));
            g.fitness = ranked[0].fitness;
            this.bestSoFar = g;
        }

        const best = ranked[0] ? ranked[0].fitness : 0;
        const worst = ranked.length ? ranked[ranked.length - 1].fitness : 0;
        const total = ranked.reduce((s, g) => s + g.fitness, 0);
        const avg = ranked.length ? total / ranked.length : 0;
        this.log.push({ generation: this.generation, best, avg, worst });

        const elitism = Math.min(CONFIG.evolution.elitismCount, ranked.length);
        const next = [];
        const parents = ranked;

        for (let i = 0; i < elitism; i++) {
            const elite = new Genome(NeuralNetwork.fromJSON(parents[i].brain.toJSON()));
            elite.fitness = parents[i].fitness;
            next.push(elite);
        }

        while (next.length < this.population.length) {
            const parentA = this.tournamentSelect(parents);
            const parentB = this.tournamentSelect(parents);
            const child = this.crossover(parentA, parentB);
            NeuralNetwork.mutate(child.brain, CONFIG.evolution.mutationRate);
            next.push(new Genome(child.brain));
        }

        this.population = next;
        this.generation++;
        return this.population;
    }

    tournamentSelect(ranked, k = 3) {
        const n = Math.min(k, ranked.length);
        let best = ranked[Math.floor(Math.random() * ranked.length)];
        for (let i = 0; i < n - 1; i++) {
            const candidate = ranked[Math.floor(Math.random() * ranked.length)];
            if (candidate.fitness > best.fitness) best = candidate;
        }
        return best;
    }

    crossover(parentA, parentB) {
        const schema = NeuralNetwork.fromJSON(parentA.brain.toJSON());
        for (let i = 0; i < schema.levels.length; i++) {
            const source = Math.random() < 0.5 ? parentA.brain : parentB.brain;
            schema.levels[i].biases = [...source.levels[i].biases];
            for (let j = 0; j < schema.levels[i].weights.length; j++) {
                schema.levels[i].weights[j] = [...source.levels[i].weights[j]];
            }
        }
        return { brain: schema };
    }

    getLog() {
        return this.log.slice();
    }

    getBestSoFar() {
        return this.bestSoFar ? { brain: this.bestSoFar.brain, fitness: this.bestSoFar.fitness } : null;
    }

    toJSON() {
        return {
            architecture: this.architecture,
            generation: this.generation,
            population: this.population.map(g => ({
                brain: g.brain.toJSON(),
                fitness: g.fitness
            })),
            log: this.log.slice(),
            bestSoFar: this.bestSoFar ? {
                brain: this.bestSoFar.brain.toJSON(),
                fitness: this.bestSoFar.fitness
            } : null
        };
    }

    static fromJSON(data) {
        const evo = new Evolution(data.architecture);
        evo.generation = data.generation || 1;
        evo.population = (data.population || []).map(p => {
            const g = new Genome(NeuralNetwork.fromJSON(p.brain));
            g.fitness = p.fitness || 0;
            return g;
        });
        evo.log = (data.log || []).slice();
        if (data.bestSoFar) {
            const g = new Genome(NeuralNetwork.fromJSON(data.bestSoFar.brain));
            g.fitness = data.bestSoFar.fitness || 0;
            evo.bestSoFar = g;
        }
        return evo;
    }
}
