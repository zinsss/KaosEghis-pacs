from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class SyncResult:
    ok: bool
    status_code: Optional[int]
    summary: str


def post_payload(url: str, payload: Dict[str, Any], timeout: int) -> SyncResult:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        return SyncResult(response.ok, response.status_code, response.text[:200])
    except requests.RequestException as exc:
        return SyncResult(False, None, str(exc))
