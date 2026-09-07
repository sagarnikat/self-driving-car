"""Exact port of mulberry32 + SeededRandom from src/ai/evolution.js.

All randomness in training MUST go through `seeded_random()` so the
call order matches JS (population init -> traffic rows -> tournament ->
crossover -> mutate). Do NOT use numpy.random for genome/traffic decisions.
"""

MASK32 = 0xFFFFFFFF


def _to_int32(n):
    n &= MASK32
    return n - 0x100000000 if n & 0x80000000 else n


def _to_uint32(n):
    return n & MASK32


def _imul(a, b):
    # Math.imul: low 32 bits of signed multiplication
    return _to_int32(_to_uint32(a) * _to_uint32(b))


class Mulberry32:
    def __init__(self, seed):
        self.a = _to_uint32(seed)

    def __call__(self):
        # a |= 0; a = (a + 0x6D2B79F5) | 0
        self.a = _to_int32(self.a | 0)
        self.a = _to_int32(self.a + 0x6D2B79F5)
        # t = Math.imul(a ^ (a >>> 15), 1 | a)
        a_u = _to_uint32(self.a)
        t = _imul(a_u ^ (a_u >> 15), 1 | self.a)
        # t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
        t_u = _to_uint32(t)
        t = _to_int32(_to_uint32(t + _imul(t ^ (t_u >> 7), 61 | t)) ^ _to_uint32(t))
        t_u = _to_uint32(t)
        # return ((t ^ (t >>> 14)) >>> 0) / 4294967296
        return _to_uint32(t ^ (t_u >> 14)) / 4294967296.0


_rng = Mulberry32(12345)


def set_seed(seed):
    global _rng
    _rng = Mulberry32(seed)


def seeded_random():
    return _rng()
