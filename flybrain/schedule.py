"""When a fly's sessions run.

A daily fly decides at 15:30 New York time on weekdays. The day's candle is
nearly complete and an order still fills before the close. An "<N>h" fly
decides at the top of every Nth hour UTC, weekends too.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .clawstreet import stock_market_open
from .config import FlyConfig, home


def slot(cadence: str, now: datetime) -> str | None:
    """The session slot `now` is in, or None when no session is due.

    For an hourly cadence the whole hour counts. A run that failed on the
    hour gets another try later in the same hour.
    """
    if cadence.endswith("h"):
        utc = now.astimezone(timezone.utc)
        return utc.strftime("%Y-%m-%dT%H") if utc.hour % int(cadence[:-1]) == 0 else None
    ny = now.astimezone(ZoneInfo("America/New_York"))
    return ny.strftime("%Y-%m-%d") if ny.weekday() < 5 and ny.hour == 15 and ny.minute >= 30 else None


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
