"""Exact port of src/ai/network.js using NumPy for the forward pass.

JS semantics preserved:
- weights[input][output] (rows=inputs, cols=outputs), same JSON order.
- binary step activation: sum > bias ? 1 : 0  (strictly greater).
- randomize order: weights row-major, then biases.
- mutate order: biases first, then weights row-major, lerp(old, rand*2-1, amount).
- toJSON/fromJSON byte-compatible with JS NeuralNetwork.
"""
import copy
import numpy as np

from . import rng as _rng_mod
from .utils import lerp


class Level:
    def __init__(self, input_count, output_count, randomize=True):
        self.inputs = [0.0] * input_count
        self.outputs = [0] * output_count
        self.biases = [0.0] * output_count
        self.weights = [[0.0] * output_count for _ in range(input_count)]
        # numpy views for fast forward (kept in sync)
        self._W = np.zeros((input_count, output_count), dtype=np.float64)
        self._b = np.zeros((output_count,), dtype=np.float64)
        if randomize:
            self._randomize()

    def _randomize(self):
        rnd = _rng_mod.seeded_random
        for i in range(len(self.inputs)):
            for j in range(len(self.outputs)):
                v = rnd() * 2 - 1
                self.weights[i][j] = v
        for i in range(len(self.biases)):
            self.biases[i] = rnd() * 2 - 1
        self._sync_to_numpy()

    def _sync_to_numpy(self):
        self._W = np.array(self.weights, dtype=np.float64)
        self._b = np.array(self.biases, dtype=np.float64)

    def _sync_from_numpy(self):
        # keep list form authoritative for JSON; refresh numpy after edits
        self._sync_to_numpy()

    @staticmethod
    def feed_forward(given_inputs, level):
        # mutate-safe: copy inputs in
        for i in range(len(level.inputs)):
            level.inputs[i] = given_inputs[i]
        # NumPy fast path, identical math: sum_j in[j]*W[j][i] > b[i]
        arr = np.asarray(given_inputs, dtype=np.float64)
        sums = arr @ level._W
        outs = (sums > level._b).astype(int).tolist()
        level.outputs = outs
        return outs


class NeuralNetwork:
    def __init__(self, neuron_counts):
        self.architecture = list(neuron_counts)
        self.levels = []
        for i in range(len(neuron_counts) - 1):
            self.levels.append(Level(neuron_counts[i], neuron_counts[i + 1]))

    def to_json(self):
        return {
            "architecture": list(self.architecture),
            "levels": [
                {
                    "inputCount": len(lv.inputs),
                    "outputCount": len(lv.outputs),
                    "biases": list(lv.biases),
                    "weights": [list(row) for row in lv.weights],
                }
                for lv in self.levels
            ],
        }

    # camelCase alias so JS readers feel at home
    toJSON = to_json

    @staticmethod
    def from_json(data):
        if "architecture" in data:
            arch = list(data["architecture"])
        else:
            # fallback mirrors JS fromJSON
            arch = [l.get("inputCount", len(l.get("inputs", []))) for l in data["levels"]]
            if data["levels"]:
                arch.append(data["levels"][-1].get("outputCount", len(data["levels"][-1].get("outputs", []))))
        nn = NeuralNetwork.__new__(NeuralNetwork)
        nn.architecture = list(arch)
        nn.levels = []
        for li, ldata in enumerate(data["levels"]):
            in_c = arch[li]
            out_c = arch[li + 1]
            lv = Level.__new__(Level)
            lv.inputs = [0.0] * in_c
            lv.outputs = [0] * out_c
            lv.biases = list(ldata["biases"])
            lv.weights = [list(row) for row in ldata["weights"]]
            lv._sync_to_numpy()
            nn.levels.append(lv)
        return nn

    fromJSON = from_json

    @staticmethod
    def feed_forward(given_inputs, network):
        outputs = Level.feed_forward(given_inputs, network.levels[0])
        for i in range(1, len(network.levels)):
            outputs = Level.feed_forward(outputs, network.levels[i])
        return outputs

    feedForward = feed_forward

    @staticmethod
    def mutate(network, amount):
        rnd = _rng_mod.seeded_random
        for lv in network.levels:
            for i in range(len(lv.biases)):
                lv.biases[i] = lerp(lv.biases[i], rnd() * 2 - 1, amount)
            for i in range(len(lv.weights)):
                for j in range(len(lv.weights[i])):
                    lv.weights[i][j] = lerp(lv.weights[i][j], rnd() * 2 - 1, amount)
            lv._sync_from_numpy()

    def clone(self):
        return NeuralNetwork.from_json(self.to_json())
