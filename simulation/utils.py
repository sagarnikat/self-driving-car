"""Exact port of src/core/utils.js — same formulas, same edge cases."""
import math


def lerp(a, b, t):
    return a + (b - a) * t


def get_intersection(A, B, C, D):
    """Port of getIntersection. Points are dicts/tuples with x,y. Returns dict or None."""
    if isinstance(A, (list, tuple)):
        Ax, Ay = A[0], A[1]
    else:
        Ax, Ay = A["x"], A["y"]
    if isinstance(B, (list, tuple)):
        Bx, By = B[0], B[1]
    else:
        Bx, By = B["x"], B["y"]
    if isinstance(C, (list, tuple)):
        Cx, Cy = C[0], C[1]
    else:
        Cx, Cy = C["x"], C["y"]
    if isinstance(D, (list, tuple)):
        Dx, Dy = D[0], D[1]
    else:
        Dx, Dy = D["x"], D["y"]

    tTop = (Dx - Cx) * (Ay - Cy) - (Dy - Cy) * (Ax - Cx)
    uTop = (Cy - Ay) * (Ax - Bx) - (Cx - Ax) * (Ay - By)
    bottom = (Dy - Cy) * (Bx - Ax) - (Dx - Cx) * (By - Ay)

    if bottom != 0:
        t = tTop / bottom
        u = uTop / bottom
        if 0 <= t <= 1 and 0 <= u <= 1:
            return {
                "x": lerp(Ax, Bx, t),
                "y": lerp(Ay, By, t),
                "offset": t,
            }
    return None


def polys_intersect(poly1, poly2):
    for i in range(len(poly1)):
        for j in range(len(poly2)):
            touch = get_intersection(
                poly1[i],
                poly1[(i + 1) % len(poly1)],
                poly2[j],
                poly2[(j + 1) % len(poly2)],
            )
            if touch:
                return True
    return False


# ---------------------------------------------------------------------------
# Fast paths for the headless simulator.
#
# Same math as above, but operating on (x, y) tuples with no isinstance
# dispatch, no dicts and no point allocation on the boolean path.
# Used by Car/Sensor; results are bit-identical to the exact port.
# ---------------------------------------------------------------------------

def seg_intersects(ax, ay, bx, by, cx, cy, dx, dy):
    """Boolean-only segment test. Same formula/edge cases as get_intersection."""
    t_top = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx)
    u_top = (cy - ay) * (ax - bx) - (cx - ax) * (ay - by)
    bottom = (dy - cy) * (bx - ax) - (dx - cx) * (by - ay)
    if bottom != 0:
        t = t_top / bottom
        if 0 <= t <= 1:
            u = u_top / bottom
            if 0 <= u <= 1:
                return True
    return False


def seg_offset(ax, ay, bx, by, cx, cy, dx, dy):
    """Offset `t` of the intersection along A->B, or None. Same math as above."""
    t_top = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx)
    u_top = (cy - ay) * (ax - bx) - (cx - ax) * (ay - by)
    bottom = (dy - cy) * (bx - ax) - (dx - cx) * (by - ay)
    if bottom != 0:
        t = t_top / bottom
        if 0 <= t <= 1:
            u = u_top / bottom
            if 0 <= u <= 1:
                return t
    return None


def poly_bounds(poly):
    """(min_x, max_x, min_y, max_y) for a tuple polygon. Exact, cheap reject."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), max(xs), min(ys), max(ys)


def bounds_overlap(b1, b2):
    return not (b1[1] < b2[0] or b2[1] < b1[0] or b1[3] < b2[2] or b2[3] < b1[2])


def polys_intersect_fast(poly1, b1, poly2, b2=None):
    """Exact boolean test with AABB early-reject.

    poly*: lists of (x, y) tuples. b1/b2 are precomputed poly_bounds()
    (b2 computed on the fly if omitted). Returns exactly what
    polys_intersect() returns, but skips segment math when bounding
    boxes cannot overlap (the common case: cars far apart).
    """
    if b2 is None:
        b2 = poly_bounds(poly2)
    if not bounds_overlap(b1, b2):
        return False
    n1 = len(poly1)
    n2 = len(poly2)
    for i in range(n1):
        ax, ay = poly1[i]
        bx, by = poly1[(i + 1) % n1]
        for j in range(n2):
            cx, cy = poly2[j]
            dx, dy = poly2[(j + 1) % n2]
            if seg_intersects(ax, ay, bx, by, cx, cy, dx, dy):
                return True
    return False
