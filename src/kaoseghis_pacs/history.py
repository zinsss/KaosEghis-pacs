from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict

import pytz


_FILE_LOCKS: Dict[str, Lock] = {}
_FILE_LOCKS_LOCK = Lock()


@dataclass
class HistoryEvent:
    timestamp: str
    event_type: str
    source_key: str
    eghis_key: str
    patient_id: str
    modality: str
    route: str
    accession_no: str
    order_code: str
    result: str
    status: str
    reason: str | None = None


def history_file_for_today(state_path: str, timezone: str) -> str:
    state_dir = Path(state_path).parent
    if str(state_dir) == '.':
        state_dir = Path('state')
    today = datetime.now(pytz.timezone(timezone)).strftime('%Y%m%d')
    return str(state_dir / f'history-{today}.jsonl')


def _to_str(value: Any) -> str:
    if value is None:
        return ''
    return str(value)


def _line_locks(path: str) -> Lock:
    with _FILE_LOCKS_LOCK:
        lock = _FILE_LOCKS.get(path)
        if lock is None:
            lock = Lock()
            _FILE_LOCKS[path] = lock
        return lock


def append_event(
    history_path: str,
    event_type: str,
    source_key: str = '',
    eghis_key: str = '',
    patient_id: str = '',
    modality: str = '',
    route: str = '',
    accession_no: str = '',
    order_code: str = '',
    result: str = '',
    status: str = '',
    reason: str | None = None,
    **extra: Any,
) -> None:
    event = HistoryEvent(
        timestamp=datetime.now().isoformat(timespec='seconds'),
        event_type=event_type,
        source_key=_to_str(source_key),
        eghis_key=_to_str(eghis_key),
        patient_id=_to_str(patient_id),
        modality=_to_str(modality),
        route=_to_str(route),
        accession_no=_to_str(accession_no),
        order_code=_to_str(order_code),
        result=_to_str(result),
        status=_to_str(status),
        reason=_to_str(reason),
    )
    payload = event.__dict__.copy()
    payload['timestamp'] = event.timestamp
    payload.update(extra)

    # Avoid writing common PII patterns even if callers pass them by mistake.
    for forbidden in ('patient_name', 'rrn', 'resid', 'phone', 'chart', 'jumin', 'resident_no'):
        payload.pop(forbidden, None)
    if payload.get('reason') == '':
        payload.pop('reason', None)

    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _line_locks(str(path))
    with lock:
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write('\n')
