"""Timestamp-safe, read-only data access to captain.db."""
import datetime as dt, sqlite3
from zoneinfo import ZoneInfo
import numpy as np

TZ = ZoneInfo("America/Toronto")
UTC = dt.timezone.utc
M1, M15, H1 = 60_000, 900_000, 3_600_000


def iso(d):
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def from_ms(ms):
    return dt.datetime.fromtimestamp(ms / 1000, UTC)


def to_ms(d):
    return int(round(d.timestamp() * 1000))


def toronto_str(ms):
    return from_ms(ms).astimezone(TZ).strftime("%Y-%m-%d %H:%M %Z")


def completed_block_cutoff(now_utc, step_min=15):
    """Most recently completed 15-minute block end (Toronto wall clock; 15m grid is identical in UTC)."""
    loc = now_utc.astimezone(TZ)
    floored = loc.replace(minute=(loc.minute // step_min) * step_min, second=0, microsecond=0)
    return floored.astimezone(UTC)


def connect_ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)


def load_bars(con, provider, symbol, timeframe, derivation, cutoff_ms, knowledge_iso, start_ms=0):
    rows = con.execute(
        "SELECT candle_start_ms, candle_end_ms, open, high, low, close, COALESCE(volume,0), received_ts FROM market_data "
        "WHERE provider=? AND instrument=? AND timeframe=? AND derivation=? AND synthetic=0 AND is_final=1 "
        "AND candle_end_ms<=? AND received_ts<=? AND candle_start_ms>=? ORDER BY candle_start_ms",
        (provider, symbol, timeframe, derivation, cutoff_ms, knowledge_iso, start_ms)).fetchall()
    if not rows:
        return {k: np.array([]) for k in ("start", "end", "o", "h", "l", "c", "v")} | {"received_max": None, "n": 0}
    a = np.array([r[:7] for r in rows], dtype=float)
    return {"start": a[:, 0].astype(np.int64), "end": a[:, 1].astype(np.int64), "o": a[:, 2], "h": a[:, 3], "l": a[:, 4],
            "c": a[:, 5], "v": a[:, 6], "received_max": max(r[7] for r in rows), "n": len(rows)}


def excluded_after_cutoff(con, provider, symbol, cutoff_ms, knowledge_iso):
    """Count of stored rows that exist but were excluded for timestamp safety (audit only)."""
    return con.execute("SELECT COUNT(*) FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND "
                       "(candle_end_ms>? OR received_ts>?)", (provider, symbol, cutoff_ms, knowledge_iso)).fetchone()[0]


def toronto_day_starts(first_ms, last_ms):
    """UTC ms of 00:00 Toronto for every date spanning [first_ms, last_ms]."""
    d0 = from_ms(first_ms).astimezone(TZ).date() - dt.timedelta(days=1)
    d1 = from_ms(last_ms).astimezone(TZ).date() + dt.timedelta(days=1)
    out, d = [], d0
    while d <= d1:
        out.append(to_ms(dt.datetime(d.year, d.month, d.day, tzinfo=TZ)))
        d += dt.timedelta(days=1)
    return np.array(out, dtype=np.int64)
