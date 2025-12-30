from dataclasses import dataclass

from retools import reclass

@reclass(r'<x>, <y>')
@dataclass
class Pair:
    x: int
    y: int

@reclass(r"x=<x>, y=<y>")
@dataclass
class Coordinate(Pair):
    pass

@reclass(r"<Coordinate>, z=<z>")
@dataclass
class Point3D(Coordinate):
    z: int

m = reclass.match(r"<Coordinate>", "x=1, y=2")
if m:
    coordinate = m.get(Pair, 1)
    print(f"{coordinate = !r}")

m = reclass.match(r"<Point3D>", "x=1, y=2, z=3")
if m:
    point = m.get(Point3D, 1)
    print(f"{point = !r}")

@reclass(r"<x> \+ <y>i")
@dataclass
class Complex(Pair):
    pass

rx = reclass.compile(r"<Pair>")

m = rx.match("1, 2")
if m:
    pair = m.get(Pair, 1)
    print(f"{pair = !r}")

m = rx.match("x=1, y=2")
if m:
    coordinate = m.get(Pair, 1)
    print(f"{coordinate = !r}")

m = rx.match("1 + 2i")
if m:
    complex = m.get(Pair, 1)
    print(f"{complex = !r}")
