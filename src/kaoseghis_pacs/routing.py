from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass(frozen=True)
class Route:
    route_name: str
    modality: str
    station_aet: str
    description: str


@dataclass(frozen=True)
class RoutedItem:
    row: Dict[str, Any]
    route: Optional[Route]
    ignored_reason: Optional[str]


def parse_eghis_key(eghis_key: str) -> tuple[str, str, str]:
    parts = (eghis_key or '').split('_')
    if len(parts) < 3:
        return '', '', ''
    return parts[0], parts[1], parts[2]


def should_route_row(row: Dict[str, Any], bmd_order_codes: Iterable[str]) -> RoutedItem:
    if (row.get('scheduled_proc_status') or '').strip() != '100':
        return RoutedItem(row, None, 'inactive status')

    if (row.get('proc_dept_cd') or '').strip().upper() != 'XRAY':
        return RoutedItem(row, None, 'non-XRAY department')

    if (row.get('dc_yn') or 'N').strip().upper() == 'Y':
        return RoutedItem(row, None, 'cancelled')

    scheduled_modality = (row.get('scheduled_modality') or '').strip().upper()
    ord_cd = (row.get('ord_cd') or '').strip().upper()
    bmd_set = {c.upper() for c in bmd_order_codes}

    if scheduled_modality == 'BMD' or ord_cd in bmd_set:
        return RoutedItem(
            row,
            Route('BMD', 'BMD', 'BMD', 'BMD'),
            None,
        )

    if scheduled_modality == 'DR':
        return RoutedItem(
            row,
            Route('INNOVISION', 'CR', 'INNOVISION', 'X-RAY'),
            None,
        )

    return RoutedItem(row, None, 'unknown modality')
