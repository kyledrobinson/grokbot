"""Read-only, timestamp-aware bar access for morning tags. captain.db is opened with mode=ro."""
import datetime as dt, sqlite3
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Toronto")
UTC = dt.timezone.utc
M1, M15, H1 = 60_000, 900_000, 3_600_000


def connect_ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_ms(s):
    return int(round(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000))


def et_ms(d, hhmm):
    h, m = map(int, hhmm.split(":"))
    return int(dt.datetime(d.year, d.month, d.day, h, m, tzinfo=TZ).timestamp() * 1000)


def et_date(ms):
    return dt.datetime.fromtimestamp(ms / 1000, TZ).date()


def et_str(ms):
    return dt.datetime.fromtimestamp(ms / 1000, TZ).strftime("%Y-%m-%d %H:%M %Z")


class Bars:
    """All final, non-synthetic bars for one instrument, keyed by candle_start_ms.
    Every bar carries its received time; callers only ever ask for bars that END at/before the moment they describe,
    and record whether all bars used were received within the allowance ('live') or arrived later ('reconstructed')."""

    def __init__(self, con, provider, symbol):
        def load(tf, der):
            q = ("SELECT candle_start_ms,candle_end_ms,open,high,low,close,received_ts FROM market_data WHERE provider=? AND instrument=? "
                 "AND timeframe=? AND derivation=? AND is_final=1 AND synthetic=0 ORDER BY candle_start_ms")
            return {r[0]: {"start": r[0], "end": r[1], "o": r[2], "h": r[3], "l": r[4], "c": r[5], "recv": parse_ms(r[6])}
                    for r in con.execute(q, (provider, symbol, tf, der))}
        self.m1 = load("1m", "native_1m")
        self.h1n = load("1h", "native_1h")
        self.m15 = load("15m", "agg_1m")
        self._h = {}

    @staticmethod
    def _agg(rows, start, end, src):
        return {"start": start, "end": end, "o": rows[0]["o"], "h": max(r["h"] for r in rows), "l": min(r["l"] for r in rows),
                "c": rows[-1]["c"], "recv": max(r["recv"] for r in rows), "src": src, "n": len(rows)}

    def hour(self, start):
        if start in self._h:
            return self._h[start]
        rows = [self.m1.get(start + i * M1) for i in range(60)]
        if all(rows):
            b = self._agg(rows, start, start + H1, "1m")
        elif start in self.h1n:
            b = dict(self.h1n[start], src="1h_native", n=1)
        else:
            b = None
        self._h[start] = b
        return b

    def window(self, start, end):
        """OHLC over [start,end) from 1m (all bars required) else from complete native/agg hours. None if incomplete."""
        n = (end - start) // M1
        rows = [self.m1.get(start + i * M1) for i in range(n)]
        if all(rows):
            return self._agg(rows, start, end, "1m")
        if (end - start) % H1 == 0 and start % H1 == 0:
            hs = [self.hour(start + i * H1) for i in range((end - start) // H1)]
            if all(hs):
                b = self._agg(hs, start, end, "1h_native" if any(h["src"] == "1h_native" for h in hs) else "1m")
                return b
        return None

    def hours(self, start, end):
        out = []
        t = start
        while t < end:
            b = self.hour(t)
            if b:
                out.append(b)
            t += H1
        return out

    def bar15(self, start):
        return self.m15.get(start)
