from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List

import pytz


def pick_anchor_datetime(row: Dict[str, Any]) -> str:
    for key in ('anchor_dttm', 'scheduled_dttm', 'imaging_request_dttm', 'trigger_dttm', 'replica_dttm'):
        value = row.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            return value
    return ''


def normalize_accession_no(row: Dict[str, Any]) -> str:
    accession = (row.get('accession_no') or '').strip()
    if accession:
        return accession
    eghis_key = (row.get('eghis_key') or '').strip().replace('_', '-')
    return f'ACC-{eghis_key}' if eghis_key else 'ACC-UNKNOWN'


def _parse_datetime_from_raw(raw: str) -> datetime | None:
    cleaned = ''.join(ch for ch in str(raw) if ch.isdigit())
    if not cleaned:
        return None
    for fmt in ('%Y%m%d%H%M%S', '%Y%m%d%H%M', '%Y%m%d'):
        if len(cleaned) >= len(fmt.replace('%', '')):
            try:
                return datetime.strptime(cleaned[: len(fmt.replace('%', ''))], fmt)
            except ValueError:
                pass
    return None


def scheduled_date_time(row: Dict[str, Any], timezone: str, default_dt: datetime) -> tuple[str, str]:
    dt_raw = pick_anchor_datetime(row)
    parsed = _parse_datetime_from_raw(dt_raw)
    tz = pytz.timezone(timezone)
    dt = tz.localize(parsed) if parsed else default_dt
    return dt.strftime('%Y%m%d'), dt.strftime('%H%M%S')


def build_payload_entries(rows: List[Dict[str, Any]], routes: Dict[str, Dict[str, str]], timezone: str) -> List[Dict[str, Any]]:
    now = datetime.now(pytz.timezone(timezone))
    out: List[Dict[str, Any]] = []
    for row in rows:
        route_name = row['route_name']
        if route_name not in routes:
            continue
        route = routes[route_name]
        scheduled_date, scheduled_time = scheduled_date_time(row, timezone, now)
        out.append({
            'source_key': f"mwl:{row['mwl_key']}",
            'eghis_key': row['eghis_key'],
            'patient_id': row['patient_id'],
            'patient_name': row['patient_name'],
            'patient_birth_date': row['patient_birth_date'],
            'patient_sex': row['patient_sex'],
            'accession_no': normalize_accession_no(row),
            'modality': route['modality'],
            'station_aet': route['station_aet'],
            'scheduled_procedure_step_description': route['description'],
            'requested_procedure_description': row.get('scheduled_proc_desc') or row.get('requested_proc_desc') or route['description'],
            'scheduled_date': scheduled_date,
            'scheduled_time': scheduled_time,
            'order_code': row['ord_cd'],
            'route': route_name,
        })
    return out


def build_payload(entries: List[Dict[str, Any]], generated_at: str) -> Dict[str, Any]:
    return {
        'source': 'kaoseghis-pacs',
        'generated_at': generated_at,
        'entries': entries,
    }


def payload_hash(payload_dict: Dict[str, Any]) -> str:
    payload_for_hash = dict(payload_dict)
    payload_for_hash.pop('generated_at', None)
    raw = json.dumps(payload_for_hash, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def sample_payload(timezone: str = 'Asia/Seoul') -> Dict[str, Any]:
    now = datetime.now(pytz.timezone(timezone))
    return {
        'source': 'kaoseghis-pacs',
        'generated_at': now.isoformat(),
        'entries': [
            {
                'source_key': 'mwl:5',
                'eghis_key': '261864_1_0',
                'patient_id': '7435',
                'patient_name': '홍길동',
                'patient_birth_date': '19830210',
                'patient_sex': 'M',
                'accession_no': '5',
                'modality': 'BMD',
                'station_aet': 'BMD',
                'scheduled_procedure_step_description': 'BMD',
                'requested_procedure_description': 'BMD',
                'scheduled_date': now.strftime('%Y%m%d'),
                'scheduled_time': now.strftime('%H%M%S'),
                'order_code': 'HC342',
                'route': 'BMD',
            }
        ],
    }
