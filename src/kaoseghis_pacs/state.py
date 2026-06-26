from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LastState:
    payload_hash: str | None = None


def load_state(path: str) -> LastState:
    p = Path(path)
    if not p.exists():
        return LastState(None)
    try:
        return LastState(payload_hash=json.loads(p.read_text(encoding='utf-8')).get('payload_hash'))
    except (OSError, json.JSONDecodeError):
        return LastState(None)


def save_state(path: str, payload_hash: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({'payload_hash': payload_hash}, ensure_ascii=False, indent=2), encoding='utf-8')
