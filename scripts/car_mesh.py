#!/usr/bin/env python3
"""A simple car for the lidar renders, built from code (no downloads).

Plain words: the body is a side profile (bumper, hood, windshield, roof, tail, with wheel arches
cut into the bottom) swept across the car's width. Above the belt line the body steps inward
(the cabin is narrower than the doors, as on a real car) so the roof reads as a roof from above.
Windows are the steep parts of the body above the belt line, drawn in tinted glass. Four wheels
are short cylinders. Shading: one key light plus ambient, with the surface normal smoothed across
the sweep so the panels do not show bands. Triangles are drawn far-to-near (painter's algorithm).
A tight soft ellipse under the car is the contact shadow; two faint warm dots are the headlights,
so the nose reads at any size.

Body options: "sedan", "suv" (the Boreas car is a mid-size SUV), "hatch". All 4.8 m long, 1.9 m
wide, sitting on the road, nose along the direction of travel. No brand, no logo.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# (x along the car from the centre, z above the road), clockwise from the rear bumper bottom.
# The bottom edge runs back from the nose with two wheel arches cut in.
BOTTOM = [(2.4, 0.50), (1.8, 0.40), (1.8, 0.55), (1.1, 0.55), (1.1, 0.40), (-1.1, 0.40), (-1.1, 0.55), (-1.8, 0.55),
          (-1.8, 0.40), (-2.4, 0.40)]
PROFILES = {
    "sedan": [(-2.4, 0.40), (-2.4, 0.95), (-2.1, 1.05), (-1.5, 1.08), (-0.9, 1.42), (0.5, 1.46), (1.3, 1.08),
              (2.2, 0.98), (2.3, 0.95), (2.4, 0.70)] + BOTTOM,
    "suv":   [(-2.4, 0.40), (-2.4, 1.05), (-2.25, 1.62), (-1.9, 1.68), (0.5, 1.68), (1.4, 1.18), (2.2, 1.05),
              (2.3, 0.95), (2.4, 0.70)] + BOTTOM,
    "hatch": [(-2.4, 0.40), (-2.4, 1.0), (-2.05, 1.52), (-1.3, 1.58), (0.4, 1.58), (1.3, 1.12), (2.2, 1.0),
              (2.3, 0.95), (2.4, 0.70)] + BOTTOM,
}
BELT = 1.12          # above this height the body is the cabin: narrower, and glass where it is steep
WIDTH = 1.9
WHEEL_R, WHEEL_W = 0.38, 0.24
WHEEL_X = (-1.45, 1.45)


def body_grid(kind):
    """Vertices of the body on a (station across the width) x (point along the profile) grid, car frame."""
    prof = np.array(PROFILES[kind])
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(prof, axis=0).T))]
    s = np.linspace(0, seg[-1], 90)
    px = np.interp(s, seg, prof[:, 0])
    pz = np.interp(s, seg, prof[:, 1])
    stations = np.linspace(-1, 1, 25)
    grid = np.zeros((len(stations), len(px), 3))
    for a, t in enumerate(stations):
        cabin = np.clip((pz - BELT - 0.05) / 0.15, 0, 1)          # 0 below the belt, 1 in the cabin
        width = (WIDTH / 2) * (1 - 0.12 * cabin)                  # the cabin steps in by 12 percent (tumblehome)
        zz = pz - 0.04 * t ** 6 * (pz > 0.5)                     # a small roundover at the edges
        grid[a, :, 0] = px
        grid[a, :, 1] = t * width
        grid[a, :, 2] = zz
    return grid


def grid_normals(grid):
    """Smooth surface normals at grid vertices, from the two tangent directions."""
    du = np.gradient(grid, axis=0)
    dv = np.gradient(grid, axis=1)
    n = np.cross(du, dv)
    return n / np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-9)


def body_triangles(kind):
    grid = body_grid(kind)
    nrm = grid_normals(grid)
    A, B = grid.shape[:2]
    tris, tnrm, mat = [], [], []
    for a in range(A - 1):
        for b in range(B - 1):
            for ids in (((a, b), (a + 1, b), (a + 1, b + 1)), ((a, b), (a + 1, b + 1), (a, b + 1))):
                tri = np.array([grid[i] for i in ids])
                n = np.mean([nrm[i] for i in ids], axis=0)
                c = tri.mean(axis=0)
                tris.append(tri)
                tnrm.append(n)
                roof = abs(n[2]) / max(np.linalg.norm(n), 1e-9) > 0.92
                in_cabin = bool(np.all(tri[:, 2] > BELT + 0.08))     # whole triangle above the step, so the belt line stays clean
                mat.append(1 if (in_cabin and -2.35 < c[0] < 1.45 and not roof) else 0)
    for a in (0, A - 1):   # the two flat sides: the lower body and the cabin are closed separately, each fanned from its own centre
        ring = grid[a]
        side_n = np.array([0, -1.0 if a == 0 else 1.0, 0])
        for part, glass in (((ring[:, 2] <= BELT + 0.05), False), ((ring[:, 2] > BELT + 0.15), True)):
            idx = np.flatnonzero(part)
            if len(idx) < 3:
                continue
            pts = np.r_[ring[idx], ring[idx[:1]]]                 # close the loop
            c = pts.mean(axis=0)
            for b in range(len(pts) - 1):
                tris.append(np.array([pts[b], pts[b + 1], c]))
                tnrm.append(side_n)
                mat.append(1 if (glass and -2.35 < pts[b][0] < 1.45) else 0)
    return tris, tnrm, mat


def wheel_triangles():
    tris, tnrm = [], []
    n = 18
    ang = np.linspace(0, 2 * np.pi, n + 1)
    for x in WHEEL_X:
        for side in (-1, 1):
            y0 = side * (WIDTH / 2 - WHEEL_W / 2 + 0.05)       # pushed 5 cm out so the tyre face shows
            for yy, sn in ((y0 - WHEEL_W / 2, -1), (y0 + WHEEL_W / 2, 1)):
                c = np.array([x, yy, WHEEL_R])
                for i in range(n):
                    p1 = c + WHEEL_R * np.array([np.cos(ang[i]), 0, np.sin(ang[i])])
                    p2 = c + WHEEL_R * np.array([np.cos(ang[i + 1]), 0, np.sin(ang[i + 1])])
                    tris.append(np.array([c, p1, p2]))
                    tnrm.append(np.array([0, sn, 0.0]))
            for i in range(n):                          # tread
                a1 = np.array([x + WHEEL_R * np.cos(ang[i]), y0 - WHEEL_W / 2, WHEEL_R + WHEEL_R * np.sin(ang[i])])
                a2 = np.array([x + WHEEL_R * np.cos(ang[i + 1]), y0 - WHEEL_W / 2, WHEEL_R + WHEEL_R * np.sin(ang[i + 1])])
                b1, b2 = a1 + [0, WHEEL_W, 0], a2 + [0, WHEEL_W, 0]
                tn = np.array([np.cos(ang[i]), 0, np.sin(ang[i])])
                tris += [np.array([a1, a2, b2]), np.array([a1, b2, b1])]
                tnrm += [tn, tn]
    return tris, tnrm


_CACHE = {}


def car_mesh(kind):
    if kind not in _CACHE:
        wt, wn = wheel_triangles()                      # wheels first, so the body is drawn over them where they meet
        bt, bn, bm = body_triangles(kind)
        tris = np.array(wt + bt)
        nrm = np.array(wn + bn)
        mat = np.r_[np.full(len(wt), 2), np.array(bm)]  # 0 paint, 1 glass, 2 rubber
        _CACHE[kind] = (tris, nrm, mat)
    return _CACHE[kind]


def draw_car(draw, img_size, car_pos, fw, lat, project, kind="suv", paint=(190, 196, 204),
             light=(0.45, -0.25, 0.85), shadow=True, headlights=True):
    """Draw the car at world position car_pos (on the road) heading along fw.
    `project(points) -> (x, y, depth)` is the renderer's camera. Draws on `draw` (RGBA ImageDraw).
    With shadow=True returns only a shadow layer (PIL "L") to multiply onto the frame before the car is drawn."""
    tris, nrm, mat = car_mesh(kind)
    up = np.array([0, 0, 1.0])
    Rw = np.vstack([fw, lat, up]).T                    # car frame -> world
    world = tris @ Rw.T + car_pos
    x, y, z = project(world.reshape(-1, 3))
    x, y, z = x.reshape(-1, 3), y.reshape(-1, 3), z.reshape(-1, 3)
    if shadow:
        ang = np.linspace(0, 2 * np.pi, 72)
        ell = car_pos + np.cos(ang)[:, None] * 3.3 * fw + np.sin(ang)[:, None] * 1.4 * lat + 0.02 * up
        sx, sy, sz = project(ell)
        layer = Image.new("L", img_size, 255)
        if np.all(sz > 0.5):
            ImageDraw.Draw(layer).polygon([(float(a), float(b)) for a, b in zip(sx, sy)], fill=60)
            car_px = max(8.0, float(np.ptp(x)))       # projected car size, so the blur stays a contact shadow at any distance
            layer = layer.filter(ImageFilter.GaussianBlur(radius=max(6.0, car_px / 18)))
        return layer
    # the key light is fixed to the car (from above and a little ahead), so the roof is always the brightest face
    L = np.array(light, float)
    L /= np.linalg.norm(L)
    lam = np.abs(nrm @ L)
    shade = 0.20 + 0.80 * lam
    shade = shade * np.where(nrm[:, 2] > 0.7, 1.12, 0.80)         # roof a little lighter, sides darker, so the roof reads as the top
    depth = z.mean(axis=1)
    order = np.argsort(-depth)
    colours = {0: np.array(paint, float), 1: np.array((40, 48, 60), float), 2: np.array((30, 30, 32), float)}
    for i in order:
        if np.any(z[i] < 0.5):
            continue
        c = tuple(int(v) for v in np.clip(colours[int(mat[i])] * shade[i], 0, 255))
        draw.polygon([(float(x[i, k]), float(y[i, k])) for k in range(3)], fill=c, outline=c)
    if headlights:   # two warm dots at the nose, two red dots at the tail: from behind, the tail lamps say "car"
        for s in (-1, 1):
            for p, col in ((car_pos + 2.42 * fw + s * 0.68 * lat + 0.78 * up, (255, 244, 214, 150)),
                           (car_pos - 2.42 * fw + s * 0.72 * lat + 0.88 * up, (235, 60, 50, 190))):
                hx, hy, hz = project(np.array([p]))
                if hz[0] > 0.5:
                    r = max(3.0, 80.0 / hz[0])
                    draw.ellipse([hx[0] - r, hy[0] - r * 0.6, hx[0] + r, hy[0] + r * 0.6], fill=col)
    return None
