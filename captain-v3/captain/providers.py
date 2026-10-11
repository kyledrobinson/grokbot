"""Public, keyless market-data adapters. Primary: Binance spot (data-api.binance.vision mirror,
api.binance.com is geo-blocked from this box: HTTP 451). Secondary cross-check: Coinbase Exchange."""
import gzip, json, os, time, urllib.request
from .util import ROOT, home, now_utc, iso, sha256_text

BINANCE_HOSTS = ["https://data-api.binance.vision", "https://api.binance.us"]
COINBASE = "https://api.exchange.coinbase.com"
UA = {"User-Agent": "captain-v3/1 (paper research)"}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _save_raw(provider, instrument, body, received):
    d = os.path.join(home(), "raw", provider, received.strftime("%Y-%m-%d"))
    os.makedirs(d, exist_ok=True)
    name = f"{received.strftime('%H%M%S%f')}-{instrument}.json.gz"
    p = os.path.join(d, name)
    with gzip.open(p, "wb") as f:
        f.write(body)
    return os.path.relpath(p, home()) + "#sha256=" + sha256_text(body.decode("utf-8", "replace"))[:16]


def binance_klines(symbol, interval, start_ms, end_ms=None, save_raw=True, max_pages=500):
    """Returns list of (batch_rows, received_dt, raw_ref, host). Rows: [start_ms, o,h,l,c,v, close_ms]."""
    step = {"1m": 60_000, "1h": 3_600_000, "15m": 900_000}[interval]
    out = []
    pages = 0
    while pages < max_pages:
        pages += 1
        path = f"/api/v3/klines?symbol={symbol}&interval={interval}&startTime={start_ms}&limit=1000"
        if end_ms:
            path += f"&endTime={end_ms}"
        body, host, last = None, None, None
        for h in BINANCE_HOSTS:
            for attempt in range(3):
                try:
                    body = _get(h + path)
                    host = h
                    break
                except Exception as e:
                    last = e
                    time.sleep(0.5 + attempt)
            if body is not None:
                break
        if body is None:
            raise RuntimeError(f"binance fetch failed {symbol} {interval}: {last}")
        received = now_utc()
        rows = json.loads(body)
        raw_ref = _save_raw("binance_spot", f"{symbol}-{interval}", body, received) if save_raw else f"not-saved:{host}"
        now_ms = int(received.timestamp() * 1000)
        final = [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), int(r[6])] for r in rows if int(r[6]) < now_ms]
        out.append((final, received, raw_ref, host))
        if len(rows) < 1000:
            break
        start_ms = int(rows[-1][0]) + step
        if end_ms and start_ms > end_ms:
            break
        time.sleep(0.12)
    return out


def coinbase_1m(product, start_dt, end_dt, save_raw=True):
    """Coinbase Exchange public candles, 300 per request. Rows [time_s, low, high, open, close, volume]."""
    import datetime as dt
    out = []
    cur = start_dt
    while cur < end_dt:
        nxt = min(cur + dt.timedelta(minutes=300), end_dt)
        url = f"{COINBASE}/products/{product}/candles?granularity=60&start={iso(cur)}&end={iso(nxt)}"
        body, last = None, None
        for attempt in range(3):
            try:
                body = _get(url)
                break
            except Exception as e:
                last = e
                time.sleep(1 + attempt)
        if body is None:
            raise RuntimeError(f"coinbase fetch failed {product}: {last}")
        received = now_utc()
        rows = json.loads(body)
        raw_ref = _save_raw("coinbase_exchange", product, body, received) if save_raw else "not-saved"
        now_ms = int(received.timestamp() * 1000)
        final = []
        for r in rows:
            s = int(r[0]) * 1000
            if s + 60_000 <= now_ms:
                final.append([s, float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5]), s + 59_999])
        final.sort()
        out.append((final, received, raw_ref, COINBASE))
        cur = nxt
        time.sleep(0.25)
    return out
