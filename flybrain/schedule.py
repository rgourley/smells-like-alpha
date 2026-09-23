"""When a fly's sessions run.

A daily fly decides at 15:30 New York time on weekdays. The day's candle is
nearly complete and an order still fills before the close. A stock fly can
also list its own times, "12:30,15:30": each is a session on weekdays, and a
missed one runs as soon as the machine wakes, up to the next time or the
close. An "<N>h" fly
decides once in every N-hour window of the UTC day, weekends too: at the top
of the window when the machine is awake, and as soon as it wakes when it was
asleep. A laptop that sleeps through 08:00 runs the 08:00 session at 09:40.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .clawstreet import stock_market_open
from .config import FlyConfig, home


CLOSE = "16:00"


def session_times(cadence: str) -> list[str]:
    """The New York times a stock fly decides at. "daily" is 15:30."""
    return ["15:30"] if cadence == "daily" else sorted(cadence.split(","))


def slot(cadence: str, now: datetime) -> str | None:
    """The session slot `now` is in, or None when no session is due.

    For an "<N>h" cadence the slot is the N-hour window `now` is in, named by
    the hour it starts. The whole window counts, so a run that failed, or a
    machine that was asleep, still gets its session before the next window.
    A stock fly's slot is the latest listed time that has passed today. It
    stays open until the next listed time, or the close.
    """
    if cadence.endswith("h"):
        utc, every = now.astimezone(timezone.utc), int(cadence[:-1])
        return utc.replace(hour=utc.hour - utc.hour % every).strftime("%Y-%m-%dT%H")
    ny = now.astimezone(ZoneInfo("America/New_York"))
    clock = ny.strftime("%H:%M")
    passed = [t for t in session_times(cadence) if t <= clock]
    if ny.weekday() >= 5 or not passed or clock >= CLOSE:
        return None
    return f"{ny:%Y-%m-%d}T{passed[-1]}"


def due(fly_id: str, config: FlyConfig, now: datetime) -> tuple[str | None, str]:
    """The slot to run now, or None and the reason there is nothing to run."""
    this = slot(config["cadence"], now)
    if this is None:
        return None, "not a session time"
    marker = home(fly_id) / "last_slot.txt"
    if marker.exists() and marker.read_text().strip() == this:
        return None, f"slot {this} already ran"
    if config["universe"] == "stocks" and not stock_market_open():
        return None, "the stock market is closed"
    return this, "due"


def mark_slot(fly_id: str, name: str) -> None:
    """Record that a slot ran. Call it after the session finishes, so a crash leaves the slot open."""
    home(fly_id).mkdir(parents=True, exist_ok=True)
    (home(fly_id) / "last_slot.txt").write_text(name)
