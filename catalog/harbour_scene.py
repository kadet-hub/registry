#!/usr/bin/env python3
"""Draws the harbour scene of the start page as two inline SVG partials.

    python3 catalog/harbour_scene.py

writes layouts/_partials/harbour-wide.html and harbour-narrow.html and the
parcel keyframes between the harbour-keyframes markers of static/style.css.
The SVG carries geometry and classes only; style.css binds every class to a
scene token, so the drawing follows the theme and the CSP needs no exception.
Every class gets the prefix h- on the way out. The rules for them in style.css
have no ancestor, because the phone's crops show the vertical drawing through
<use>, and inside the tree of a <use> no selector matches that reaches outside it.

World axes: X runs to the lower right, Y to the upper right, Z up. A box shows
its top, its +X face (right) and its -Y face (left); the light makes the top
lightest, the right face mid and the left face darkest.
"""
import itertools
import math
import pathlib
import re

C, S, K = 0.8660254, 0.5, 0.57735
WZ = -26  # water level below the quay's top
SITE = pathlib.Path(__file__).parent / "site"


def n(v):
    """A number with one decimal, as short as SVG allows."""
    s = f"{v:.1f}"
    s = s.removesuffix(".0")
    return "0" if s == "-0" else s.replace("0.", ".", 1) if s.startswith(("0.", "-0.")) else s


class Iso:
    def __init__(self, ox, oy, out=None, k=1, bb=None):
        self.ox, self.oy, self.k = ox, oy, k
        self.out = [] if out is None else out
        self.bb = [1e9, 1e9, -1e9, -1e9] if bb is None else bb   # the box around everything projected so far

    def at(self, ox, oy, k=1):
        """The same output with another origin, and its geometry at the scale k; lines keep their weight."""
        return Iso(ox, oy, self.out, k, self.bb)

    def P(self, x, y, z=0):
        p = (self.ox + (x + y) * C * self.k, self.oy + ((x - y) * S - z) * self.k)
        b = self.bb
        b[0], b[1], b[2], b[3] = min(b[0], p[0]), min(b[1], p[1]), max(b[2], p[0]), max(b[3], p[1])
        return p

    def d(self, pts, close=True):
        """Path data: the first point absolute, the others relative to the rounded point before, so no error adds up."""
        q = [(round(a, 1), round(b, 1)) for a, b in (self.P(*p) for p in pts)]
        s = f"M{n(q[0][0])} {n(q[0][1])}"
        for (x0, y0), (x1, y1) in itertools.pairwise(q):
            dx, dy = round(x1 - x0, 1), round(y1 - y0, 1)
            s += f"h{n(dx)}" if dy == 0 else f"v{n(dy)}" if dx == 0 else f"l{n(dx)}{'' if dy < 0 else ' '}{n(dy)}"
        return s + ("z" if close else "")

    def path(self, cls, d):
        """Appends a path; one that follows a path of the same class joins it. Shadows stay apart, since two of them darken twice."""
        head = f'<path class="{cls}" d="'
        if cls != "shade" and self.out and self.out[-1].startswith(head) and self.out[-1].endswith('"/>'):
            self.out[-1] = self.out[-1][:-3] + d + '"/>'
        else:
            self.out.append(head + d + '"/>')

    def raw(self, s):
        self.out.append(s)

    def poly(self, cls, pts):
        self.path(cls, self.d(pts))

    def line(self, cls, pts):
        self.path(cls, self.d(pts, False))

    def top(self, cls, x0, x1, y0, y1, z=0):
        self.poly(cls, [(x0, y0, z), (x0, y1, z), (x1, y1, z), (x1, y0, z)])

    def right(self, cls, x, y0, y1, z0, z1):
        self.poly(cls, [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)])

    def left(self, cls, y, x0, x1, z0, z1):
        self.poly(cls, [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)])

    def box(self, fam, x0, x1, y0, y1, z0, z1):
        self.left(f"{fam}-l", y0, x0, x1, z0, z1)
        self.right(f"{fam}-r", x1, y0, y1, z0, z1)
        self.top(f"{fam}-t", x0, x1, y0, y1, z1)

    def shade(self, x0, x1, y0, h, z=0, k=.5, cls="shade"):
        """The shadow a box of height h throws from its left face. The class shade multiplies over what lies below;
        inside a group that moves or fades that no longer works, so such a group takes a solid shade for its ground."""
        self.top(cls, x0, x1, y0 - k * h, y0, z)

    def text_r(self, cls, s, x, y, z, anchor="middle"):
        px, py = self.P(x, y, z)
        self.raw(f'<text class="{cls}" text-anchor="{anchor}" transform="matrix(1 -{K} 0 1 {n(px)} {n(py)})">{s}</text>')

    def text_l(self, cls, s, x, y, z, anchor="middle"):
        px, py = self.P(x, y, z)
        self.raw(f'<text class="{cls}" text-anchor="{anchor}" transform="matrix(1 {K} 0 1 {n(px)} {n(py)})">{s}</text>')

    def plate_r(self, x, y0, y1, z0, z1, lines):
        """A white plate on a +X face with centred text lines: (class, text, font size)."""
        self.right("light", x, y0, y1, z0, z1)
        h = (z1 - z0) / len(lines)
        for i, (cls, s, fs) in enumerate(lines):
            self.text_r(cls, s, x, (y0 + y1) / 2, z1 - h * (i + 1) + (h - .72 * fs) / 2)

    def disc_r(self, cls, x, y, z, r):
        px, py = self.P(x, y, z)
        self.raw(f'<circle class="{cls}" r="{n(r)}" transform="matrix({C:.3f} -{S} 0 1 {n(px)} {n(py)})"/>')

    def disc_l(self, cls, x, y, z, r):
        px, py = self.P(x, y, z)
        self.raw(f'<circle class="{cls}" r="{n(r)}" transform="matrix({C:.3f} {S} 0 1 {n(px)} {n(py)})"/>')

    def frustum(self, fam, x, y, w0, w1, z0, z1):
        """A square tower that tapers from half-width w0 to w1."""
        self.poly(f"{fam}-l", [(x - w0, y - w0, z0), (x + w0, y - w0, z0), (x + w1, y - w1, z1), (x - w1, y - w1, z1)])
        self.poly(f"{fam}-r", [(x + w0, y - w0, z0), (x + w0, y + w0, z0), (x + w1, y + w1, z1), (x + w1, y - w1, z1)])
        self.top(f"{fam}-t", x - w1, x + w1, y - w1, y + w1, z1)

    def slab(self, fam, pts, z0, z1, foam=False):
        """A rectilinear footprint as a slab: every edge that faces +X or -Y gets its face, the farthest first."""
        ring = list(zip(pts, pts[1:] + pts[:1]))
        turn = 1 if sum(ax * by - bx * ay for (ax, ay), (bx, by) in ring) > 0 else -1
        faces = []
        for (ax, ay), (bx, by) in ring:
            if ay == by and (bx - ax) * turn > 0:
                faces.append((ax - ay + bx - by, "l", (ax, ay), (bx, by)))
            elif ax == bx and (by - ay) * turn > 0:
                faces.append((ax - ay + bx - by, "r", (ax, ay), (bx, by)))
        for _, side, a, b in sorted(faces):
            self.poly(f"{fam}-{side}", [(*a, z0), (*b, z0), (*b, z1), (*a, z1)])
            if foam:
                self.line("ln foam-s", [(*a, z0), (*b, z0)])
        self.poly(f"{fam}-t", [(x, y, z1) for x, y in pts])


# ---------------------------------------------------------------- parts

def tree(sc, x, y, s=1.0):
    sc.shade(x - 5 * s, x + 5 * s, y - 5 * s, 22 * s)
    sc.box("hull", x - 1.5, x + 1.5, y - 1.5, y + 1.5, 0, 7 * s)
    for z0, w, h in ((6 * s, 10 * s, 16 * s), (15 * s, 7.5 * s, 15 * s)):
        sc.poly("teal-l", [(x - w, y - w, z0), (x + w, y - w, z0), (x, y, z0 + h)])
        sc.poly("teal-r", [(x + w, y - w, z0), (x + w, y + w, z0), (x, y, z0 + h)])


def lamp(sc, x, y, h=44):
    sc.line("ln hull-s", [(x, y, 0), (x, y, h), (x + 9, y, h)])
    sc.box("wht", x + 6, x + 12, y - 2, y + 2, h - 4, h - 1)


def bollard(sc, x, y):
    sc.shade(x - 3, x + 3, y - 3, 8)
    sc.box("hull", x - 2.5, x + 2.5, y - 2.5, y + 2.5, 0, 6)
    sc.box("hull", x - 4.5, x + 4.5, y - 4.5, y + 4.5, 6, 9)


def cube(sc, fam, x, y, z, s):
    sc.box(fam, x, x + s, y, y + s, z, z + s)


def tick(sc, cls, x, y, z, side="l"):
    """A check mark on a face."""
    px, py = sc.P(x, y, z)
    sc.raw(f'<path class="ln {cls}" transform="matrix({C:.3f} {S if side == "l" else -S} 0 1 {n(px)} {n(py)})" d="M-4 0l3 3 5-6"/>')


def container(sc, fam, x0, y0, z0, label, L=132, W=50, H=46):
    x1, y1, z1 = x0 + W, y0 + L, z0 + H
    sc.box(fam, x0, x1, y0, y1, z0, z1)
    # bottom and top rails, and the corrugation at both ends of the side
    sc.right(f"{fam}-l", x1, y0, y1, z0, z0 + 4)
    sc.right(f"{fam}-l", x1, y0, y1, z1 - 4, z1)
    for y in (y0 + 4, y1 - 4):
        sc.line(f"ln {fam}-ls", [(x1, y, z0 + 7), (x1, y, z1 - 7)])
    if label:
        sc.plate_r(x1, y0 + 9, y1 - 9, z0 + 12, z1 - 12, [("tx-plate", label, 12.5)])
    else:
        for i in range(1, int(L // 12)):
            sc.line(f"ln {fam}-ls", [(x1, y0 + 4 + i * (L - 8) / (L // 12), z0 + 7), (x1, y0 + 4 + i * (L - 8) / (L // 12), z1 - 7)])
    # the door end: two leaves with their bars
    for x in (x0 + 9, (x0 + x1) / 2, x1 - 9):
        sc.line(f"ln {fam}-ts", [(x, y0, z0 + 5), (x, y0, z1 - 5)])
    # corner castings on the roof
    for cx, cy in ((x0, y0), (x1 - 5, y0), (x0, y1 - 5), (x1 - 5, y1 - 5)):
        sc.top(f"{fam}-r", cx, cx + 5, cy, cy + 5, z1)


SEAL = (50, 13, 37)   # where the seal sits on a container, from the container's corner


def seal(sc, x, y, z, cls=""):
    """The seal customs puts on a container: on its long side, over the corner of the plate."""
    sc.raw(f'<g class="seal{" " + cls if cls else ""}">')
    sc.disc_r("or-r", x, y, z, 7.5)
    tick(sc, "light-s", x, y, z, side="r")
    sc.raw("</g>")


def defs(sc, v):
    """The two containers of the story, drawn once; every place they pass shows them through <use>."""
    sc.raw("<defs>")
    for key, fam, label in (("k", CARGO_K, "kubernetes"), ("t", "teal", "terraform-aws")):
        sc.raw(f'<g id="h{v}-c{key}">')
        container(Iso(0, 0, sc.out), fam, 0, 0, 0, label)
        sc.raw("</g>")
    sc.raw("</defs>")


def put(sc, ref, x, y, z):
    px, py = sc.P(x, y, z)
    sc.raw(f'<use href="#{ref}" transform="translate({n(px)} {n(py)})"/>')


def quay(sc, y0, y1, x_back=-700):
    """The quay: wall with fenders, the water darker towards it in two steps, the coping's joint on top."""
    sc.top("shade", 0, 46, y0, y1 + 30, WZ)
    sc.top("shade", 0, 16, y0, y1 + 10, WZ)
    sc.right("land-r", 0, y0, y1, WZ, 0)
    sc.right("land-l", 0, y0, y1, WZ, WZ + 5)
    sc.line("ln foam-s", [(0, y0, WZ), (0, y1, WZ)])
    sc.top("land-t", x_back, 0, y0, y1, 0)
    sc.line("ln land-s", [(-7, y0, 0), (-7, y1 - 7, 0), (x_back, y1 - 7, 0)])
    for y in range(int(y0) + 40, int(y1), 70):
        px, py = sc.P(0, y, -10)
        sc.raw(f'<rect class="hull-l" x="-5" y="-8" width="10" height="16" rx="5" transform="matrix({C:.3f} -{S} 0 1 {n(px)} {n(py)})"/>')


def road(sc, x0, x1, y0, y1):
    sc.top("road", x0, x1, y0, y1)
    xm = (x0 + x1) / 2
    sc.line("ln foam-s dash", [(xm, y0, 0), (xm, y1, 0)])
    sc.line("ln foam-s", [(x0 + 4, y0, 0), (x0 + 4, y1, 0)])
    sc.line("ln foam-s", [(x1 - 4, y0, 0), (x1 - 4, y1, 0)])


def cargo_list(sc, x, ya, yb, top):
    """The target as a cargo list on the office wall: its name, then one line for each generator it pins, with a box
    in that generator's colour. The lines are drawn below the head, the lower one first: each slides out from under it."""
    rows = (("kubernetes", CARGO_K + "-r"), ("terraform-aws", "teal-r"))
    for k in (2, 1):
        name, tone = rows[k - 1]
        z1 = top - 13 - 14 * (k - 1)
        z0 = z1 - 14
        sc.raw(f'<g class="row row-{k}">')
        sc.right("light", x, ya, yb, z0, z1)
        sc.right(tone, x, ya + 6, ya + 17, z0 + 2.5, z0 + 11.5)
        sc.raw(f'<g class="tick tick-{k}">')
        tick(sc, "light-s", x, ya + 11.5, z0 + 7, side="r")
        sc.raw("</g>")
        sc.text_r("tx-list", name, x, ya + 24, z0 + 3.2, "start")
        sc.raw("</g>")
    sc.right("hull-r", x, ya, yb, top - 13, top)
    sc.text_r("tx-sign", "prod", x, ya + 8, top - 10.2, "start")


def office(sc, x0, y0, dx=96, dy=176, h=92):
    """The harbour office, two floors high: the door in its end wall, and on the upper floor of its long wall the sign
    and the cargo list, above what a truck in the lane hides."""
    x1, y1 = x0 + dx, y0 + dy
    assert x1 + 4 <= XL - 20, "the office stands clear of the truck's lane"
    assert dx > 50 and dy > 132 and h > 2 * 46 - 1, "the office is larger than a container"
    sc.shade(x0 - 4, x1 + 4, y0 - 4, h + 8)
    sc.left("ind-l", y0, x0, x1, 0, h)
    sc.right("ind-r", x1, y0, y1, 0, h)
    sc.left("hull-l", y0, x0, x1, 0, 5)       # plinth
    sc.right("hull-r", x1, y0, y1, 0, 5)
    # the end wall: door with a step and a canopy, a window beside it, three windows upstairs, each with its sill
    sc.box("land", x0 + 10, x0 + 42, y0 - 9, y0, 0, 4)
    sc.left("hull-l", y0, x0 + 14, x0 + 38, 5, 44)
    sc.left("ind-t", y0, x0 + 17, x0 + 35, 26, 40)
    sc.box("hull", x0 + 10, x0 + 42, y0 - 8, y0, 44, 47)
    for xa, xb, za, zb in ((x0 + 52, x0 + 84, 20, 40), (x0 + 12, x0 + 32, 58, 78), (x0 + 40, x0 + 60, 58, 78), (x0 + 68, x0 + 88, 58, 78)):
        sc.left("light", y0, xa, xb, za, zb)
        sc.left("hull-l", y0, xa - 2, xb + 2, za - 3, za)
    # the long wall: windows on the ground floor, upstairs the sign and below it the cargo list
    for ya in (y0 + 14, y0 + 54, y0 + 94, y0 + 134):
        sc.right("light", x1, ya, ya + 26, 12, 26)
    sc.plate_r(x1, y0 + 10, y0 + 104, 76, 89, [("tx-plate", "inventory/", 11.5)])
    cargo_list(sc, x1, y0 + 10, y0 + 152, 73)
    # flat roof with a dark fascia, the deck inside it and a vent
    sc.box("hull", x0 - 4, x1 + 4, y0 - 4, y1 + 4, h, h + 7)
    sc.top("ind-t", x0 + 2, x1 - 2, y0 + 2, y1 - 2, h + 7)
    sc.box("wht", x0 + 30, x0 + 54, y0 + 110, y0 + 138, h + 7, h + 18)


GATE = (80, 24)   # customs: the height under the beam, and the beam's own


def gate_back(sc, v, yg, x0=-168, x1=-44):
    """Customs, what a truck in the lane stands in front of: the stop line, the landward post, and the barrier on it.
    The barrier is drawn down across the lane; the stylesheet turns it up about its pivot."""
    h, hb = GATE
    assert x0 + 12 + 20 <= XL and x1 - 12 - 20 >= XL + 50 and h >= 58 + 20, "a loaded truck passes between the posts and under the beam with room to spare"
    sc.top("foam", XL + 2, XL + 48, yg - 34, yg - 29)
    sc.top("shade", x0, x1, yg - .5 * (h + hb) - 2, yg + 12 - .5 * h)      # the beam's shadow across the road
    sc.shade(x0, x0 + 12, yg, h)
    sc.box("hull", x0 - 2, x0 + 14, yg - 2, yg + 12, 0, 6)
    sc.box("or", x0, x0 + 12, yg, yg + 10, 6, h)
    yb, xp, xa = yg - 3, x0 + 12, XL + 55     # the barrier hinges on the post and stands against it when it is up
    sc.box("hull", xp - 4, xp + 2, yb - 3, yb, 17, 28)
    sc.raw(f'<g class="arm {v}-arm">')
    sc.left("light", yb, xp, xa, 20, 25)
    for x in range(int(xp) + 8, int(xa) - 8, 20):
        sc.left("or-l", yb, x, x + 10, 20, 25)
    sc.raw("</g>")
    return sc.P(xp, yb, 22.5)


def gate_front(sc, yg, x0=-168, x1=-44):
    """Customs, what stands in front of a truck in the lane: the waterside post with its signal, the beam with its
    plate, the shield."""
    h, hb = GATE
    px0 = x1 - 12
    sc.shade(px0, px0 + 12, yg, h)
    sc.box("hull", px0 - 2, px0 + 14, yg - 2, yg + 12, 0, 6)
    sc.box("or", px0, px0 + 12, yg, yg + 10, 6, h)
    # the signal: the lower lamp is lit; before the check the upper one is (the stylesheet shows the two covers)
    sx = px0 + 6
    sc.box("hull", sx - 5, sx + 5, yg - 5, yg, 30, 58)
    sc.disc_l("hull-r", sx, yg - 5, 50, 3.6)
    sc.disc_l("teal-t", sx, yg - 5, 39, 3.6)
    sc.raw('<g class="lamp">')
    sc.disc_l("or-r", sx, yg - 5, 50, 3.6)
    sc.disc_l("hull-r", sx, yg - 5, 39, 3.6)
    sc.raw("</g>")
    sc.box("or", x0, x1, yg - 2, yg + 12, h, h + hb)
    sc.left("light", yg - 2, x0 + 14, x1 - 14, h + 4, h + hb - 4)
    sc.text_l("tx-plate", "kadet-hub", (x0 + x1) / 2, yg - 2, h + 4 + (hb - 8 - .72 * 12.5) / 2)
    xm = (x0 + x1) / 2
    sc.line("ln ink-s", [(xm, yg + 5, h + hb), (xm, yg + 5, h + hb + 8)])
    px, py = sc.P(xm, yg + 5, h + hb + 24)
    sc.raw(f'<g transform="matrix({C:.3f} {S} 0 1 {n(px)} {n(py)})"><path class="light ink-o" d="M-13-17c8.7 3.3 17.3 3.3 26 0v15.2c0 8.7-13 15.2-13 15.2s-13-6.5-13-15.2z"/>'
           '<path class="ln or-ls" d="M-6-3l4.5 4.5 7.5-9"/></g>')


def turn(p, deg):
    """The CSS matrix that turns a shape drawn in an X-Z plane up about the screen point p, as the projection shows it:
    the screen images of the X axis, (C, S), and of the Z axis, (0, -1), turn into each other."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    m11, m12 = c - s * S, C * s
    m21, m22 = (S * (c - s * S) - (s + c * S)) / C, S * s + c
    e, f = p[0] - (m11 * p[0] + m12 * p[1]), p[1] - (m21 * p[0] + m22 * p[1])
    return f"matrix({m11:.4f}, {m21:.4f}, {m12:.4f}, {m22:.4f}, {e:.2f}, {f:.2f})"


TRUCK = 314   # the truck's length: a trailer for two containers and its tractor
XL, XS = -131, 32   # where a container stands across the truck's lane, and across the ship
ZH = 114      # the foot of a hoisted container: clear of the beams of the crane's portal


def truck(sc, v, key, tail, boxes):
    """The truck that brings both containers. boxes: (def, place from the tail, number in the order of unloading).
    What stands nearer the tractor lies farther back in the picture and is painted first."""
    x0, x1 = XL, XL + 50
    sc.raw(f'<g class="truck {v}-truck{key}">')
    sc.top("shade-road", x0 + 2, x1, tail - 12, tail + TRUCK - 6)
    sc.box("hull", x0 + 5, x1 - 5, tail, tail + 282, 5, 9)
    for y in (14, 32, 150, 168, 262):
        sc.disc_r("ink", x1 - 5, tail + y, 4.5, 4.5)
    # the tractor: as wide as its load and nearly as tall, with a deflector on its roof
    sc.box("wht", x0 + 2, x1 - 2, tail + 280, tail + TRUCK, 3, 54)
    sc.right("hull-r", x1 - 2, tail + 293, tail + 310, 30, 47)
    sc.line("ln ind-ls", [(x1 - 2, tail + 289, 8), (x1 - 2, tail + 289, 50)])
    sc.box("hull", x0 + 7, x1 - 7, tail + 282, tail + 294, 54, 58)
    sc.disc_r("ink", x1 - 2, tail + 300, 5.5, 5.5)
    for ref, off, i in sorted(boxes, key=lambda box: -box[1]):
        sc.raw(f'<g class="tc {v}-tc{key}-{i}">')
        put(sc, ref, x0, tail + off, 9)
        seal(sc, x0 + SEAL[0], tail + off + SEAL[1], 9 + SEAL[2], f"tseal {v}-tseal-{i}")
        sc.raw("</g>")
    sc.raw("</g>")


def scan(sc, v, i, y_front):
    """The scan: a band of light around a container on the truck, drawn at the container's front end."""
    sc.raw(f'<g class="scan {v}-scan-{i}">')
    sc.right("or-t", XL + 50, y_front - 12, y_front, 9, 55)
    sc.top("or-t", XL, XL + 50, y_front - 12, y_front, 55)
    sc.raw("</g>")


def crane_back(sc, v, yc, H, x_land=-78, x_sea=-12, half=80):
    """The crane's portal, what a container travelling through it passes in front of: rails, the far legs, the beams
    along the quay. The portal is wide enough for a container to pass between its legs."""
    for lx in (x_land, x_sea):
        sc.line("ln land-s", [(lx + 4.5, yc - half - 220, 0), (lx + 4.5, yc + half + 60, 0)])
    sc.raw(f'<g class="gantry {v}-gantry">')
    for lx in (x_land, x_sea):
        for ly in (yc + half, yc - half):
            sc.shade(lx, lx + 9, ly - 8, 60, k=.4)
    ly = yc + half
    for lx in (x_land, x_sea):
        sc.box("hull", lx - 3, lx + 12, ly - 9, ly + 18, 0, 9)
        sc.box("hull", lx, lx + 9, ly, ly + 9, 9, H)
        sc.box("hull", lx + 1, lx + 8, yc - half + 9, yc + half, 20, 28)
        sc.line("ln ind-rs", [(lx + 9, yc - half + 9, 28), (lx + 9, yc + half, 100)])
        sc.line("ln ind-rs", [(lx + 9, yc + half, 28), (lx + 9, yc - half + 9, 100)])
        sc.box("hull", lx + 1, lx + 8, yc - half + 9, yc + half, 100, 108)
    sc.box("hull", x_land + 9, x_sea, ly + 1, ly + 8, 100, 108)
    sc.line("ln ind-rs", [(x_land + 9, ly, 108), (x_sea, ly, H)])
    sc.raw("</g>")


def crane_front(sc, v, yc, H, x_land=-78, x_sea=-12, half=80):
    """The near legs and their beam, in front of a container that travels through the portal."""
    ly = yc - half
    sc.raw(f'<g class="gantry {v}-gantry">')
    for lx in (x_land, x_sea):
        sc.box("hull", lx - 3, lx + 12, ly - 9, ly + 18, 0, 9)
        sc.box("hull", lx, lx + 9, ly, ly + 9, 9, H)
    sc.box("hull", x_land + 9, x_sea, ly + 1, ly + 8, 100, 108)
    sc.line("ln ind-rs", [(x_land + 9, ly, 108), (x_sea, ly, H)])
    sc.raw("</g>")


def crane_top(sc, v, yc, H, x_back=-134, x_tip=124, x_sea=-12, x_land=-78, trolley=57):
    """Girders from over the truck's lane to over the ship, the trolley that runs between them, the operator's cab,
    machinery house, A-frame and stays."""
    g = 22
    sc.raw(f'<g class="gantry {v}-gantry">')
    for gy in (yc + g, yc - g):
        sc.box("hull", x_back, x_tip, gy - 5, gy + 5, H, H + 13)
        if gy > yc:   # the far girder first, then what sits between the two; the trolley runs below the house
            sc.box("hull", x_tip - 7, x_tip, yc - g + 5, yc + g - 5, H + 2, H + 11)
            sc.raw(f'<g class="trolley {v}-trolley">')
            sc.box("teal", trolley - 14, trolley + 14, yc - g + 5, yc + g - 5, H + 2, H + 12)
            sc.raw("</g>")
            sc.box("ind", x_land + 14, x_land + 56, yc - g + 2, yc + g - 2, H + 13, H + 38)   # machinery house
            sc.left("hull-l", yc - g + 2, x_land + 20, x_land + 50, H + 21, H + 31)
            sc.box("hull", x_land + 12, x_land + 58, yc - g, yc + g, H + 38, H + 42)
    # the cab hangs below the near girder
    sc.box("wht", trolley - 40, trolley - 22, yc - g - 8, yc - g + 8, H - 22, H - 1)
    sc.left("hull-l", yc - g - 8, trolley - 37, trolley - 25, H - 16, H - 7)
    sc.right("hull-r", trolley - 22, yc - g - 5, yc - g + 5, H - 16, H - 7)
    # A-frame above the waterside legs, with stays to the tip and to the back
    apex = H + 52
    for gy in (yc + g, yc - g):
        sc.box("hull", x_sea + 2, x_sea + 7, gy - 2.5, gy + 2.5, H + 13, apex)
        sc.line("ln hull-s", [(x_sea + 4.5, gy, apex), (x_tip - 8, gy, H + 13)])
        sc.line("ln hull-s", [(x_sea + 4.5, gy, apex), (x_back + 8, gy, H + 13)])
    sc.box("hull", x_sea + 2, x_sea + 7, yc - g - 2.5, yc + g + 2.5, apex - 5, apex)
    sc.box("teal", x_sea + 2.5, x_sea + 6.5, yc - 2, yc + 2, apex, apex + 4)
    sc.raw("</g>")


def falls(sc, cls, x0, yc, H, z=ZH):
    """The four falls from the trolley to the head block on a hoisted container."""
    for cx, cy in ((x0 + 15, yc + 14), (x0 + 35, yc + 14), (x0 + 15, yc - 14), (x0 + 35, yc - 14)):
        a, b = sc.P(cx, cy, H + 4), sc.P(cx, cy, z + 59)
        sc.raw(f'<path class="ln ink-s cable{" " + cls if cls else ""}" d="M{n(a[0])} {n(a[1])}V{n(b[1])}"/>')


def rig(sc, x0, yc, z=ZH, L=132):
    """Spreader and head block on the roof of a hoisted container."""
    sc.box("hull", x0 + 4, x0 + 46, yc - L / 2 + 5, yc + L / 2 - 5, z + 46, z + 51)
    sc.box("hull", x0 + 12, x0 + 38, yc - 17, yc + 17, z + 51, z + 59)


def hung(sc, ref, x0, yc, rigged=True, z=ZH):
    """A sealed container hoisted, with or without what holds it."""
    put(sc, ref, x0, yc - 66, z)
    seal(sc, x0 + SEAL[0], yc - 66 + SEAL[1], z + SEAL[2])
    if rigged:
        rig(sc, x0, yc, z)


def foam(sc, spots, z=WZ):
    """Flecks of foam on the water: small tiles, given as (x, y, size)."""
    for x, y, w in spots:
        sc.top("foam", x - w / 2, x + w / 2, y - w / 2, y + w / 2, z)


def ship_dims(S, slots, short=False):
    X0, X1, D = 14, 100, 14
    Yf = slots[-1][1] + 12          # the forecastle starts here
    E = Yf + (20 if short else 32)  # the hull's parallel body ends, the bow tapers
    return {"S": S, "slots": slots, "short": short, "X0": X0, "X1": X1, "D": D, "Yf": Yf, "E": E, "T": 62 if short else 86, "F": D + 13, "c": 14}


def ship_water(sc, g):
    """What the ship leaves on the water: the hull's shadow and, behind the stern, the wash."""
    S, short, X0, X1, E, T = (g[k] for k in ("S", "short", "X0", "X1", "E", "T"))
    xm = (X0 + X1) / 2
    # on the water: the hull's shadow, and the wash the propeller leaves behind the stern
    sc.poly("shade", [(X0, S - 20, WZ), (X1 + 12, S - 20, WZ), (X1 + 12, E, WZ), (xm + 10, E + T - 14, WZ), (xm, E + T - 20, WZ), (X0, E, WZ)])
    k = .5 if short else 1
    sc.poly("shade", [(X0 + 20, S, WZ), (X1 - 20, S, WZ), (X1 - 4, S - 120 * k, WZ), (X0 + 4, S - 120 * k, WZ)])
    sc.raw('<g class="wake">')
    for x, dxw in ((X0 + 12, -24), (X1 - 12, 24)):
        sc.line("ln foam-s", [(x, S - 4, WZ), (x + dxw * k, S - 4 - 130 * k, WZ)])
    foam(sc, [(xm - 12, S - 9 * k, 9), (xm + 10, S - 14 * k, 11), (xm - 2, S - 30 * k, 8), (xm + 18, S - 40 * k, 6), (xm - 20, S - 46 * k, 7),
              (xm + 2, S - 62 * k, 6), (xm - 14, S - 84 * k, 5), (xm + 16, S - 96 * k, 5), (xm, S - 118 * k, 4)])
    sc.raw("</g>")
    sc.raw('<g class="wash">')                     # what the propeller throws up while the ship works
    foam(sc, [(xm - 6, S - 20 * k, 12), (xm + 14, S - 30 * k, 9), (xm - 18, S - 34 * k, 8)])
    sc.raw("</g>")


def ship_hull(sc, g):
    """The ship Kapitan, bow to the upper right: hull with waterline, cut stern corners, bulwark and far rail,
    forecastle and hatches. What stands on the hatches and the superstructure follow."""
    S, slots, _short, X0, X1, D, Yf, E, T, F, c = (g[k] for k in ("S", "slots", "short", "X0", "X1", "D", "Yf", "E", "T", "F", "c"))
    xm = (X0 + X1) / 2
    # hull: transom, the cut corner, the side, the bow; the boot topping along the waterline
    sc.left("hull-l", S, X0 + c, X1 - c, WZ, D + 4)
    sc.left("ind-l", S, X0 + c, X1 - c, WZ, WZ + 7)
    sc.poly("hull-r", [(X1 - c, S, WZ), (X1, S + c, WZ), (X1, S + c, D + 4), (X1 - c, S, D + 4)])
    sc.poly("ind-r", [(X1 - c, S, WZ), (X1, S + c, WZ), (X1, S + c, WZ + 7), (X1 - c, S, WZ + 7)])
    sc.poly("hull-r", [(X1, E, WZ), (xm, E + T - 20, WZ), (xm, E + T, F + 4), (X1, E, F + 4)])
    sc.poly("ind-r", [(X1, E, WZ), (xm, E + T - 20, WZ), (xm, E + T - 14.6, WZ + 7), (X1, E, WZ + 7)])
    sc.line("ln foam-s", [(X0 + c, S, WZ), (X1 - c, S, WZ), (X1, S + c, WZ), (X1, E, WZ), (xm, E + T - 20, WZ)])
    sc.disc_r("ind-r", (X1 + xm) / 2 + 6, E + T / 2 - 14, 8, 4)                # hawse
    # the transom: two fairleads under the rim, the stern door, draught marks at its edge
    for x in (X0 + c + 6, X1 - c - 16):
        sc.left("ind-l", S, x, x + 10, D - 5, D)
    sc.left("ink", S, xm - 14, xm + 14, -12, 6)
    sc.line("ln ind-ls", [(xm, S, -12), (xm, S, 6)])
    for z in (-15, -9, -3):
        sc.line("ln ind-ls", [(X1 - c - 7, S, z), (X1 - c - 2, S, z)])
    # deck: rim of the bulwark, the deck inside it, the far rail
    sc.poly("ind-r", [(X0 + c, S, D + 4), (X0, S + c, D + 4), (X0, Yf, D + 4), (X1, Yf, D + 4), (X1, S + c, D + 4), (X1 - c, S, D + 4)])
    sc.right("hull-r", X0 + 3, S + c, Yf, D, D + 4)
    sc.poly("hull-t", [(X0 + c + 1, S + 3, D), (X0 + 3, S + c + 1, D), (X0 + 3, Yf, D), (X1 - 3, Yf, D), (X1 - 3, S + c + 1, D), (X1 - c - 1, S + 3, D)])
    for y in range(int(S) + c + 8, int(Yf), 24):
        sc.line("ln hull-s", [(X0 + 1.5, y, D + 4), (X0 + 1.5, y, D + 13)])
    sc.line("ln hull-s", [(X0 + 1.5, S + c, D + 13), (X0 + 1.5, Yf, D + 13)])
    # forecastle with windlass and foremast
    sc.left("hull-l", Yf, X0 + 3, X1 - 3, D, F + 4)
    sc.left("ind-t", Yf, xm - 7, xm + 7, D, D + 15)
    sc.poly("ind-r", [(X0, Yf, F + 4), (X0, E, F + 4), (xm, E + T, F + 4), (X1, E, F + 4), (X1, Yf, F + 4)])
    sc.poly("hull-t", [(X0 + 3, Yf + 3, F), (X0 + 3, E - 1, F), (xm, E + T - 8, F), (X1 - 3, E - 1, F), (X1 - 3, Yf + 3, F)])
    sc.box("hull", xm - 14, xm - 4, E - 8, E + 4, F, F + 7)
    sc.box("hull", xm + 4, xm + 14, E - 8, E + 4, F, F + 7)
    sc.line("ln hull-s", [(xm, E + T - 26, F), (xm, E + T - 26, F + 30)])
    sc.box("wht", xm - 2, xm + 2, E + T - 28, E + T - 24, F + 30, F + 34)
    # hatches, the farthest first, and what stands on them
    for ya, yb in reversed(slots):
        sc.box("ind", 28, 86, ya - 4, yb + 4, D, D + 6)
        for t in (1, 2, 3):
            y = ya - 4 + (yb - ya + 8) * t / 4
            sc.line("ln ind-rs", [(28, y, D + 6), (86, y, D + 6)])

def ship_side(sc, g, lib):
    """The hull's near side with the name and the plate for lib/. It is painted after everything on deck, because the
    bulwark hides the foot of what stands at the rail."""
    S, short, _X0, X1, D, Yf, E, F, c = (g[k] for k in ("S", "short", "X0", "X1", "D", "Yf", "E", "F", "c"))
    sc.top("ind-r", X1 - 3, X1, S + c, Yf - 14, D + 4)
    sc.poly("hull-r", [(X1, S + c, WZ), (X1, E, WZ), (X1, E, F + 4), (X1, Yf, F + 4), (X1, Yf - 14, D + 4), (X1, S + c, D + 4)])
    sc.right("ind-r", X1, S + c, E, WZ, WZ + 7)
    sc.line("ln foam-s", [(X1, S + c, WZ), (X1, E, WZ)])
    sc.line("ln ind-ls", [(X1, S + c + 2, 4), (X1, E - 2, 4)])                 # rubbing strake
    sc.text_r("tx-hull", "Kapitan", X1, S + c + 8, WZ + 14, "start")
    if not short:
        for y in (S + 132, S + 150, S + 168):
            sc.disc_r("ind-r", X1, y, -6, 3.2)
    sc.plate_r(X1, lib, lib + 52, -13, 5, [("tx-plate", "lib/", 12.5)])


def ship_top(sc, g):
    """Aft: one block of accommodation with the wheelhouse on its bridge deck, a mast, the funnel and its smoke,
    the stern rail and the ensign."""
    S, X0, X1, D, c = (g[k] for k in ("S", "X0", "X1", "D", "c"))
    xm = (X0 + X1) / 2
    # aft: the accommodation, one block with a row of windows; on it the bridge deck with its wings and the wheelhouse
    b0 = S + 20
    sc.shade(24, 90, b0, 34, z=D, k=.25, cls="shade-deck")
    sc.box("wht", 24, 90, b0, b0 + 56, D, D + 32)
    for y in (b0 + 9, b0 + 24, b0 + 39):
        sc.right("hull-r", 90, y, y + 9, D + 13, D + 23)
    sc.left("hull-l", b0, 34, 46, D, D + 22)
    sc.box("wht", 16, 98, b0 + 22, b0 + 56, D + 32, D + 36)
    sc.box("wht", 30, 84, b0 + 26, b0 + 54, D + 36, D + 58)
    sc.left("hull-l", b0 + 26, 34, 80, D + 43, D + 53)
    sc.right("hull-r", 84, b0 + 29, b0 + 51, D + 43, D + 53)
    sc.box("hull", 28, 86, b0 + 24, b0 + 56, D + 58, D + 61)
    sc.line("ln hull-s", [(57, b0 + 42, D + 61), (57, b0 + 42, D + 84)])
    sc.box("wht", 50, 64, b0 + 40, b0 + 44, D + 71, D + 74)
    # the funnel aft on the block, with its band, and the smoke straight above it
    sc.box("hull", 52, 76, b0 + 3, b0 + 19, D + 32, D + 64)
    sc.left("teal-l", b0 + 3, 52, 76, D + 49, D + 57)
    sc.right("teal-r", 76, b0 + 3, b0 + 19, D + 49, D + 57)
    sc.top("ink", 56, 72, b0 + 6, b0 + 16, D + 64)
    for i, (z, w) in enumerate(((D + 70, 6), (D + 80, 8), (D + 93, 11))):
        sc.raw(f'<g class="puff puff-{i + 1}">')
        cube(sc, "ind", 64 - w / 2, b0 + 11 - i * 2 - w / 2, z, w)
        sc.raw("</g>")
    for i in range(3):                             # the run of smoke while the ship works: three more, which rise and thin out
        sc.raw(f'<g class="smoke smoke-{i + 1}">')
        cube(sc, "ind", 58, b0 + 4, D + 96, 12)
        sc.raw("</g>")
    # the stern rail and the ensign staff
    for x in (X0 + c + 4, xm, X1 - c - 4):
        sc.line("ln hull-s", [(x, S + 1.5, D + 4), (x, S + 1.5, D + 13)])
    sc.line("ln hull-s", [(X0 + c, S + 1.5, D + 13), (X1 - c, S + 1.5, D + 13), (X1 - 1.5, S + c, D + 13)])
    sc.line("ln hull-s", [(xm - 26, S + 3, D + 4), (xm - 26, S + 3, D + 30)])
    sc.poly("teal-r", [(xm - 26, S + 3, D + 30), (xm - 26, S + 3, D + 21), (xm - 12, S + 3, D + 25.5)])


def ship_rail(sc, g):
    """The near rail, in front of everything on deck."""
    S, X1, D = g["S"], g["X1"], g["D"]
    y0 = S + 82
    for y in range(int(y0), int(g["Yf"]) - 14, 24):
        sc.line("ln hull-s", [(X1 - 1.5, y, D + 4), (X1 - 1.5, y, D + 13)])
    sc.line("ln hull-s", [(X1 - 1.5, y0, D + 13), (X1 - 1.5, g["Yf"] - 16, D + 13)])


def mooring(sc, a, b):
    pa, pb = sc.P(*a), sc.P(*b)
    mx, my = (pa[0] + pb[0]) / 2, max(pa[1], pb[1]) + 6
    sc.raw(f'<path class="ln hull-s" d="M{n(pa[0])} {n(pa[1])}Q{n(mx)} {n(my)} {n(pb[0])} {n(pb[1])}"/>')


def depot(sc, fam, x0, x1, y0, y1, h=30):
    """An island's store: a door and a window in its long wall, a hatch in the end wall, a flat roof."""
    sc.shade(x0 - 2, x1 + 2, y0 - 2, h + 3)
    sc.box(fam, x0, x1, y0, y1, 0, h)
    sc.right("hull-r", x1, y0 + 8, y0 + 22, 0, 20)
    sc.right("light", x1, y0 + 30, y1 - 8, 10, 20)
    sc.left("hull-l", y0, x0 + 9, x1 - 9, 0, 18)
    for z in (6, 12):
        sc.line(f"ln {fam}-ls", [(x0 + 9, y0, z), (x1 - 9, y0, z)])
    sc.box("hull", x0 - 2, x1 + 2, y0 - 2, y1 + 2, h, h + 3)
    sc.top(f"{fam}-t", x0 + 2, x1 - 2, y0 + 2, y1 - 2, h + 3)


def rock(sc, x, y, w):
    sc.box("land", x, x + w, y, y + w * .8, 0, w * .5)


CARGO_K = "kub"   # the kubernetes generator's colour, a strong indigo: its container, what it writes, and the store on its island


def island(sc, fam, parcels=3):
    """An island: shallows and a line of surf, a beach, the green above it with a knoll and trees, a store, the parcels
    landed and a pier towards the ship. Its name stands beside it (tag). Returns the pier's head and two places on its
    shore where a label's stem can end: at the back and at the front."""
    z0, zb = -18, -11
    beach = [(0, 24), (0, 140), (16, 140), (16, 168), (66, 168), (66, 190), (112, 190), (112, 176), (130, 176), (130, 56), (114, 56),
             (114, 20), (92, 20), (92, 0), (38, 0), (38, 24)]
    green = [(9, 33), (9, 131), (25, 131), (25, 159), (75, 159), (75, 181), (103, 181), (103, 167), (121, 167), (121, 65), (105, 65),
             (105, 29), (83, 29), (83, 9), (47, 9), (47, 33)]
    shallows = [(x + (13 if x > 50 else -13), y + (13 if y > 90 else -13)) for x, y in beach]
    sc.poly("shallow", [(x, y, z0) for x, y in shallows])
    sc.line("ln foam-s surf", [(x, y, z0) for x, y in shallows + shallows[:1]])
    sc.slab("road", beach, z0, zb, foam=True)
    sc.slab("land", green, zb, 0)
    sc.slab("land", [(14, 56), (14, 100), (30, 100), (30, 126), (56, 126), (56, 84), (42, 84), (42, 56)], 0, 9)   # the knoll
    sc.raw(f'<g transform="translate(0 {n(-9 * sc.k)})">')
    tree(sc, 27, 82, 1.15)
    tree(sc, 44, 108, .95)
    sc.raw("</g>")
    tree(sc, 38, 146, 1.05)
    tree(sc, 62, 22, .9)
    sc.raw(f'<g transform="translate(0 {n(11 * sc.k)})">')
    rock(sc, 120, 34, 8)
    rock(sc, 4, 128, 7)
    sc.raw("</g>")
    depot(sc, fam, 62, 102, 96, 154)
    for i in range(parcels):
        py, pz = (62 + 15 * i, 0) if i < 2 else (69.5, 14)
        if pz == 0:
            sc.shade(88, 102, py, 14, k=.4)
        cube(sc, fam, 88, py, pz, 14)
    sc.shade(54, 76, -36, 12, z=z0)                                  # the pier and its lamp
    sc.box("hull", 54, 76, -36, 6, z0, -8)
    sc.line("ln hull-s", [(58, -28, -8), (58, -28, 12)])
    sc.box("wht", 56, 60, -30, -26, 12, 16)
    return sc.P(65, -40, z0), sc.P(18, 140, 0), sc.P(40, 14, zb)


def tag(sc, px, py, name, path, tail, narrow=False):
    """An island's name and the path it stands for: a flat label beside it, in the manner of the stations' pills."""
    w = 196 if narrow else 186
    tx, ty = tail[0] - px, tail[1] - py
    ax = min(max(tx, 14), w - 14)
    ay = 46 if ty > 23 else 0
    sc.raw(f'<g class="tag" transform="translate({n(px)} {n(py)})">'
           f'<path class="ln" d="M{n(ax)} {ay}L{n(tx)} {n(ty)}"/><circle class="pin-dot" cx="{n(tx)}" cy="{n(ty)}" r="3.5"/>'
           f'<rect class="pin-bg" width="{w}" height="46" rx="12"/>'
           f'<text class="tx-tag" x="13" y="19.5">{name}</text><text class="{"tx-tagp-n" if narrow else "tx-tagp"}" x="13" y="36">{path}</text></g>')


def parcel(sc, fam, px, py, cls):
    """A parcel under way: a cube on a raft, placed in screen space on its route."""
    sc.raw(f'<g class="parcel {cls}">')
    o = Iso(px - 10, py - 2, sc.out)
    o.top("shade-water", -3, 17, -9, 11, 0)
    o.box("ind" if fam == CARGO_K else "hull", -2, 14, -2, 14, 0, 3)     # the raft, in the tone that sets the cube off
    o.box(fam, 0, 12, 0, 12, 3, 15)
    sc.raw("</g>")


def waves(sc, marks):
    d = "".join(f"M{n(x)} {n(y)}l{n(l * C)} {n(-l * S)}M{n(x + 14)} {n(y + 5)}l{n(l * .45 * C)} {n(-l * .45 * S)}" for x, y, *o in marks for l in (o or [20]))
    sc.raw(f'<path class="ln foam-s" d="{d}"/>')


def swells(sc, marks):
    """Long broken lines of swell along the same axis as the wave marks."""
    d = "".join(f"M{n(x)} {n(y)}l{n(l * C)} {n(-l * S)}" for x, y, l in marks)
    sc.raw(f'<path class="ln foam-s swell" d="{d}"/>')


def buoy(sc, px, py):
    o = Iso(px, py, sc.out)
    o.top("shade", -9, 9, -16, 4, 0)
    o.box("teal", -6, 6, -6, 6, 0, 5)
    o.poly("teal-l", [(-5, -5, 5), (5, -5, 5), (0, 0, 24)])
    o.poly("teal-r", [(5, -5, 5), (5, 5, 5), (0, 0, 24)])
    o.box("wht", -2, 2, -2, 2, 22, 27)


PIN_W = {"Inventory": 104, "Verify": 84, "Fetch": 78, "Generators": 118, "Output": 88}


def pin(sc, i, label, px, py, tail):
    """A station's pill: flat, above the drawing. tail is where its stem ends, in the drawing's coordinates."""
    w = PIN_W[label]
    tx, ty = tail[0] - px, tail[1] - py
    ax = min(max(tx, 14), w - 14)
    ay = 28 if ty > 14 else 0
    sc.raw(f'<g class="pin" data-station="{i}" transform="translate({n(px)} {n(py)})">'
           f'<path class="ln" d="M{n(ax)} {ay}L{n(tx)} {n(ty)}"/><circle class="pin-dot" cx="{n(tx)}" cy="{n(ty)}" r="3.5"/>'
           f'<rect class="pin-ring" x="-5" y="-5" width="{w + 10}" height="38" rx="19"/>'
           f'<rect class="pin-bg" width="{w}" height="28" rx="14"/><circle class="pin-n" cx="14" cy="14" r="10"/>'
           f'<text class="tx-pin-n" x="14" y="18.6" text-anchor="middle">{i}</text><text class="tx-pin" x="30" y="18.6">{label}</text></g>')


def route(sc, pts):
    """A dotted route through three screen points; returns the curve for the parcels and their keyframes."""
    (x0, y0), (cx, cy), (x1, y1) = pts
    sc.raw(f'<path class="ln foam-s route" d="M{n(x0)} {n(y0)}Q{n(cx)} {n(cy)} {n(x1)} {n(y1)}"/>')
    return lambda t: ((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1)


def station(sc, i):
    sc.raw(f'<g class="st" data-station="{i}">')


def end(sc):
    sc.raw("</g>")


# ---------------------------------------------------------------- motion
# Every motion changes transform and opacity only and ends within its station's time. A part is drawn where it ends up, so
# the drawing without motion shows the finished run; a rule moves it there from where it starts. The rules that
# depend on the geometry are written here and land between the harbour-keyframes markers of style.css.

def kf(name, frames):
    return f"@keyframes {name} {{ " + " ".join(f"{p}% {{ {d} }}" for p, d in frames) + " }"


def mv(a, b):
    """The CSS translate that puts a part drawn at screen point b at screen point a."""
    return f"translate({n(a[0] - b[0])}px, {n(a[1] - b[1])}px)"


def run(css, v, cls, name, frames, timing):
    css.append(kf(f"h{v}-{name}", frames))
    css.append(f".h-st.on .h-{cls} {{ animation: h{v}-{name} {timing} both; }}")


def glow(sc, i, x0, y0, z0, roof, L=132, W=50, H=46):
    """A container at work: a light frame around its plate, and its roof where that is free. The plate stays as it is."""
    x1 = x0 + W
    sc.raw(f'<g class="glow glow-{i}">')
    if roof:
        sc.top("light", x0, x1, y0, y0 + L, z0 + H)
    sc.right("light", x1, y0, y0 + 9, z0, z0 + H)
    sc.right("light", x1, y0 + L - 9, y0 + L, z0, z0 + H)
    sc.right("light", x1, y0 + 9, y0 + L - 9, z0, z0 + 12)
    sc.right("light", x1, y0 + 9, y0 + L - 9, z0 + H - 12, z0 + H)
    sc.raw("</g>")


def stack(sc, css, v, key, fam, spots, origin, delay):
    """The file parcels one generator writes: they rise out of its container and stack on the deck beside it.
    Returns where each stands, for the parcels that later sail from there."""
    places = []
    for i, (x, y, z) in enumerate(spots):
        cls = f"{v}-rise-{key}{i + 1}"
        sc.raw(f'<g class="rise {cls}">')
        if z == spots[0][2]:
            sc.top("shade-deck", x, x + 12, y - 5, y + 12, z)
        cube(sc, fam, x, y, z, 12)
        sc.raw("</g>")
        rest, start = sc.P(x + 6, y + 6, z), sc.P(*origin)
        apex = ((rest[0] + start[0]) / 2, min(rest[1], start[1]) - 26)
        run(css, v, cls, f"rise-{key}{i + 1}", [(0, f"opacity: 0; transform: {mv(start, rest)}"), (25, "opacity: 1"), (55, f"transform: {mv(apex, rest)}"), (100, "transform: none")],
            f".65s {delay + .14 * i:.2f}s ease-in-out")
        places.append(rest)
    return places


def sailing(sc, css, v, key, fam, curve, rests, starts):
    """Parcels at rest along a route. Selected, each leaves its place in the stack on deck and sails there."""
    for i, (t, start) in enumerate(zip(rests, starts)):
        cls = f"{v}-p{key}-{i + 1}"
        rest = curve(t)
        parcel(sc, fam, *rest, cls)
        frames = [(0, f"transform: {mv(start, rest)}"), (16, f"transform: {mv(curve(0), rest)}")]
        frames += [(16 + round(84 * k / 5), f"transform: {mv(curve(t * k / 5), rest)}") for k in range(1, 6)]
        run(css, v, cls, f"p{key}-{i + 1}", frames, f"1.5s {.14 * i:.2f}s ease-in-out")


def along_y(d):
    return f"translate({n(d * C)}px, {n(-d * S)}px)"


def along_x(d):
    return f"translate({n(d * C)}px, {n(d * S)}px)"


def timed(D, rows):
    """Keyframes from (seconds, declarations) for a run of D seconds."""
    return [(f"{100 * t / D:.2f}".rstrip("0").rstrip("."), d) for t, d in rows]


def shown(D, a, b, start, stop):
    """Visible from a to b seconds only, moving from start to stop meanwhile."""
    rows = [(0, f"opacity: 0; transform: {start}"), (a - .01, f"opacity: 0; transform: {start}")] if a else []
    rows += [(a, f"opacity: 1; transform: {start}; animation-timing-function: ease-in-out"), (b, f"opacity: 1; transform: {stop}")]
    return rows + ([(b + .01, f"opacity: 0; transform: {stop}"), (D, f"opacity: 0; transform: {stop}")] if b < D else [])


D1, D2, D3 = 2.2, 2.4, 3.45   # how long the motion of stations 1 to 3 takes, in seconds
T2ND = 1.9                    # when in station 3 the crane takes the second container
TURN = (.2, .5, .95, 1.27, 1.53)   # one container's turn: the spreader is down on it, it is hoisted, over the ship, on deck, the spreader up again


def at_station(css, k, cls, name, D, rows, base=""):
    """A part that belongs to no single station, the truck: its rule hangs on the station the frame shows."""
    css.append(kf(name, timed(D, rows)))
    css.append(f'.scene-frame[data-at="{k}"] .h-{cls} {{ opacity: 1; {base}animation: {name} {D}s linear both; }}')


def customs(css, v, pivot, order):
    """Station 2 at the gate: the scan over each container, the nearer to the gate first, its seal, the signal, the
    barrier. order: the containers' numbers in the order of the scan."""
    for k, i in enumerate(order):
        css.append(f".h-st.on .h-{v}-scan-{i} {{ animation: hb-scan .28s {.42 + .27 * k:.2f}s linear both; }}")
        css.append(f'.scene-frame[data-at="2"] .h-{v}-tseal-{i} {{ animation: hb-pop .25s {.72 + .27 * k:.2f}s both; }}')
    css.append(f".h-{v}-arm {{ transform: {turn(pivot, 90)}; }}")
    css.append(f".harbour.live .h-st:not(.on, .done) .h-{v}-arm {{ transform: none; }}")
    run(css, v, f"{v}-arm", "arm", timed(D2, [(0, "transform: matrix(1, 0, 0, 1, 0, 0)"), (1.08, "transform: matrix(1, 0, 0, 1, 0, 0)")]
                                         + [(1.08 + .05 * k, f"transform: {turn(pivot, 15 * k)}") for k in range(1, 7)]), f"{D2}s linear")


def unload(css, v, key, fall, drops, shift=0, advance=0, fade=False):
    """Station 3: the crane unloads the truck. For each container the trolley stands over the lane, the spreader comes
    down on the container, the hoist lifts it off the truck, the trolley carries it between the portal's legs over the
    ship, the hoist lowers it and the spreader goes up again. Between the two the trolley returns, while the crane
    travels to the second place on deck (shift) or the truck moves up (advance). Then the truck drives off. Each phase
    shows the copy of the container, or of the empty spreader, that is painted at the right depth for it."""
    D, back, lift = D3, along_x(XL - XS), ZH - 9
    ease = "; animation-timing-function: ease-in-out"
    long = f"scaleY({(fall + lift) / fall:.3f})"
    park, parkc, rest, trolley, turns = [], [], [(0, "opacity: 0; transform: none")], [], []
    for i, t0 in ((1, 0), (2, T2ND)):
        ta, tb, tc, td, te = (t0 + t for t in TURN)
        turns.append((ta, tb, te))
        drop, k = drops[i - 1], (fall + drops[i - 1]) / fall
        for rows, still, moved in ((park, "none", f"translateY({lift}px)"), (parkc, "scaleY(1)", long)):
            rows += ([(t0 - .01, f"opacity: 0; transform: {still}")] if t0 else []) + [(t0, f"opacity: 1; transform: {still}{ease}"), (ta, f"opacity: 1; transform: {moved}"), (ta + .01, f"opacity: 0; transform: {moved}")]
        run(css, v, f"{v}-lift-{i}", f"lift-{i}", timed(D, shown(D, ta, tb, f"translateY({lift}px)", "none")), f"{D}s linear")
        run(css, v, f"{v}-liftc-{i}", f"liftc-{i}", timed(D, shown(D, ta, tb, long, "scaleY(1)")), f"{D}s linear")
        run(css, v, f"{v}-carry-{i}", f"carry-{i}", timed(D, shown(D, tb, tc, back, "none")), f"{D}s linear")
        hidden = [(0, "opacity: 0; transform: {0}"), (tc - .01, "opacity: 0; transform: {0}")]
        down = hidden + [(tc, "opacity: 1; transform: {0}; animation-timing-function: ease-in"), (td, "transform: {1}"), (td + .05, "transform: {2}"), (td + .1, "opacity: 1; transform: {1}")]
        up = [(td + .11, "opacity: 1; transform: {1}" + ease), (te, "opacity: 1; transform: {0}"), (te + .01, "opacity: 0; transform: {0}"), (D, "opacity: 0; transform: {0}")]
        box = ("none", f"translateY({drop}px)", f"translateY({drop - 3}px)")
        rope = ("scaleY(1)", f"scaleY({k:.3f})", f"scaleY({(fall + drop - 3) / fall:.3f})")
        run(css, v, f"{v}-load-{i}", f"load-{i}", timed(D, [(t, d.format(*box)) for t, d in down + [(D, "opacity: 1; transform: {1}")]]), f"{D}s linear")
        css.append(f".h-{v}-load-{i} {{ transform: translateY({drop}px); }}")
        run(css, v, f"{v}-sp-{i}", f"sp-{i}", timed(D, [(t, d.format(*box)) for t, d in down + up]), f"{D}s linear")
        run(css, v, f"{v}-loadc-{i}", f"loadc-{i}", timed(D, [(t, d.format(*rope)) for t, d in down + up]), f"{D}s linear")
        rest += [(te, "opacity: 0; transform: none"), (te + .01, f"opacity: 1; transform: none{ease}")]
        rest += [(T2ND, f"opacity: 1; transform: {back}"), (T2ND + .01, f"opacity: 0; transform: {back}")] if i == 1 else [(D, "opacity: 1; transform: none")]
        trolley += [(t0, f"transform: {back}"), (tb, f"transform: {back}{ease}"), (tc, "transform: none"), (te, f"transform: none{ease}")]
    (a1, _b1, e1), (a2, b2, _e2) = turns
    for cls, rows in (("park", park), ("parkc", parkc), ("rest", rest), ("trolley", trolley + [(D, "transform: none")])):
        run(css, v, f"{v}-{cls}", cls, timed(D, rows + ([(D, rows[-1][1])] if rows[-1][0] < D else [])), f"{D}s linear")
    css.append(f".harbour.live .h-st:not(.on, .done) .h-{v}-trolley {{ transform: {back}; }}")
    if shift:
        run(css, v, f"{v}-gantry", "gantry", timed(D, [(0, f"transform: {along_y(shift)}"), (e1, f"transform: {along_y(shift)}{ease}"), (T2ND, "transform: none"), (D, "transform: none")]), f"{D}s linear")
        css.append(f".harbour.live .h-st:not(.on, .done) .h-{v}-gantry {{ transform: {along_y(shift)}; }}")
    here, off, go = along_y(advance), along_y(advance + (480 if fade else 700)), b2 + .1
    rows = [(0, "transform: none"), (e1, f"transform: none{ease}"), (T2ND, f"transform: {here}"), (go, f"transform: {here}; animation-timing-function: ease-in")]
    rows += [(D - .15, f"opacity: 1; transform: {off}"), (D, f"opacity: 0; transform: {off}")] if fade else [(D, f"transform: {off}")]
    at_station(css, 3, f"{v}-truck{key}", f"h{v}-truck{key}-3", D, rows)
    for i, ta in ((1, a1), (2, a2)):   # a container stands on the truck until the hoist has it
        css.append(kf(f"h{v}-tc{key}-{i}", timed(D, [(0, "opacity: 1"), (ta, "opacity: 1"), (ta + .01, "opacity: 0"), (D, "opacity: 0")])))
        css.append(f'.scene-frame[data-at="3"] .h-{v}-tc{key}-{i} {{ animation: h{v}-tc{key}-{i} {D}s linear both; }}')


NAME_K, PATH_K = "Kubernetes manifests", "compiled/prod/manifests/"
NAME_T, PATH_T = "Terraform JSON", "compiled/prod/terraform/"

ALT = ("Isometric drawing of a harbour with five numbered stations. 1 Inventory: the harbour office with the cargo list of the target prod. "
       "2 Verify: a customs gate labelled kadet-hub. 3 Fetch: a crane has set the containers kubernetes and terraform-aws on the ship. "
       "4 Generators: the ship Kapitan. 5 Output: routes to two islands, Kubernetes manifests and Terraform JSON.")


def prefixed(markup):
    """Every class with the prefix h-, so the ancestor-free rules of style.css meet nothing else on the site."""
    return re.sub(r'class="([^"]+)"', lambda m: 'class="' + " ".join("h-" + c for c in m.group(1).split()) + '"', markup)


def svg(v, w, h, sc, ref=None):
    body = prefixed("".join(sc.out))
    if ref:   # the phone's crops show this drawing again through <use>
        body = f'<g id="{ref}">{body}</g>'
    return f'<svg class="sc scene scene-{v}" viewBox="0 0 {w} {h}" role="img" aria-label="{ALT}">{body}</svg>'


# ---------------------------------------------------------------- the wide drawing

def afloat(sc, css, v, g, ys, HC, mooring_lines, on_top=False):
    """The crane, the ship and the two containers' way from the truck's lane to the deck, in the order that hides what
    lies behind. ys: where along the quay each container is lifted and set down; the crane is drawn where it ends.
    Everything on the ship stands in one group, which bobs while the generators run.
    Returns where the parcels stack and the length of a fall above a hoisted container."""
    slots, D = g["slots"], g["D"]
    ya = slots[0][0]
    yb = ya if on_top else slots[1][0]              # one hatch: the second container lands on the first
    zs = (D + 6, D + 52 if on_top else D + 6)
    refs = (f"h{v}-ck", f"h{v}-ct")
    yc = ys[1]
    station(sc, 3)
    sc.raw(f'<g class="gantry {v}-gantry">')        # the empty spreader over the lane, parked and on its way down to the truck
    falls(sc, f"parkc {v}-parkc", XL, yc, HC)
    sc.raw(f'<g class="park {v}-park">')
    rig(sc, XL, yc)
    sc.raw("</g></g>")
    for i in (2, 1):                                # hoisted off the truck: behind every part of the crane
        falls(sc, f"liftc {v}-liftc-{i}", XL, ys[i - 1], HC)
        sc.raw(f'<g class="lift {v}-lift-{i}">')
        hung(sc, refs[i - 1], XL, ys[i - 1])
        sc.raw("</g>")
    crane_back(sc, v, yc, HC)
    sc.raw(f'<g class="gantry {v}-gantry"><g class="rest {v}-rest">')   # the empty spreader over the ship, and on its way back
    falls(sc, "", XS, yc, HC)
    rig(sc, XS, yc)
    sc.raw("</g></g>")
    for i in (2, 1):                                # carried through the portal: in front of its far side
        sc.raw(f'<g class="carry {v}-carry-{i}">')
        falls(sc, "", XS, ys[i - 1], HC)
        hung(sc, refs[i - 1], XS, ys[i - 1])
        sc.raw("</g>")
    crane_front(sc, v, yc, HC)
    end(sc)
    station(sc, 4)
    for line in mooring_lines[:1]:
        mooring(sc, *line)
    ship_water(sc, g)
    end(sc)
    sc.raw('<g class="ship" data-station="4">')
    station(sc, 4)
    ship_hull(sc, g)
    end(sc)

    for i in ((1, 2) if on_top else (2, 1)):        # lowered and set free; what stands nearer is painted later
        station(sc, 3)
        falls(sc, f"spc {v}-loadc-{i}", XS, ys[i - 1], HC)
        sc.raw(f'<g class="load {v}-load-{i}">')
        hung(sc, refs[i - 1], XS, ys[i - 1], rigged=False)
        sc.raw("</g>")
        sc.raw(f'<g class="sp {v}-sp-{i}">')
        rig(sc, XS, ys[i - 1])
        sc.raw("</g>")
        end(sc)
    station(sc, 4)
    ship_top(sc, g)
    end(sc)
    station(sc, 4)
    glow(sc, 1, XS, ya, zs[0], roof=not on_top)
    glow(sc, 2, XS, yb, zs[1], roof=False)
    if on_top:   # one hatch: the stacks stand at the two ends of the containers' plates
        places = (stack(sc, css, v, "k", CARGO_K, [(85, ya + 130, D), (85, ya + 118, D), (85, ya + 124, D + 12)], (57, ya + 96, D + 52), .15),
                  stack(sc, css, v, "t", "teal", [(85, ya - 5, D), (85, ya - 5, D + 12)], (57, ya + 36, D + 98), .75))
    else:        # each stack beyond the far end of its container's plate
        places = (stack(sc, css, v, "k", CARGO_K, [(85, ya + 134, D), (85, ya + 122, D), (85, ya + 128, D + 12)], (57, ya + 66, D + 52), .15),
                  stack(sc, css, v, "t", "teal", [(85, yb + 130, D), (85, yb + 118, D)], (57, yb + 66, D + 52), .75))
    ship_side(sc, g, lib=ya + 100 if on_top else yb + 40)   # the plate clear of the name on the short hull
    ship_rail(sc, g)
    end(sc)
    sc.raw("</g>")
    station(sc, 4)
    for line in mooring_lines[1:]:
        mooring(sc, *line)
    end(sc)
    station(sc, 3)
    crane_top(sc, v, yc, HC)
    end(sc)
    return places, HC + 4 - (ZH + 59), (ZH - zs[0], ZH - zs[1])


def wide():
    W, H = 1168, 700
    sc = Iso(112, 616)
    css, v = [], "w"
    yg, HC = 384, 176
    yc1 = yg + 140
    yc2 = yc1 + 140
    slots = [(yc1 - 66, yc1 + 66), (yc2 - 66, yc2 + 66)]
    S = slots[0][0] - 82
    g = ship_dims(S, slots)
    defs(sc, v)
    swells(sc, [(330, 692, 90), (560, 668, 120), (790, 540, 70), (1040, 416, 110), (1060, 688, 80), (120, 688, 70)])
    waves(sc, [(650, 648, 22), (440, 620, 18), (580, 560, 22), (830, 462, 18), (1104, 60, 18), (250, 666, 22),
               (720, 600, 18), (690, 510, 20), (1110, 670, 18), (800, 666, 20), (40, 692, 18)])
    quay(sc, -340, 1300)
    road(sc, -132, -80, -340, 1300)
    for y in (S - 104, S - 52, S - 8, g["E"] + 58, g["E"] + 98, g["E"] + 158, g["E"] + 228):
        bollard(sc, -16, y)
    for y in (96, g["E"] + 128):
        lamp(sc, -30, y)
    # the yard behind the road: empty slots, and trees along its back
    for x in (-250, -196):
        for y in (436, 510, 584, 658, 732):
            sc.line("ln land-s", [(x, y, 0), (x + 42, y, 0), (x + 42, y + 62, 0), (x, y + 62, 0), (x, y, 0)])
    for y, k in ((348, 1.1), (392, .9), (470, 1.2), (540, 1.0), (600, 1.15), (668, .95), (740, 1.1), (812, .9)):
        tree(sc, -292, y, k)
    for x, y, k in ((-560, 470, 1.1), (-520, 520, .9), (-470, 590, 1.2), (-430, 640, 1.0), (-600, 420, .95), (-380, 700, 1.1), (-500, 430, 1.0)):
        tree(sc, x, y, k)

    station(sc, 1)
    office(sc, -262, 160)
    end(sc)
    station(sc, 2)
    pivot = gate_back(sc, v, yg)
    end(sc)
    # the truck: drawn where it stands at the crane; the stylesheet brings it there by way of the office and the gate
    tail = {"crane": yc1 - 68, "gate": yg - 22 - TRUCK}
    tail["office"], tail["edge"] = tail["gate"] - 40, tail["gate"] - 420
    truck(sc, v, "", tail["crane"], [(f"h{v}-ck", 2, 1), (f"h{v}-ct", 142, 2)])
    to = {k: along_y(y - tail["crane"]) for k, y in tail.items()}
    ease = "; animation-timing-function: cubic-bezier(.2, .7, .3, 1)"
    at_station(css, 1, f"{v}-truck", "hw-truck-1", D1, [(0, f"transform: {to['edge']}"), (.9, f"transform: {to['edge']}{ease}"), (1.95, f"transform: {to['office']}"),
                                                         (D1, f"transform: {to['office']}")], base=f"transform: {to['office']}; ")
    at_station(css, 2, f"{v}-truck", "hw-truck-2", D2, [(0, f"transform: {to['office']}{ease}"), (.4, f"transform: {to['gate']}"),
                                                         (1.4, f"transform: {to['gate']}; animation-timing-function: ease-in-out"), (2.3, "transform: none"), (D2, "transform: none")])
    station(sc, 2)
    scan(sc, v, 2, tail["gate"] + 142 + 132)
    scan(sc, v, 1, tail["gate"] + 2 + 132)
    gate_front(sc, yg)
    customs(css, v, pivot, order=(2, 1))
    end(sc)

    (sk, st_), fall, drops = afloat(sc, css, v, g, (yc1, yc2), HC,
                                    mooring_lines=[((30, S + 2, 18), (-16, S - 8, 9)), ((17, g["E"] + 20, g["F"] + 4), (-16, g["E"] + 58, 9))])
    unload(css, v, "", fall, drops, shift=yc1 - yc2)

    # station 5: two islands, the routes to them and the parcels under way
    station(sc, 5)
    bow = sc.P(g["X1"] + 8, g["E"] - 10, WZ)
    ik, it = sc.at(886, 336), sc.at(856, 600)
    mark = len(sc.out)
    jk, ak, _ = island(ik, CARGO_K)
    jt, at, _ = island(it, "teal", parcels=2)
    islands = sc.out[mark:]
    del sc.out[mark:]
    rk = route(sc, [(bow[0] + 2, bow[1] + 6), (bow[0] + 30, bow[1] + 60), (jk[0] - 4, jk[1] + 4)])
    rt = route(sc, [(bow[0] - 8, bow[1] + 12), (bow[0] - 26, bow[1] + 170), (jt[0] - 6, jt[1] + 2)])
    sc.out.extend(islands)
    sailing(sc, css, v, "k", CARGO_K, rk, (.86, .52, .2), sk)
    sailing(sc, css, v, "t", "teal", rt, (.82, .44), st_)
    end(sc)
    buoy(sc, 640, 652)

    pin(sc, 1, "Inventory", 22, 196, sc.P(-214, 250, 99))
    pin(sc, 2, "Verify", 192, 150, sc.P(-166, yg + 5, GATE[0] + GATE[1]))
    station(sc, 3)                                   # this pill travels with the crane
    sc.raw(f'<g class="gantry {v}-gantry">')
    pin(sc, 3, "Fetch", 812, 84, sc.P(110, yc2, HC + 10))
    sc.raw("</g>")
    end(sc)
    pin(sc, 4, "Generators", 344, 628, sc.P(g["X1"] - g["c"] / 2, S + g["c"] / 2, -6))
    pin(sc, 5, "Output", 736, 548, rt(.36))
    station(sc, 5)
    tag(sc, 958, 180, NAME_K, PATH_K, ak)
    tag(sc, 868, 450, NAME_T, PATH_T, at)
    end(sc)
    return svg("wide", W, H, sc), css


# ---------------------------------------------------------------- the vertical drawing, below 48rem

BAND = 316   # the height of a phone crop, in the vertical drawing's units: 300 px in a 361 px column


def strip(sc, x0, x1, y0, y1):
    """A piece of quay that runs through the drawing from edge to edge."""
    foot = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
    sc.poly("shade", [(x + 3, y - 14, WZ) for x, y in foot])
    sc.slab("land", foot, WZ, 0, foam=True)


def narrow():
    """The same harbour in three pieces of quay, one above the other: the office, customs, and the crane with the ship,
    then the two islands. 380 units wide for a 361 px column, so its labels render at 95 %. Each station has a window
    of BAND units, which the phone shows alone above the station's text. The truck stands on each piece in turn: it
    leaves one window and is at its place in the next. Returns the drawing, its rules and the windows' tops."""
    W, H = 380, 1422
    T2, T3 = 316, 632
    sc = Iso(0, 0)
    css, v = [], "n"
    a, b, c = sc.at(183, 350), sc.at(404, T2 + 208), sc.at(38, T3 + 355)
    yc, HC = 148, 176
    g = ship_dims(0, [(yc - 66, yc + 66)], short=True)
    boxes = [(f"h{v}-ct", 2, 2), (f"h{v}-ck", 142, 1)]       # the one to be unloaded first rides in front
    ease = "; animation-timing-function: cubic-bezier(.2, .7, .3, 1)"
    defs(sc, v)
    swells(sc, [(250, 150, 70), (20, 470, 60), (290, 760, 60), (250, 1096, 80)])
    waves(sc, [(300, 250), (16, 250), (330, 470), (300, 1030), (20, 1150), (300, 1404)])

    strip(a, -282, -60, -220, 400)
    road(a, -132, -80, -220, 400)
    station(sc, 1)
    office(a, -257, 56)
    end(sc)
    truck(a, v, "a", 0, boxes)
    at_station(css, 1, f"{v}-trucka", "hn-trucka", D1, [(0, f"transform: {along_y(-420)}"), (.9, f"transform: {along_y(-420)}{ease}"), (1.95, "transform: none"), (D1, "transform: none")])

    strip(b, -190, -30, -470, 130)
    road(b, -132, -80, -470, 130)
    station(sc, 2)
    pivot = gate_back(b, v, 0)
    end(sc)
    truck(b, v, "b", -22 - TRUCK, boxes)
    at_station(css, 2, f"{v}-truckb", "hn-truckb", D2, [(0, f"transform: {along_y(-60)}{ease}"), (.4, "transform: none"), (1.4, "transform: none; animation-timing-function: ease-in"),
                                                        (2.25, f"opacity: 1; transform: {along_y(420)}"), (D2, f"opacity: 0; transform: {along_y(470)}")])
    station(sc, 2)
    scan(b, v, 1, -22 - TRUCK + 142 + 132)
    scan(b, v, 2, -22 - TRUCK + 2 + 132)
    gate_front(b, 0)
    customs(css, v, pivot, order=(1, 2))
    end(sc)

    strip(c, -146, 0, -150, 440)
    road(c, -132, -80, -150, 440)
    truck(c, v, "c", yc - 66 - 142, boxes)
    (sk, st_), fall, drops = afloat(c, css, v, g, (yc, yc), HC, [], on_top=True)
    unload(css, v, "c", fall, drops, advance=140, fade=True)

    station(sc, 5)
    ik, it = sc.at(10, 1208, .72), sc.at(106, 1300, .72)
    stern = c.P(57, -34, WZ)
    mark = len(sc.out)
    jk, _, _ = island(ik, CARGO_K)
    jt, _, at = island(it, "teal", parcels=2)
    islands = sc.out[mark:]
    del sc.out[mark:]
    # one line calls at both piers: from the stern to the first island, and on to the second
    rk = route(sc, [stern, (-10, stern[1] + 90), (jk[0] - 4, jk[1] + 4)])
    rt = route(sc, [(jk[0] - 4, jk[1] + 4), (jk[0] + 10, jt[1] - 30), (jt[0] - 6, jt[1] + 2)])
    sc.out.extend(islands)
    sailing(sc, css, v, "k", CARGO_K, rk, (.84, .56, .28), sk)
    sailing(sc, css, v, "t", "teal", rt, (.74, .3), st_)
    end(sc)

    pin(sc, 1, "Inventory", 262, 8, a.P(-209, 190, 99))
    pin(sc, 2, "Verify", 124, T2 + 8, b.P(-166, 5, GATE[0] + GATE[1]))
    pin(sc, 3, "Fetch", 270, T3 + 14, c.P(118, yc, HC + 8))
    pin(sc, 4, "Generators", 252, T3 + 376, c.P(100, 156, -17))
    pin(sc, 5, "Output", 6, 1116, rk(.62))
    station(sc, 5)
    tag(sc, 180, 1112, NAME_K, PATH_K, ik.P(96, 178, 0), narrow=True)
    tag(sc, 4, 1372, NAME_T, PATH_T, at, narrow=True)
    end(sc)
    # CAT-67i: each window holds its station's object whole, with its pill: the office (y 2 to 242), the gate with its
    # shield (317 to 504), the crane (643 to 958), the ship (811 to 1056) and the islands with their labels (1112 to 1418).
    tops = [0, T2 - 16, T3 + 10, T3 + 110, H - BAND]
    for i, top in enumerate(tops):   # the selected station's window: the drawing moves up behind its frame, by a share of its own height
        css.append(f'.harbour.live .scene-frame[data-at="{i + 1}"]:not(.whole) .scene-narrow {{ transform: translateY({-100 * top / H:.3f}%); }}')
    return svg("narrow", W, H, sc, ref="hn"), css, tops


# ---------------------------------------------------------------- spot drawings for the inner pages

def pad(sc, foot):
    """A piece of quay standing in the water."""
    sc.poly("shade", [(x + 3, y - 12, WZ) for x, y in foot])
    sc.slab("land", foot, WZ, 0, foam=True)


def use(sc, ref, fam, x, y, z=0):
    """A shape drawn once at the origin in the v family, placed again in the colours of fam."""
    px, py = sc.P(x, y, z)
    sc.raw(f'<use href="#{ref}" class="fam-{fam}" transform="translate({n(px)} {n(py)})"/>')


BEAM = 46   # how far the lighthouse's beam reaches


def ring(sc, cls, x, y, z, r):
    """A circle lying level, as the projection shows it."""
    px, py = sc.P(x, y, z)
    k = r * 2 ** -.5
    for dx, dy in ((k, k), (-k, -k), (k, -k), (-k, k)):
        sc.P(x + dx, y + dy, z)
    sc.raw(f'<ellipse class="{cls}" cx="{n(px)}" cy="{n(py)}" rx="{n(2 * k * C)}" ry="{n(2 * k * S)}"/>')


def prow(sc, fam, x0, x1, y0, tip, z0, z1):
    """The pointed end of a hull towards the viewer: two flanks that meet at the stem, and the deck between them."""
    xm = (x0 + x1) / 2
    sc.poly(f"{fam}-l", [(x0, y0, z0), (xm, tip, z0), (xm, tip, z1), (x0, y0, z1)])
    sc.poly(f"{fam}-r", [(xm, tip, z0), (x1, y0, z0), (x1, y0, z1), (xm, tip, z1)])
    sc.poly(f"{fam}-t", [(x0, y0, z1), (x1, y0, z1), (xm, tip, z1)])


def spots():
    """One small drawing per section of the site, each with a motif of its own and without text: a container stack on a quay
    corner for the catalog, one sealed container for a generator, a lighthouse for a guide, three containers lashed
    into one load for a recipe. Light and palette are the scene's. Each drawing takes its frame from what it draws.
    A barge with stacks stands for the stacks, a basin with a model ship for the playground, a signal mast for the
    blog, a pilot boat for the quickstart, a mooring bollard for pages that explain, a tide gauge for reference pages.
    Each has one part that moves once when its page loads (style.css): the top container is set down, a scan runs
    over the container and its seal comes on, the light goes round, the lashings are pulled tight, the barge glides
    in, the model leaves its slipway, the flags run up, the boat casts off, the loop drops over the bollard, the
    gauge's float bobs."""
    out = {}
    # catalog: three containers stacked on the corner of a quay
    sc = Iso(52, 172)
    pad(sc, [(-14, -22), (-14, 118), (112, 118), (112, 44), (76, 44), (76, -22)])
    sc.line("ln land-s", [(69, -22, 0), (69, 51, 0), (112, 51, 0)])
    bollard(sc, 92, 60)
    bollard(sc, 62, -8)
    sc.raw('<defs><g id="sp-box">')
    container(Iso(0, 0, sc.out), "v", 0, 0, 0, None, L=92, W=36, H=32)
    sc.raw("</g></defs>")
    for fam, x, y, z in (("ind", -4, 14, 0), ("teal", 34, 2, 0), ("wht", 14, 8, 32)):
        if z == 0:
            sc.shade(x, x + 36, y, 32)
        else:
            sc.raw('<g class="set">')
        use(sc, "sp-box", fam, x, y, z)
        sc.P(x, y + 92, z + 32)                # the frame counts what a placed box reaches: here its far top corner
        seal(sc, x + 36, y + 12, z + 23)
        if z:
            sc.raw("</g>")
    out["catalog"] = sc
    # generator: one container on its bearers, sealed across the doors
    sc = Iso(70, 148)
    pad(sc, [(-22, -24), (-22, 132), (62, 132), (62, -24)])
    sc.shade(0, 44, 0, 44)
    for y in (12, 96):
        sc.box("hull", -2, 46, y, y + 8, 0, 4)
    container(sc, "ind", 0, 0, 4, None, L=116, W=44, H=40)
    sc.raw('<g class="sweep">')                # the scan, drawn at the far end
    sc.right("or-t", 44, 104, 116, 4, 44)
    sc.top("or-t", 0, 44, 104, 116, 44)
    sc.raw('</g><g class="seal">')
    sc.line("ln or-ls", [(3, 0, 23), (41, 0, 23)])
    sc.disc_l("or-r", 22, 0, 23, 10)
    tick(sc, "light-s", 22, 0, 23)
    sc.raw("</g>")
    out["generator"] = sc
    # guide: a lighthouse on its rock, with the keeper's house
    sc = Iso(80, 196)
    pad(sc, [(-24, -6), (-24, 86), (10, 86), (10, 104), (70, 104), (70, 20), (48, 20), (48, -6)])
    sc.slab("land", [(-10, 30), (-10, 78), (34, 78), (34, 30)], 0, 7)
    sc.raw('<g transform="translate(0 -7)">')
    sc.shade(-2, 26, 40, 110, k=.3)
    sc.frustum("wht", 12, 54, 13, 8.5, 0, 96)
    sc.frustum("hull", 12, 54, 12, 11, 20, 38)
    sc.frustum("hull", 12, 54, 10.1, 9.2, 58, 76)
    sc.left("hull-l", 41, 8, 16, 0, 15)
    sc.box("hull", 0, 24, 42, 66, 96, 100)
    lx, ly = sc.P(12, 54, 107)
    # the beam lies in the lantern's level plane: drawn flat and projected, so that turning it there is a turn round the tower
    sc.raw(f'<g transform="matrix({C:.3f} {S} {C:.3f} -{S} {n(lx)} {n(ly)})"><path class="beam" d="M0 0L{BEAM}-8V8zM0 0L-{BEAM}-8V8z"/></g>'
           f'<circle class="halo" cx="{n(lx)}" cy="{n(ly)}" r="17"/>')
    sc.box("teal", 5, 19, 47, 61, 100, 114)
    sc.left("light", 47, 8, 16, 103, 111)
    sc.right("light", 19, 50, 58, 103, 111)
    sc.poly("hull-l", [(3, 45, 114), (21, 45, 114), (12, 54, 130)])
    sc.poly("hull-r", [(21, 45, 114), (21, 63, 114), (12, 54, 130)])
    sc.raw("</g>")
    sc.raw('<g class="rays">')
    for dx in (-1, 1):                         # the light, as three rays to either side
        for dz in (-9, 0, 9):
            a = sc.P(12, 54, 114)
            sc.raw(f'<path class="ln foam-s" d="M{n(a[0] + dx * 22)} {n(a[1] + dz * .4)}l{n(dx * 26)} {n(dz * 1.1)}"/>')
    sc.raw("</g>")
    sc.shade(40, 62, 30, 22)
    sc.box("ind", 40, 62, 30, 66, 0, 20)
    sc.right("hull-r", 62, 36, 46, 0, 14)
    sc.right("light", 62, 52, 61, 7, 14)
    sc.box("hull", 38, 64, 28, 68, 20, 23)
    tree(sc, -12, 12, .9)
    sc.bb[1] -= 7                              # the tower stands 7 higher than it is projected
    assert ly - 7 - BEAM * 2 ** .5 * S > sc.bb[1] - 12, "the beam turns inside the frame's margin"
    out["guide"] = sc
    # recipe: three shipping containers lashed into one load, two on the ground and one across them
    sc = Iso(0, 0)
    pad(sc, [(-18, -18), (-18, 112), (98, 112), (98, -18)])
    for fam, x, z in (("ind", 0, 0), ("ind", 42, 0), ("teal", 21, 30)):
        if z == 0:
            sc.shade(x, x + 36, 0, 30)
        else:
            sc.raw('<g class="press">')
        container(sc, fam, x, 0, z, None, L=92, W=36, H=30)
        if z:
            sc.raw("</g>")
    sc.raw('<g class="lash">')
    for y in (24, 68):                         # a lashing over the load, down to the ground on the near side
        sc.line("ln or-ls", [(21, y, 60), (57, y, 60), (57, y, 30), (78, y, 30), (78, y, 0)])
    sc.raw("</g>")
    for y in (24, 68):
        sc.box("hull", 76, 82, y - 3, y + 3, 0, 3)
    out["recipe"] = sc
    # stacks: a barge with container stacks, afloat; it glides in and settles
    sc = Iso(0, 0)
    sc.raw('<defs><g id="sp-load">')
    container(Iso(0, 0, sc.out), "v", 0, 0, 0, None, L=40, W=20, H=16)
    sc.raw('</g></defs><g class="glide"><g class="trail">')    # what it leaves behind while it moves; not part of the frame
    wake = Iso(0, 0, sc.out)
    wake.line("ln foam-s", [(8, -8, 0), (2, -34, 0)])
    wake.line("ln foam-s", [(48, -8, 0), (54, -34, 0)])
    foam(wake, [(28, -14, 7), (22, -30, 5), (36, -40, 4)], z=0)
    sc.raw("</g>")
    sc.poly("shade-water", [(4, -12, 0), (60, -12, 0), (60, 150, 0), (4, 150, 0)])
    sc.box("hull", 0, 56, 0, 160, 0, 8)
    sc.line("ln foam-s", [(0, 0, 0), (56, 0, 0), (56, 160, 0)])
    sc.box("wht", 8, 30, 5, 21, 8, 24)          # the deckhouse at the stern
    sc.left("hull-l", 5, 12, 26, 14, 20)
    sc.right("hull-r", 30, 8, 18, 14, 20)
    sc.box("hull", 6, 32, 3, 23, 24, 26)
    fams = ("ind", "teal", "wht", "kub")
    for k, (y, heights) in enumerate(((118, (2, 2)), (74, (1, 2)), (30, (2, 1)))):   # the bay farthest from the viewer first
        for row, x in enumerate((5, 31)):
            for level in range(heights[row]):
                use(sc, "sp-load", fams[(k + 2 * row + level) % 4], x, y, 8 + 16 * level)
    sc.P(5, 158, 40)                           # the frame counts the far stack's top
    sc.P(51, 158, 8)
    sc.raw("</g>")
    out["barge"] = sc
    # playground: a training basin with a model ship that has just left its slipway
    sc = Iso(0, 0)
    sc.poly("shade", [(x + 3, y - 12, WZ) for x, y in ((0, 0), (0, 126), (120, 126), (120, 0))])
    sc.slab("land", [(0, 0), (0, 126), (120, 126), (120, 88), (22, 88), (22, 0)], WZ, 0, foam=True)
    sc.poly("road-t", [(42, 88, 0), (78, 88, 0), (78, 50, WZ), (42, 50, WZ)])          # the slipway and its two rails
    sc.poly("land-r", [(78, 88, 0), (78, 50, WZ), (78, 88, WZ)])
    for x in (51, 69):
        sc.line("ln land-s", [(x, 88, 0), (x, 50, WZ)])
    sc.raw('<g class="ripple">')
    ring(sc, "ln foam-s", 60, 16, WZ, 30)
    sc.raw('</g><g class="launch">')
    sc.box("kub", 46, 74, 4, 36, WZ, WZ + 13)
    prow(sc, "kub", 46, 74, 4, -14, WZ, WZ + 13)
    sc.box("wht", 51, 69, 14, 32, WZ + 13, WZ + 26)
    sc.left("hull-l", 14, 54, 66, WZ + 17, WZ + 23)
    sc.right("hull-r", 69, 17, 29, WZ + 17, WZ + 23)
    sc.box("teal", 56, 64, 19, 27, WZ + 26, WZ + 35)
    sc.raw("</g>")
    sc.slab("land", [(98, 0), (98, 88), (120, 88), (120, 0)], WZ, 0, foam=True)           # the near wall of the basin, in front of what floats in it
    bollard(sc, 109, 18)
    bollard(sc, 11, 18)
    tree(sc, 14, 110, .9)
    out["basin"] = sc
    # blog: a signal mast beside its hut; the flags run up
    sc = Iso(0, 0)
    pad(sc, [(-24, -24), (-24, 84), (80, 84), (80, -24)])
    sc.shade(-18, 6, 14, 22)
    sc.box("ind", -18, 6, 14, 44, 0, 22)
    sc.left("hull-l", 14, -10, 0, 0, 15)
    sc.right("light", 6, 22, 38, 8, 16)
    sc.box("hull", -20, 8, 12, 46, 22, 25)
    sc.shade(42, 46, 8, 60, k=.3)
    sc.box("hull", 38, 50, 4, 16, 0, 5)
    sc.box("hull", 42, 46, 8, 12, 5, 130)
    sc.box("hull", 12, 76, 9, 11, 100, 103)                                              # the yard
    sc.box("wht", 41, 47, 7, 13, 130, 135)
    for x in (14, 74):                                                                   # a halyard from each end of the yard
        sc.line("ln hull-s", [(x, 10, 100), (x, 10, 2)])
    for i, (tone, z) in enumerate((("teal-r", 79), ("or-r", 60), ("kub-r", 41))):
        sc.raw(f'<g class="flag flag-{i + 1}">')
        sc.left(tone, 10, 74, 100, z, z + 17)
        sc.raw("</g>")
    sc.raw('<g class="flag flag-4">')
    sc.poly("hull-r", [(14, 10, 94), (14, 10, 76), (-14, 10, 85)])
    sc.raw("</g>")
    out["mast"] = sc
    # quickstart: a pilot boat that has cast off from the pier
    sc = Iso(0, 0)
    pad(sc, [(0, 30), (0, 150), (30, 150), (30, 30)])
    bollard(sc, 22, 44)
    bollard(sc, 22, 104)
    lamp(sc, 8, 132, 34)
    sc.raw('<g class="churn">')
    sc.line("ln foam-s", [(52, 92, WZ), (44, 122, WZ)])
    sc.line("ln foam-s", [(74, 92, WZ), (84, 122, WZ)])
    foam(sc, [(63, 96, 8), (58, 110, 6), (70, 120, 5), (62, 132, 4)])
    sc.raw('</g><g class="cast">')
    sc.poly("shade-water", [(54, 26, WZ), (80, 26, WZ), (80, 88, WZ), (54, 88, WZ)])
    sc.box("hull", 50, 76, 40, 90, WZ, WZ + 9)
    prow(sc, "hull", 50, 76, 40, 18, WZ, WZ + 9)
    sc.line("ln or-ls", [(63, 18, WZ + 5), (76, 40, WZ + 5), (76, 90, WZ + 5)])
    sc.box("wht", 54, 72, 52, 76, WZ + 9, WZ + 23)
    sc.left("hull-l", 52, 57, 69, WZ + 14, WZ + 20)
    sc.right("hull-r", 72, 55, 73, WZ + 14, WZ + 20)
    sc.box("hull", 52, 74, 50, 78, WZ + 23, WZ + 25)
    sc.line("ln hull-s", [(63, 66, WZ + 25), (63, 66, WZ + 38)])
    sc.box("teal", 61, 65, 64, 68, WZ + 38, WZ + 42)
    sc.raw("</g>")
    out["pilot"] = sc
    # documentation: a mooring bollard on the quay's edge; the line's loop drops over it
    sc = Iso(0, 0)
    pad(sc, [(-34, -30), (-34, 74), (70, 74), (70, -30)])
    sc.shade(4, 36, 4, 30)
    sc.box("hull", 4, 36, 4, 36, 0, 5)
    cx, cy = sc.P(20, 20, 16)
    rx, ry = 15 * 2 ** .5 * C, 15 * 2 ** .5 * S
    sc.raw(f'<path class="ln or-ls loop" d="M{n(cx - rx)} {n(cy)}A{n(rx)} {n(ry)} 0 0 1 {n(cx + rx)} {n(cy)}"/>')
    sc.frustum("hull", 20, 20, 10, 8, 5, 34)
    sc.box("hull", 6, 34, 6, 34, 34, 43)
    sc.raw(f'<path class="ln or-ls loop" d="M{n(cx - rx)} {n(cy)}A{n(rx)} {n(ry)} 0 0 0 {n(cx + rx)} {n(cy)}"/>')
    e, w = sc.P(70, 8, 1), sc.P(104, -14, WZ)
    sc.raw(f'<path class="ln or-ls rope" d="M{n(cx + rx)} {n(cy)}Q{n((cx + rx + e[0]) / 2)} {n(e[1] + 7)} {n(e[0])} {n(e[1])}Q{n(e[0] + 8)} {n(e[1] + 22)} {n(w[0])} {n(w[1])}"/>')
    for y in (-12, 56):
        bollard(sc, 58, y)
    out["bollard"] = sc
    # reference: a tide gauge at the quay, and its float, which bobs once
    sc = Iso(0, 0)
    pad(sc, [(-10, 6), (-10, 96), (46, 96), (46, 6)])
    sc.shade(8, 30, 40, 18)
    sc.box("ind", 8, 30, 40, 70, 0, 18)                                                  # the gauge hut
    sc.right("light", 30, 48, 62, 6, 13)
    sc.box("hull", 6, 32, 38, 72, 18, 21)
    sc.line("ln hull-s", [(30, 32, 10), (58, 32, 10)])                                   # the arm that holds the staff
    for i in range(7):                                                                   # the staff, banded
        sc.box("wht" if i % 2 else "hull", 56, 64, 28, 36, WZ + 8 * i, WZ + 8 * i + 8)
    sc.box("teal", 54, 66, 26, 38, WZ + 56, WZ + 60)
    sc.raw('<g class="ripple">')
    ring(sc, "ln foam-s", 92, 12, WZ, 17)
    sc.raw('</g><g class="bob">')
    sc.frustum("teal", 92, 12, 9, 7, WZ, WZ + 9)
    sc.frustum("wht", 92, 12, 6, 2, WZ + 9, WZ + 22)
    sc.line("ln hull-s", [(92, 12, WZ + 22), (92, 12, WZ + 34)])
    sc.box("or", 89, 95, 9, 15, WZ + 34, WZ + 40)
    sc.raw("</g>")
    out["gauge"] = sc
    return out


def main():
    part = SITE / "layouts" / "_partials"
    note = "{{/* Written by catalog/harbour_scene.py. */}}\n"
    art, css = wide()
    (part / "harbour-wide.html").write_text(note + art + "\n")
    art2, css2, tops = narrow()
    (part / "harbour-narrow.html").write_text(note + art2 + "\n")
    css += css2
    # one station's window into the vertical drawing, for the list a phone shows without JavaScript or with reduced motion
    crops = "".join(f'{{{{ {"if" if i == 0 else "else if"} eq . {i + 1} }}}}<svg class="sc crop" viewBox="0 {top} 380 {BAND}" aria-hidden="true"><use href="#hn"/></svg>'
                    for i, top in enumerate(tops))
    (part / "harbour-crop.html").write_text("{{/* Written by catalog/harbour_scene.py. Argument: the station's number. */}}\n" + crops + "{{ end }}\n")
    parts = []
    for name, sc in spots().items():
        x0, y0, x1, y1 = sc.bb   # the frame: what was drawn, with a margin for the shadow on the water and for strokes
        drawing = f'<svg class="sc spot" viewBox="{n(x0 - 12)} {n(y0 - 12)} {n(x1 - x0 + 24)} {n(y1 - y0 + 24)}" aria-hidden="true">' + prefixed("".join(sc.out)) + "</svg>"
        assert not re.search(r"<style|<script|<text| (style|fill|stroke|on[a-z]+)=", drawing), name
        parts.append(f'{{{{ {"if" if not parts else "else if"} eq . "{name}" }}}}{drawing}')
        print(len(drawing), "bytes", name)
    (part / "spot.html").write_text("{{/* Written by catalog/harbour_scene.py. One small drawing per page type; argument: its name. */}}\n" + "".join(parts) + "{{ end }}\n")
    for drawing in (art, art2):   # what the page's CSP and the one stylesheet require of both drawings
        assert not re.search(r"<style|<script| (style|fill|stroke|on[a-z]+)=", drawing), "colours and behaviour belong to style.css and site.js"
        ids = re.findall(r' id="([^"]+)"', drawing)
        assert ids in (["hw-ck", "hw-ct"], ["hn", "hn-ck", "hn-ct"]), ids   # the two containers, and the vertical drawing for the phone's crops
        for label in (">kadet-hub<", ">Kapitan<", ">kubernetes<", ">terraform-aws<", f">{NAME_K}<", f">{NAME_T}<", f">{PATH_K}<", f">{PATH_T}<"):
            assert drawing.count(label) == (2 if label in (">kubernetes<", ">terraform-aws<") else 1), label   # on its container and on the cargo list
        assert not any(c.isdigit() for label in drawing.split('class="h-tx-plate"')[1:] for c in label[label.index(">") + 1:label.index("<")]), "plates carry names only"
    print(len(art2), "bytes narrow")
    sheet = SITE / "static" / "style.css"
    text = sheet.read_text()
    a, b = "/* harbour-keyframes:start */", "/* harbour-keyframes:end */"
    text = text[:text.index(a) + len(a)] + "\n" + "\n".join(css) + "\n" + text[text.index(b):]
    sheet.write_text(text)
    print(len(art), "bytes wide")


if __name__ == "__main__":
    main()
