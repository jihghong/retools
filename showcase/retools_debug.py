from dataclasses import dataclass

from retools import Builder

rules = Builder().debug()


@rules.reclass(
    r"<year>-<month>-<day>",
    fields=dict(year=r"\d{4}", month=r"\d{2}", day=r"\d{2}"),
    token="DATE",
)
@dataclass
class Date:
    year: int
    month: int
    day: int


@rules.reclass(r"<color> <item>", fields=dict(color=r"red|blue", item=r"\w+"))
@dataclass
class Paint:
    color: str
    item: str


print("case 1: token typo")
m = rules.match(r"<DATE> to <DAT>", "2025-01-01 to 2025-02-02")
print(f"{m = !r}")

print("case 2: literal punctuation")
m = rules.match(r"ship <id>: <DATE>", "ship 12 2025-01-01")
print(f"{m = !r}")

print("case 3: missing grouping for |")
m = rules.match(r"red|blue <Paint>", "blue wall")
print(f"{m = !r}")
