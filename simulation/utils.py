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
