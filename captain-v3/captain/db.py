"""SQLite ledger: WAL, transactional, single writer (flock + BEGIN IMMEDIATE)."""
import contextlib, fcntl, os, sqlite3, time
from .util import ROOT, home

SCHEMA_VERSION = 1

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, job TEXT NOT NULL, scheduled_ts TEXT NOT NULL, strategy_version TEXT NOT NULL,
  config_version TEXT, config_hash TEXT, code_version TEXT, status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 1,
  pid INTEGER, started_ts TEXT, finished_ts TEXT, error TEXT, rows_written TEXT, data_cutoff_ts TEXT, receipt TEXT,
  trigger TEXT, synthetic INTEGER NOT NULL DEFAULT 0,
  UNIQUE(job, scheduled_ts, strategy_version));
CREATE TABLE IF NOT EXISTS run_attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, attempt INTEGER NOT NULL, pid INTEGER,
  started_ts TEXT, finished_ts TEXT, status TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS market_data(
  id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, instrument TEXT NOT NULL, timeframe TEXT NOT NULL,
  derivation TEXT NOT NULL, candle_start_ms INTEGER NOT NULL, candle_end_ms INTEGER NOT NULL,
  open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL, volume REAL,
  received_ts TEXT NOT NULL, is_final INTEGER NOT NULL, raw_ref TEXT, synthetic INTEGER NOT NULL DEFAULT 0,
  UNIQUE(provider, instrument, timeframe, derivation, candle_start_ms));
CREATE INDEX IF NOT EXISTS md_lookup ON market_data(provider, instrument, timeframe, candle_start_ms);
CREATE TABLE IF NOT EXISTS data_revisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, instrument TEXT, timeframe TEXT, candle_start_ms INTEGER,
  stored TEXT, received TEXT, received_ts TEXT);
CREATE TABLE IF NOT EXISTS snapshots(
  snapshot_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, market TEXT, cutoff_ts TEXT NOT NULL, created_ts TEXT NOT NULL,
  freshness TEXT, features TEXT, calc_versions TEXT, features_hash TEXT, synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS forecasts(
  forecast_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, market TEXT NOT NULL, model_id TEXT NOT NULL, model_version TEXT,
  is_official INTEGER NOT NULL, created_ts TEXT NOT NULL, cutoff_ts TEXT NOT NULL, session_date TEXT NOT NULL,
  target_start_ts TEXT NOT NULL, target_end_ts TEXT NOT NULL, outcome_definition TEXT NOT NULL,
  p_up REAL, p_down REAL, p_range REAL, probabilities_available INTEGER NOT NULL,
  sample_count INTEGER, sample_first_date TEXT, sample_last_date TEXT, smoothing TEXT, evidence TEXT,
  snapshot_id TEXT, synthetic INTEGER NOT NULL DEFAULT 0,
  UNIQUE(session_date, market, model_id, model_version));
CREATE TABLE IF NOT EXISTS signals(
  signal_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, snapshot_id TEXT, market TEXT NOT NULL, setup TEXT NOT NULL,
  setup_version TEXT NOT NULL, side TEXT NOT NULL, trigger_bar_start_ts TEXT, trigger_bar_end_ts TEXT, decision_ts TEXT,
  levels TEXT, horizon_ts TEXT, gates TEXT, passed INTEGER NOT NULL, rank INTEGER, synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS decisions(
  decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, signal_id TEXT, market TEXT, action TEXT NOT NULL,
  reason_code TEXT NOT NULL, detail TEXT, snapshot_id TEXT, risk_model TEXT, cost_model TEXT, committed_ts TEXT NOT NULL,
  synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS trades(
  trade_id TEXT PRIMARY KEY, decision_id TEXT NOT NULL UNIQUE, session_date TEXT NOT NULL, market TEXT NOT NULL,
  side TEXT NOT NULL, setup TEXT NOT NULL, status TEXT NOT NULL, notional_usd REAL, collateral_usd REAL, leverage REAL,
  stop_price REAL, target_r REAL, target_price REAL, stop_rule TEXT, commit_ts TEXT NOT NULL, expires_ts TEXT,
  entry_ts TEXT, entry_price REAL, exit_ts TEXT, exit_price REAL, exit_reason TEXT, ambiguous INTEGER NOT NULL DEFAULT 0,
  last_processed_ms INTEGER, gross_pnl REAL, total_costs REAL, net_pnl REAL, synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS trade_events(
  event_id TEXT PRIMARY KEY, trade_id TEXT, seq INTEGER NOT NULL, event_type TEXT NOT NULL, event_ts TEXT NOT NULL,
  recorded_ts TEXT NOT NULL, price REAL, amounts TEXT, trading_cash_delta REAL NOT NULL DEFAULT 0,
  reserve_delta REAL NOT NULL DEFAULT 0, external_flow INTEGER NOT NULL DEFAULT 0, evidence TEXT, run_id TEXT,
  supersedes TEXT, synthetic INTEGER NOT NULL DEFAULT 0,
  UNIQUE(trade_id, event_type, seq));
CREATE TABLE IF NOT EXISTS costs(
  cost_id TEXT PRIMARY KEY, trade_id TEXT, decision_id TEXT, component TEXT NOT NULL, amount_usd REAL NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('quote','estimate','modeled')), phase TEXT NOT NULL, source TEXT,
  interval_start TEXT, interval_end TEXT, evidence TEXT, synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS scores(
  score_id TEXT PRIMARY KEY, kind TEXT NOT NULL, forecast_id TEXT, trade_id TEXT, status TEXT NOT NULL,
  outcome TEXT, ref_start_price REAL, ref_end_price REAL, return_pct REAL, brier REAL, scored_ts TEXT NOT NULL,
  data_refs TEXT, ambiguous INTEGER NOT NULL DEFAULT 0, exclusion_reason TEXT, run_id TEXT,
  synthetic INTEGER NOT NULL DEFAULT 0, UNIQUE(kind, forecast_id, trade_id));
CREATE TABLE IF NOT EXISTS experiments(
  experiment_id TEXT PRIMARY KEY, hypothesis TEXT, mechanism TEXT, registered_params TEXT, data_splits TEXT,
  trial_count INTEGER, results TEXT, status TEXT, created_ts TEXT, decided_ts TEXT);
CREATE TABLE IF NOT EXISTS deliveries(
  delivery_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, payload_hash TEXT NOT NULL, destination TEXT NOT NULL,
  queued_ts TEXT NOT NULL, attempted_ts TEXT, acknowledged_ts TEXT, status TEXT NOT NULL, receipt TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS ledger_state(
  id INTEGER PRIMARY KEY CHECK(id=1), trading_cash REAL NOT NULL, reserve REAL NOT NULL, updated_ts TEXT, last_event_id TEXT);
CREATE TABLE IF NOT EXISTS day_state(
  session_date TEXT PRIMARY KEY, start_trading_equity REAL NOT NULL, start_reserve REAL NOT NULL,
  locked INTEGER NOT NULL DEFAULT 0, lock_ts TEXT, lock_reason TEXT, created_ts TEXT, synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS borrow_snapshots(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fetched_ts TEXT NOT NULL, asset TEXT NOT NULL, long_hourly_pct REAL,
  short_hourly_pct REAL, source TEXT, run_id TEXT, raw TEXT, synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS corrections(
  correction_id TEXT PRIMARY KEY, entity_table TEXT NOT NULL, entity_id TEXT NOT NULL, field TEXT NOT NULL,
  recorded_value TEXT, corrected_value TEXT, reason TEXT NOT NULL, affects_outcome INTEGER NOT NULL, recorded_ts TEXT NOT NULL, code_version TEXT);
CREATE TABLE IF NOT EXISTS hypothetical_outcomes(
  hyp_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('SKIPPED_PROSPECTIVE','HINDSIGHT')), hypothetical INTEGER NOT NULL DEFAULT 1 CHECK(hypothetical=1),
  excluded_from_official INTEGER NOT NULL DEFAULT 1 CHECK(excluded_from_official=1), signal_id TEXT, decision_id TEXT, skip_reason TEXT,
  session_date TEXT, market TEXT, setup TEXT, side TEXT, created_ts TEXT NOT NULL, commit_ts TEXT, expires_ts TEXT, status TEXT NOT NULL,
  notional_usd REAL, size_flag TEXT, initial_risk_usd REAL, stop_price REAL, target_r REAL, target_price REAL, cost_fractions TEXT,
  entry_ts TEXT, entry_price REAL, proxy_entry_open REAL, exit_ts TEXT, exit_price REAL, exit_reason TEXT, ambiguous INTEGER DEFAULT 0,
  last_processed_ms INTEGER, mae_px REAL, mae_ts TEXT, mfe_px REAL, mfe_ts TEXT, mae_usd REAL, mfe_usd REAL, mae_r REAL, mfe_r REAL,
  gross_pnl REAL, fees_usd REAL, financing_usd REAL, slippage_usd REAL, net_pnl REAL, net_r REAL, cost_sensitivity TEXT,
  condition_labels TEXT, note TEXT, synthetic INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS experiment_trials(
  trial_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, variant TEXT NOT NULL, params TEXT, feature_set TEXT,
  registered_ts TEXT NOT NULL, train_cutoff TEXT, forward_start TEXT, forward_end TEXT, status TEXT NOT NULL,
  n_obs INTEGER, mean_r REAL, sd_r REAL, sharpe_per_obs REAL, skew REAL, kurtosis REAL, results TEXT, updated_ts TEXT);
CREATE TABLE IF NOT EXISTS quotes(
  quote_id TEXT PRIMARY KEY, decision_ref TEXT, run_id TEXT, requested TEXT, response TEXT, stderr TEXT,
  exit_code INTEGER, quoted_ts TEXT, synthetic INTEGER NOT NULL DEFAULT 0);
"""


def db_path():
    return os.environ.get("CAPTAIN_DB") or os.path.join(home(), "captain.db")


def connect(path=None):
    path = path or db_path()
    con = sqlite3.connect(path, timeout=60, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=60000")
    return con


MIGRATIONS = {
    "trades": [("initial_risk_usd", "REAL"), ("net_r", "REAL"), ("proxy_entry_open", "REAL"), ("mae_px", "REAL"), ("mae_ts", "TEXT"), ("mfe_px", "REAL"),
               ("mfe_ts", "TEXT"), ("mae_usd", "REAL"), ("mfe_usd", "REAL"), ("mae_r", "REAL"), ("mfe_r", "REAL"), ("fees_usd", "REAL"),
               ("financing_usd", "REAL"), ("slippage_usd", "REAL"), ("cost_sensitivity", "TEXT"), ("condition_labels", "TEXT")],
    "signals": [("condition_labels", "TEXT"), ("labels_version", "TEXT"), ("descriptive_features", "TEXT")],
    "runs": [("duration_s", "REAL"), ("data_quality", "TEXT"), ("failure_class", "TEXT")],
    "experiments": [("trial_count_total", "INTEGER"), ("train_cutoff", "TEXT"), ("forward_start", "TEXT"), ("forward_end", "TEXT"), ("comparison_design", "TEXT")],
}


def migrate(con):
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        for c, t in cols:
            if c not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {c} {t}")


def init(con, initial_capital=50.0):
    con.executescript(SCHEMA)
    migrate(con)
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    con.execute("INSERT OR IGNORE INTO ledger_state(id,trading_cash,reserve,updated_ts,last_event_id) VALUES(1,?,0,NULL,NULL)", (initial_capital,))


@contextlib.contextmanager
def tx(con):
    """Atomic transaction; everything inside commits together or not at all."""
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")


@contextlib.contextmanager
def writer_lock(timeout_s=180, path=None):
    """Single ledger writer across processes (flock). Blocks up to timeout_s."""
    path = path or (db_path() + ".lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    t0 = time.time()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() - t0 > timeout_s:
                os.close(fd)
                raise TimeoutError("writer lock busy")
            time.sleep(0.2)
    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
