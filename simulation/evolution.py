"""Exact port of src/ai/evolution.js (Genome + Evolution).

- mulberry32 seed drives ALL randomness via simulation.rng.
- elitism: copy top-N unchanged (deep clone via toJSON).
- tournament k=3 over full ranked list, uniform picks.
- crossover: per-LEVEL whole-level copy from parentA or parentB (p=0.5).
- mutate: lerp(old, rand*2-1, mutationRate) for every non-elite child.
- log: {generation, best, avg, worst} per finished generation.
"""
import math

from . import config as C
from . import rng as rng_mod
from .network import NeuralNetwork


class Genome:
    def __init__(self, brain):
        self.brain = brain
        self.fitness = 0.0


class Evolution:
    def __init__(self, architecture):
        self.architecture = list(architecture)
        self.generation = 0
        self.population = []
        self.log = []
        self.best_genome = None
        self.best_so_far = None

    def create_population(self, size):
        self.population = [Genome(NeuralNetwork(self.architecture)) for _ in range(size)]
        self.generation = 1
        return self.population

    def seed_population(self, size, source_brain):
        self.population = []
        for i in range(size):
            brain = NeuralNetwork.from_json(source_brain.to_json())
            if i > 0:
                NeuralNetwork.mutate(brain, C.EVOLUTION["mutation_rate"])
            self.population.append(Genome(brain))
        self.generation = 1
        return self.population

    def set_fitness(self, genome, fitness):
        genome.fitness = fitness

    def get_ranked(self):
        return sorted(self.population, key=lambda g: g.fitness, reverse=True)

    def get_best_genome(self):
        r = self.get_ranked()
        return r[0] if r else None

    def next_generation(self):
        ranked = self.get_ranked()
        self.best_genome = ranked[0] if ranked else None
        if ranked and (self.best_so_far is None or ranked[0].fitness > self.best_so_far.fitness):
            g = Genome(NeuralNetwork.from_json(ranked[0].brain.to_json()))
            g.fitness = ranked[0].fitness
            self.best_so_far = g

        best = ranked[0].fitness if ranked else 0
        worst = ranked[-1].fitness if ranked else 0
        total = sum(g.fitness for g in ranked)
        avg = total / len(ranked) if ranked else 0
        self.log.append({"generation": self.generation, "best": best, "avg": avg, "worst": worst})

        elitism = min(C.EVOLUTION["elitism_count"], len(ranked))
        nxt = []
        for i in range(elitism):
            elite = Genome(NeuralNetwork.from_json(ranked[i].brain.to_json()))
            elite.fitness = ranked[i].fitness
            nxt.append(elite)
        while len(nxt) < len(self.population):
            parent_a = self.tournament_select(ranked)
            parent_b = self.tournament_select(ranked)
            child = self.crossover(parent_a, parent_b)
            child_brain = child["brain"] if isinstance(child, dict) else child.brain
            NeuralNetwork.mutate(child_brain, C.EVOLUTION["mutation_rate"])
            nxt.append(Genome(child_brain))
        self.population = nxt
        self.generation += 1
        return self.population

    def tournament_select(self, ranked, k=3):
        rnd = rng_mod.seeded_random
        n = min(k, len(ranked))
        best = ranked[math.floor(rnd() * len(ranked))]
        for _ in range(n - 1):
            cand = ranked[math.floor(rnd() * len(ranked))]
            if cand.fitness > best.fitness:
                best = cand
        return best

    def crossover(self, parent_a, parent_b):
        rnd = rng_mod.seeded_random
        schema = NeuralNetwork.from_json(parent_a.brain.to_json())
        for i in range(len(schema.levels)):
            source = parent_a.brain if rnd() < 0.5 else parent_b.brain
            schema.levels[i].biases = list(source.levels[i].biases)
            schema.levels[i].weights = [list(row) for row in source.levels[i].weights]
            schema.levels[i]._sync_from_numpy()
        return {"brain": schema}

    # JS-compatible aliases
    createPopulation = create_population
    seedPopulation = seed_population
    setFitness = set_fitness
    getRanked = get_ranked
    getBestGenome = get_best_genome
    nextGeneration = next_generation
    tournamentSelect = tournament_select

    def get_log(self):
        return list(self.log)

    def get_best_so_far(self):
        if not self.best_so_far:
            return None
        return {"brain": self.best_so_far.brain, "fitness": self.best_so_far.fitness}

    def to_json(self):
        return {
            "architecture": list(self.architecture),
            "generation": self.generation,
            "population": [{"brain": g.brain.to_json(), "fitness": g.fitness} for g in self.population],
            "log": list(self.log),
            "bestSoFar": (
                {"brain": self.best_so_far.brain.to_json(), "fitness": self.best_so_far.fitness}
                if self.best_so_far
                else None
            ),
        }

    @staticmethod
    def from_json(data):
        evo = Evolution(data["architecture"])
        evo.generation = data.get("generation", 1)
        evo.population = []
        for p in data.get("population", []):
            g = Genome(NeuralNetwork.from_json(p["brain"]))
            g.fitness = p.get("fitness", 0)
            evo.population.append(g)
        evo.log = list(data.get("log", []))
        if data.get("bestSoFar"):
            g = Genome(NeuralNetwork.from_json(data["bestSoFar"]["brain"]))
            g.fitness = data["bestSoFar"].get("fitness", 0)
            evo.best_so_far = g
        return evo
