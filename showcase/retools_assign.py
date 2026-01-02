from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from retools import Builder


# Example 1: constants produce a full object from a single word.
people = Builder()


@people.reclass(
    r"(?:John<name=John><height=180><weight=75>|Mary<name=Mary><height=165><weight=54>)"
)
@dataclass
class Person:
    name: str
    height: int
    weight: int


for text in ("John", "Mary"):
    person = people.construct(Person, text)
    print(f"person from {text!r} = {person!r}")


# Example 2: built-in type assignments.
defaults = Builder()


@defaults.reclass(
    r"preset"
    r"<flag=true><count=42><ratio=3.5><amount=12.50>"
    r"<born=1990-05-12><login=2026-01-02 03:04:05>"
    r"<alarm=07:30:00><uid=123e4567-e89b-12d3-a456-426614174000>"
    r"<note=hello>"
)
@dataclass
class BuiltinDefaults:
    flag: bool
    count: int
    ratio: float
    amount: Decimal
    born: date
    login: datetime
    alarm: time
    uid: UUID
    note: str


m = defaults.match("<BuiltinDefaults>", "preset")
print(f"builtin preset = {m.get(BuiltinDefaults) if m else None!r}")


# Example 3: overriding field regex changes which assignments are accepted.
travel = Builder()
billing = Builder()


@dataclass
class Direction:
    direction: str


travel.reclass(
    Direction,
    r"(?:go<direction=to>|drop<direction=down to>)",
    fields=dict(direction=r"to|down to"),
)

billing.reclass(
    Direction,
    r"(go<direction=up>|drop<direction=down>)",
    fields=dict(direction=r"up|down"),
)

for label, engine in (("travel", travel), ("billing", billing)):
    direction = engine.construct(Direction, "go")
    print(f"{label} go => {direction!r}")


# Example 4: escaping '>' inside constant assignments.
escape = Builder()


@escape.reclass(r"literal<text=3 \> 2>")
@dataclass
class Note:
    text: str


m = escape.match("<Note>", "literal")
print(f"escaped note = {m.get(Note) if m else None!r}")


# Example 5: conditional assignments in a single pattern.
orders = Builder()


@orders.reclass(r"order <id> (shipped<status=shipped>|cancelled<status=cancelled>)")
@dataclass
class Order:
    id: int
    status: str


for text in ("order 10 shipped", "order 11 cancelled"):
    m = orders.match("<Order>", text)
    order = m.get(Order) if m else None
    print(f"order from {text!r} = {order!r}")


# Example 6: assignments can build nested dataclasses too.
nested = Builder()


@nested.reclass(r"<x>,<y>")
@dataclass
class Point:
    x: int
    y: int


@nested.reclass(r"box<origin=1,2>")
@dataclass
class Box:
    origin: Point


m = nested.match("<Box>", "box")
print(f"box = {m.get(Box) if m else None!r}")
