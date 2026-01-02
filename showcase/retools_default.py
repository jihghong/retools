from dataclasses import dataclass

from retools import reclass


@reclass(r"a = <a>")
@dataclass
class A:
    a: int
    b: str = "good"


@reclass(r"value = <value>")
@dataclass
class B:
    value: int
    note: str | None


tests = [
    ("<A>", "a = 3"),
    ("<B>", "value = 7"),
]


for pattern, text in tests:
    m = reclass.match(pattern, text)
    if not m:
        print(f"{text!r} -> no match")
        continue
    cls = {"<A>": A, "<B>": B}[pattern]
    print(f"{text!r} -> {m.get(cls)!r}")
