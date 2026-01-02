from dataclasses import dataclass

from retools import reclass


@reclass(
    r"^(\s*(minX\s+<minX>|maxX\s+<maxX>|minY\s+<minY>|maxY\s+<maxY>))*\s*$"
)
@dataclass
class Limit:
    minX: float | None = None
    maxX: float | None = None
    minY: float | None = None
    maxY: float | None = None


tests = [
    "minX 3",
    "minX 3 maxX 18",
    "maxX 18 minX 3",
    "minX 3 minY 80",
    "minY 80 maxY 100 maxX 18",
    "minX 3 maxY 100 maxX 18 minY 80",
    "",
    "minY 80 minX 3 maxX 18 maxY 100",
    "maxX 17 maxX 18",
    "minX 1 minX 2 maxX 3",
    "minY 50 minY 60 maxY 70 maxY 80",
]


def render(text: str) -> None:
    limit = reclass.construct(r"<Limit>", text)
    print(f"{text!r} -> {limit!r}")


for item in tests:
    render(item)
