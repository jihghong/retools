from dataclasses import dataclass

from retools import reclass

@reclass
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
    coordinate = m.get(Pair)
    print(f"{coordinate = !r}")

m = reclass.match(r"<Point3D>", "x=1, y=2, z=3")
if m:
    point = m.get(Point3D)
    print(f"{point = !r}")

@reclass(r"<x> \+ <y>i")
@dataclass
class Complex(Pair):
    pass

rx = reclass.compile(Pair)

for item in ("x=1, y=2", "x=1, y=2, z=3", "1 + 2i"):
    pair = rx.construct(item)
    print(f"{pair = !r}")

text = "x=3, y=4; x=5, y=6, z=7; 8 + 9i"
pairs = [m.get(Pair) for m in rx.finditer(text)]
print(f"{pairs = !r}")
pairs = rx.findall(text)
print(f"{pairs = !r}")
