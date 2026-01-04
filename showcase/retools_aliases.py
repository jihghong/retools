from dataclasses import dataclass

from retools import Builder

rules = Builder()

# Builder-level alias shared across classes.
rules.aliases(
    range=r"(?:min <min>|max <max>)(?:\s+(?:min <min>|max <max>))*",
)


@rules.reclass(r"temperature <range>")
@dataclass
class TemperatureRange:
    min: int | None = None
    max: int | None = None


@rules.reclass(r"speed <range>")
@dataclass
class SpeedRange:
    min: float | None = None
    max: float | None = None


# Class-level alias overrides the builder-level one.
@rules.reclass(r"budget <range>").aliases(range=r"from <min> to <max>")
@dataclass
class BudgetRange:
    min: int
    max: int


# Different classes can define the same alias name without collisions.
@rules.reclass(r"color <pair>").aliases(pair=r"<r>,<g>,<b>")
@dataclass
class Color:
    r: int
    g: int
    b: int


@rules.reclass(r"address <pair>").aliases(pair=r"<street> / <city>").fields(
    street=r"[^/]+",
    city=r".+",
)
@dataclass
class Address:
    street: str
    city: str


tests = [
    ("temperature min 10 max 28", TemperatureRange),
    ("speed max 120.5 min 40.0", SpeedRange),
    ("budget from 100 to 300", BudgetRange),
    ("color 12,34,56", Color),
    ("address Main St / Taipei", Address)
]

for text, cls in tests:
    value = rules.construct(cls, text)
    print(f"{text!r} -> {value!r}")
