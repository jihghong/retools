from dataclasses import dataclass

from retools import Builder, reclass, repeat

@reclass(r"<year>-<month>-<date>|<year>/<month>/<date>").fields(
    year=r"\d{4}",
    month=r"\d{2}",
    date=r"\d{2}",
)
@dataclass
class Date:
    year: int
    month: int
    date: int

@reclass(r"^<subject>(?:\s+dates\s*=\s*\[<dates>\])?$")
@dataclass
class Schedule:
    subject: str
    dates: list[Date] | None

calendar = Builder()
calendar.reclass(r"<year>-<month>-<date>|<year>/<month>/<date>").fields(
    year=r"\d{4}",
    month=r"\d{2}",
    date=r"\d{2}"
)(Date)

calendar.reclass(r"^<subject>:\s*<dates>$").fields(dates=repeat(empty=r"TBD"))(Schedule)

m = reclass.match(
    r"<Schedule>",
    "practice baseball dates = [2025-01-01, 2025/02/02, 2026-03-03]",
)
if m:
    schedule = m.get(Schedule)
    print(f"{schedule = !r}")

m = reclass.match(r"<Schedule>", "practice baseball dates = []")
if m:
    schedule = m.get(Schedule)
    print(f"{schedule = !r}")

m = reclass.match(r"<Schedule>", "practice baseball")
if m:
    schedule = m.get(Schedule)
    print(f"{schedule = !r}")

m = calendar.match(r"<Schedule>", "practice baseball: TBD")
if m:
    schedule = m.get(Schedule)
    print(f"{schedule = !r}")
