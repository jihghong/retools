from retools import Builder, reclass
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

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

m = reclass.match(
    r"<DATE> is (my|your|his|her) birthday",
    "2011/01/01 is her birthday",
)
if m:
    birthday = m.get(Date)
    whos = m.group(1)
    print(f"{birthday = !r}, {whos = !r}")

@reclass(fields=dict(direction=r"to|down to"))
@dataclass
class To:
    direction: str

rx = reclass.compile(r"<DATE> <To> <DATE>")
m = rx.match("2025-12-29 to 2026/01/01")
if m:
    date1 = m.get(Date)
    print(f"date1 = Date({type(date1.year).__name__}({date1.year}), {type(date1.month).__name__}({date1.month}), {type(date1.date).__name__}({date1.date}))")
    direction = m.get(To)
    print(f"{direction.direction = !r}")
    date2 = m.get(Date, 2)
    print(f"date2 = Date({type(date2.year).__name__}({date2.year}), {type(date2.month).__name__}({date2.month}), {type(date2.date).__name__}({date2.date}))")

m = reclass.match(r"<DATE> <To> <DATE>", "2026-01-01 down to 2025/12/29")
if m:
    direction = m.get(To)
    print(f"{direction.direction = !r}")


@reclass(
    r"<from_date>\s+<To>\s+<to_date>",
)
@dataclass
class Period:
    from_date: Date
    to_date: Date


vacation_rx = reclass.compile(
    r"summer vacation is <Period> and winter vacation is <Period>"
)
m = vacation_rx.match(
    "summer vacation is 2025-06-01 to 2025/08/31 and winter vacation is 2025-12-20 to 2026/01/05"
)
if m:
    summer_vacation = m.get(Period)
    winter_vacation = m.get(Period, 2)
    print(f"{summer_vacation = !r}")
    print(f"{winter_vacation = !r}")


@reclass(
    (
        r"id=<id>; name=<name>; age=<age>; height=<height>; "
        r"member=<member>; balance=<balance>; born=<born>; "
        r"login=<login>; alarm=<alarm>"
    ),
)
@dataclass
class Profile:
    id: UUID
    name: str
    age: int
    height: float
    member: bool
    balance: Decimal
    born: date
    login: datetime
    alarm: time


profile_rx = reclass.compile(r"<Profile>")
profile_text = (
    "id=123e4567-e89b-12d3-a456-426614174000; name=Alice; age=35; "
    "height=1.75; member=true; balance=1234.50; born=1990-05-12; "
    "login=2025-01-02 03:04:05; alarm=07:30:00"
)
m = profile_rx.match(profile_text)
if m:
    profile = m.get(Profile)
    print(f"{profile = !r}")


@reclass(
    r"order <order_id> shipped <shipped_at>( delivered <delivered_at>)?",
)
@dataclass
class Delivery:
    order_id: int
    shipped_at: datetime
    delivered_at: datetime | None


delivery_rx = reclass.compile(r"<Delivery>")
m = delivery_rx.match("order 42 shipped 2025-01-02 03:04:05")
if m:
    delivery = m.get(Delivery)
    print(f"{delivery = !r}")

m = delivery_rx.match("order 43 shipped 2025-01-03 04:05:06 delivered 2025-01-05 07:08:09")
if m:
    delivery = m.get(Delivery)
    print(f"{delivery = !r}")

m = reclass.match(r"<Delivery> is a (?P<condition>good|damaged) (package|furniture)", 'order 44 shipped 2025-01-05 05:06:07 is a good furniture')
if m:
    delivery = m.get(Delivery)
    condition = m.group('condition')
    thing = m.group(1)
    named = m.groupdict()
    print(f"{delivery = !r}, {condition = !r}, {thing = !r}, {named = !r}")

travel = Builder()
billing = Builder()

travel.reclass(
    Date,
    r"<year>/<month>/<date>",
    fields=dict(
        year=r"\d{4}",
        month=r"\d{2}",
        date=r"\d{2}",
    ),
    token="TRAVEL_DATE",
)
travel.reclass(To, fields=dict(direction=r"to|down to"))
travel.reclass(Period, r"<from_date> <To> <to_date>", token="TRAVEL_PERIOD")

billing.reclass(
    Date,
    r"<year>-<month>-<date>",
    fields=dict(
        year=r"\d{4}",
        month=r"\d{2}",
        date=r"\d{2}",
    ),
    token="BILL_DATE",
)
billing.reclass(To, fields=dict(direction=r"to|down to"))
billing.reclass(Period, r"<from_date> <To> <to_date>", token="BILL_PERIOD")

m = travel.match(
    r"summer vacation is <TRAVEL_PERIOD>",
    "summer vacation is 2025/06/01 to 2025/08/31",
)
if m:
    trip = m.get(Period)
    print(f"{trip = !r}")

m = billing.match(
    r"summer vacation is <BILL_PERIOD>",
    "summer vacation is 2025-06-01 to 2025-08-31",
)
if m:
    trip = m.get(Period)
    print(f"{trip = !r}")

text = "Dates: 2025-01-01, 2025/02/02, and 2026-03-03."
rx = reclass.compile(r"<DATE>")
matches = rx.finditer(text)
print(f"finditer matches = {len(matches)}")
print(f"findall matches = {reclass.findall(r'<DATE>', text)}")
