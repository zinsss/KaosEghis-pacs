from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class MWLAttributeDict(dict):
    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _str_or_empty(value: Any) -> str:
    if value is None:
        return ''
    return str(value)


def _pick_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value) != '':
            return _str_or_empty(value)
    return ''


def load_current_worklist(path: str = 'config/current_worklist.json') -> list[dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    if isinstance(payload, dict) and 'entries' in payload:
        return payload['entries']
    if isinstance(payload, list):
        return payload
    raise ValueError('current_worklist format not supported')


def filter_by_modality(
    rows: Iterable[Mapping[str, Any]],
    *,
    modality: str,
) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if _str_or_empty(row.get('modality')) == modality]


def build_mwl_datasets(rows: Iterable[Mapping[str, Any]]) -> list[MWLAttributeDict]:
    return [to_mwl_dataset(row) for row in rows]


def to_mwl_dataset(row: Mapping[str, Any]) -> MWLAttributeDict:
    patient_name = _pick_text(
        row,
        'patient_name',
        'PatientName',
    )
    requested_description = _pick_text(
        row,
        'requested_procedure_description',
        'RequestedProcedureDescription',
    )
    scheduled_description = _pick_text(
        row,
        'scheduled_procedure_step_description',
        'ScheduledProcedureStepDescription',
        'scheduled_proc_desc',
    )

    dataset = MWLAttributeDict(
        {
            'SpecificCharacterSet': 'ISO_IR 192',
            'PatientName': patient_name,
            'RequestedProcedureDescription': requested_description,
            'ScheduledProcedureStepSequence': [
                MWLAttributeDict(
                    {'ScheduledProcedureStepDescription': scheduled_description},
                ),
            ],
        },
    )

    for source_field, target_field in [
        ('patient_id', 'PatientID'),
        ('patient_birth_date', 'PatientBirthDate'),
        ('patient_sex', 'PatientSex'),
        ('accession_no', 'AccessionNumber'),
        ('modality', 'Modality'),
        ('station_aet', 'ScheduledStationAETitle'),
        ('route', 'ScheduledProcedureStepLocation'),
        ('order_code', 'RequestedProcedureID'),
    ]:
        value = _pick_text(row, source_field)
        if value:
            dataset[target_field] = value

    return dataset
