"""Deterministic indicators. ATR: Wilder smoothing seeded with SMA of first `period` true ranges
(first TR = high-low). EMA: seeded with SMA of first `period` closes, k = 2/(period+1)."""


def true_ranges(bars):
    out = []
    prev = None
    for b in bars:
        if prev is None:
            out.append(b["high"] - b["low"])
        else:
            out.append(max(b["high"] - b["low"], abs(b["high"] - prev), abs(b["low"] - prev)))
        prev = b["close"]
    return out


def atr_wilder(bars, period=14):
    tr = true_ranges(bars)
    out = [None] * len(tr)
    if len(tr) < period:
        return out
    a = sum(tr[:period]) / period
    out[period - 1] = a
    for i in range(period, len(tr)):
        a = (a * (period - 1) + tr[i]) / period
        out[i] = a
    return out


def ema(values, period=50):
    out = [None] * len(values)
    if len(values) < period:
        return out
    e = sum(values[:period]) / period
    out[period - 1] = e
    k = 2.0 / (period + 1)
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out


def contiguous(bars, span_ms):
    return all(bars[i]["candle_start_ms"] - bars[i - 1]["candle_start_ms"] == span_ms for i in range(1, len(bars)))
