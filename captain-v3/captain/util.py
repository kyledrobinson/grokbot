import datetime as dt, hashlib, json, os, subprocess
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Toronto")
UTC = dt.timezone.utc
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def home():
    """Data root (DB, exports, backups, raw, logs, state). Tests point CAPTAIN_HOME at a temp dir."""
    return os.environ.get("CAPTAIN_HOME") or ROOT



def now_utc():
    # CAPTAIN_FAKE_NOW is only used by tests (labeled synthetic); never set in production.
    f = os.environ.get("CAPTAIN_FAKE_NOW")
    if f:
        return parse_ts(f)
    return dt.datetime.now(UTC)


def parse_ts(s):
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def iso(d):
    if d is None:
        return None
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def to_ms(d):
    return int(round(d.timestamp() * 1000))


def from_ms(ms):
    return dt.datetime.fromtimestamp(ms / 1000, UTC)


def et(d):
    return d.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def toronto_dt(date, hhmm):
    """Toronto wall time -> aware UTC datetime (DST aware)."""
    h, m = map(int, hhmm.split(":"))
    local = dt.datetime(date.year, date.month, date.day, h, m, tzinfo=TZ)
    return local.astimezone(UTC)


def toronto_date(d):
    return d.astimezone(TZ).date()


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(s):
    return hashlib.sha256(s.encode()).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_version():
    try:
        rev = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "captain", "config", "bin"], capture_output=True, text=True, timeout=5).stdout.strip()
        return (rev or "nogit") + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"
