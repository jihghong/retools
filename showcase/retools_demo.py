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

@reclass(fields=dict(direction=r"to|down to"))
@dataclass
class To:
    direction: str

rx = reclass.compile(r"<DATE> <To> <DATE>")
m = rx.match("2025-12-29 to 2026/01/01")
if m:
    date1 = m.get(Date, 1)
    print(f"date1 = Date({type(date1.year).__name__}({date1.year}), {type(date1.month).__name__}({date1.month}), {type(date1.date).__name__}({date1.date}))")
    direction = m.get(To, 1)
    print(f"{direction.direction = !r}")
    date2 = m.get(Date, 2)
    print(f"date2 = Date({type(date2.year).__name__}({date2.year}), {type(date2.month).__name__}({date2.month}), {type(date2.date).__name__}({date2.date}))")

m = reclass.match(r"<DATE> <To> <DATE>", "2026-01-01 down to 2025/12/29")
if m:
    direction = m.get(To, 1)
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
    summer_vacation = m.get(Period, 1)
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
    profile = m.get(Profile, 1)
    print(f"{profile = !r}")


@reclass(
    r"order <order_id> shipped <shipped_at>(?: delivered <delivered_at>)?",
)
@dataclass
class Delivery:
    order_id: int
    shipped_at: datetime
    delivered_at: datetime | None


delivery_rx = reclass.compile(r"<Delivery>")
m = delivery_rx.match("order 42 shipped 2025-01-02 03:04:05")
if m:
    delivery = m.get(Delivery, 1)
    print(f"{delivery = !r}")
m = delivery_rx.match("order 43 shipped 2025-01-03 04:05:06 delivered 2025-01-05 07:08:09")
if m:
    delivery = m.get(Delivery, 1)
    print(f"{delivery = !r}")


@dataclass
class TripDate:
    year: int
    month: int
    date: int


@dataclass
class TripPeriod:
    from_date: TripDate
    to_date: TripDate


travel = Builder()
billing = Builder()

travel.reclass(TripDate, r"<year>/<month>/<date>")
travel.reclass(TripPeriod, r"<from_date> to <to_date>")

billing.reclass(TripDate, r"<year>-<month>-<date>")
billing.reclass(TripPeriod, r"<from_date> to <to_date>")

m = travel.match(
    r"summer vacation is <TripPeriod>",
    "summer vacation is 2025/06/01 to 2025/08/31",
)
if m:
    trip = m.get(TripPeriod, 1)
    print(f"{trip = !r}")

m = billing.match(
    r"summer vacation is <TripPeriod>",
    "summer vacation is 2025-06-01 to 2025-08-31",
)
if m:
    trip = m.get(TripPeriod, 1)
    print(f"{trip = !r}")
