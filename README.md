# retools

Composable, typed regular expressions built from dataclasses.

`retools` lets you register a dataclass as a reusable regex token and then
compose larger expressions from those tokens. Matched groups are converted
into typed dataclass instances, including nested dataclasses.

## Install

```bash
pip install git+https://github.com/jihghong/retools
```

## Quickstart

```python
from dataclasses import dataclass
from retools import reclass

@reclass(
    r"<year>-<month>-<date>|<year>/<month>/<date>",
    fields=dict(
        year=r"\d{4}",
        month=r"\d{2}",
        date=r"\d{2}",
    ),
    token="DATE",
)
@dataclass
class Date:
    year: int
    month: int
    date: int

@reclass(fields=dict(direction=r"to|down to"))
@dataclass
class To:
    direction: str

rx = reclass.compile(r"<DATE> <To> <DATE>")
m = rx.match("2025-12-29 to 2026/01/01")
if m:
    date1 = m.get(Date)
    direction = m.get(To)
    date2 = m.get(Date, 2)
    print(date1, direction, date2)

m = reclass.match(r"<DATE> <To> <DATE>", "2026-01-01 down to 2025/12/29")
if m:
    print(m.get(To))
```

## Placeholder syntax

- `<TOKEN>` expands to a registered token's regex.
- If you omit `token=...`, the token name defaults to the class name (e.g., `<Date>`).
- Token names are case-sensitive.
- `<field>` expands to the field pattern inside a dataclass regex template.
- `<field=value>` assigns a constant to the field without consuming input. The value is
  validated against the field regex and converted with the field's converter.
- Escape `>` as `\>` inside `<field=value>` when you need a literal `>`.
- Only known tokens/fields are expanded. Unknown placeholders are left as-is.
- Placeholders can take regex qualifiers (e.g., `<Date>{1,3}`)

## Assignment placeholders

`<field=value>` assigns a constant without consuming any input. The value is validated
against the field regex (including `fields=...` overrides) and converted using the same
converter as normal matches. If the value does not match the field regex, the assigned
value becomes `None`.

Use this to build full objects from a literal token, or to set flags based on which
branch matched:

```python
@reclass(r"(?:John<name=John><height=180>|Mary<name=Mary><height=165>)")
@dataclass
class Person:
    name: str
    height: int

@reclass(r"order <id> (shipped<status=shipped>|cancelled<status=cancelled>)")
@dataclass
class Order:
    id: int
    status: str

m = reclass.match("<Person>", "Mary")
print(m.get(Person))  # Person(name='Mary', height=165)
```

Constants also use built-in converters and can target nested dataclasses:

```python
@reclass(r"preset<flag=true><count=42><when=2026-01-02 03:04:05>")
@dataclass
class Preset:
    flag: bool
    count: int
    when: datetime

@reclass(r"<x>,<y>")
@dataclass
class Point:
    x: int
    y: int

@reclass(r"box<origin=1,2>")
@dataclass
class Box:
    origin: Point
```

Escape `>` inside a constant with `\>` (e.g., `<text=3 \> 2>`).

## Default field patterns

You can omit `fields` when a dataclass field type has a built-in pattern.
These defaults also enable automatic conversion back to typed values.

Built-in defaults:

- `bool` -> `(?i:true|false|1|0)`
- `int` -> `-?\d+`
- `float` -> `-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?`
- `Decimal` -> `-?(?:\d+(?:\.\d*)?|\.\d+)`
- `datetime.date` -> `\d{4}-\d{2}-\d{2}`
- `datetime.datetime` -> `\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?`
- `datetime.time` -> `\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?`
- `UUID` -> `[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}`
- `str` -> `.+?`

If you provide `fields=...`, your patterns override the defaults.

## Multiple builders

Use `Builder()` when you want isolated registries with different grammars.

```python
from retools import Builder

travel = Builder()
billing = Builder()

travel.reclass(Date, r"<year>/<month>/<date>")
billing.reclass(Date, r"<year>-<month>-<date>")

m = travel.match(r"depart on <Date>", "depart on 2025/06/01")
if m:
    print(m.get(Date))
```

## Nested dataclasses

If a field type is another registered dataclass, it will be inferred using its token.

```python
@reclass(
    r"<from_date>\s+<To>\s+<to_date>",
)
@dataclass
class Period:
    from_date: Date
    to_date: Date
```

You can then compose it in larger patterns:

```python
vacation_rx = reclass.compile(
    r"summer vacation is <Period> and winter vacation is <Period>"
)
```

## List fields

`list[T]` fields are supported. By default, items are separated by commas
(`\s*,\s*`). When the list segment is present but empty, it becomes `[]`.
If the list segment is missing entirely, the field is `None` (when optional).

Use `repeat(...)` to customize separators or provide an empty literal:

```python
from retools import Builder, reclass, repeat

@reclass(r"^<subject>(?:\s+dates\s*=\s*\[<dates>\])?$")
@dataclass
class Schedule:
    subject: str
    dates: list[Date] | None

calendar = Builder()
calendar.reclass(
    Date,
    r"<year>-<month>-<date>|<year>/<month>/<date>",
    fields=dict(year=r"\d{4}", month=r"\d{2}", date=r"\d{2}"),
)
calendar.reclass(
    Schedule,
    r"^<subject>:\s*<dates>$",
    fields=dict(dates=repeat(empty=r"TBD")),
)
```

## Inheritance and polymorphism

If you register a base dataclass and its subclasses, `<Base>` will match any
registered subclass of `Base` (polymorphism). Use `<Subclass>` to match a
specific subclass.

```python
@reclass(r"<x>, <y>")
@dataclass
class Pair:
    x: int
    y: int

@reclass(r"x=<x>, y=<y>")
@dataclass
class Coordinate(Pair):
    pass

@reclass(r"<x> \+ <y> i")
@dataclass
class Complex(Pair):
    pass

m = reclass.match(r"<Pair>", "x=1, y=2")
if m:
    print(m.get(Pair))  # Coordinate(...)

m = reclass.match(r"<Pair>", "1 + 2 i")
if m:
    print(m.get(Pair))  # Complex(...)
```

## Optional segments

Optional tokens work as expected; when a token is missing entirely, `get()`
returns `None` if the target dataclass is wrapped in an optional segment.

```python
@reclass(
    r"order <order_id> shipped <shipped_at>(?: delivered <delivered_at>)?",
)
@dataclass
class Delivery:
    order_id: int
    shipped_at: datetime
    delivered_at: Optional[datetime]
```

## API

`reclass` is the default `Builder` instance.

`reclass(regex=None, *, fields=None, token=None)` registers a dataclass.

- `regex`: template for the dataclass, using `<field>` placeholders.
- `fields`: mapping of field name to regex (optional for supported types).
- `token`: placeholder name used in other patterns (defaults to the class name).
- `repeat(sep=..., required=False, empty=...)` customizes list fields.
- `reclass(...).fields(...)` is shorthand for `fields=dict(...)`.
- `reclass(...).token("NAME")` overrides the default token name.

`reclass.compile(pattern, flags=0)` returns a compiled matcher. You can also pass
the class directly (e.g., `reclass.compile(Date)`), which is shorthand for
`reclass.compile("<Date>")`.

- `match(text)` returns a match object (or `None`).
- The match object has `get(Class, index=1)` which returns the Nth occurrence.

`reclass.match(pattern, text, flags=0)` is a convenience that compiles (with
cache) and matches in one call.

`reclass.construct(Class, text, flags=0)` matches `<Class>` and returns the
constructed object (or `None`).
When a matcher is compiled from a class (or a single-token pattern), the compiled matcher
also provides `construct(text)` which returns the constructed object (or `None`).

## Chained syntax

You can also chain helpers on the decorator:

```python
@reclass(r"<subject>:\s*<dates>").fields(dates=repeat(empty='TBD')).token("SCHEDULE")
@dataclass
class Schedule:
    subject: str
    dates: list[Date]
```

For a builder, the above code is equivalent to

```python
calendar = Builder()
calendar.reclass(r"<subject>:\s*<dates>").fields(dates=repeat(empty='TBD')).token("SCHEDULE")(Schedule)
```

## Match helpers

The match object proxies common `re.Match` helpers:

- `group(n)` for user-defined numeric groups (tokens do not shift numbering).
- `group("name")` for named groups.
- `groups()` and `groupdict()` for user groups in the pattern.
- `start()`, `end()`, `span()`, `expand()`, plus `match`, `re`, `string`.
