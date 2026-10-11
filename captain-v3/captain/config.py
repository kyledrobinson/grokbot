import json, os
from .util import ROOT, sha256_text, canon

DEFAULT = os.path.join(ROOT, "config", "strategy-v3.1.1.json")


def load(path=None):
    path = path or os.environ.get("CAPTAIN_CONFIG") or DEFAULT
    with open(path) as f:
        cfg = json.load(f)
    cfg["_path"] = path
    cfg["_hash"] = sha256_text(canon({k: v for k, v in cfg.items() if not k.startswith("_")}))[:16]
    return cfg


def version_tag(cfg):
    return f"{cfg['config_version']}/{cfg['strategy_version']}#{cfg['_hash']}"
