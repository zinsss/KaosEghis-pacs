from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Dict, List

import pytz

from . import history, payload, sync_client


_ROUTE_PROFILE: Dict[str, Dict[str, str]] = {
    'XRAY': {
        'modality': 'CR',
        'station_aet': 'INNOVISION',
        'route': 'INNOVISION',
        'procedure_description': 'X-RAY',
    },
    'BMD': {
        'modality': 'BMD',
        'station_aet': 'BMD',
        'route': 'BMD',
        'procedure_description': 'BMD',
    },
}


def _make_acc_no(patient_id: str, scheduled_at: datetime) -> str:
    return f"MANUAL-{scheduled_at.strftime('%Y%m%d')}-{scheduled_at.strftime('%H%M%S')}-{patient_id}"


def _normalize_study_type(study_type: str) -> str:
    if study_type not in _ROUTE_PROFILE:
        raise ValueError(f'unsupported study type: {study_type}')
    return study_type


def validate_manual_form(values: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if not (values.get('patient_id') or '').strip():
        errors.append('Patient chart number is required.')
    if not (values.get('patient_name') or '').strip():
        errors.append('Patient name is required.')
    if (values.get('patient_sex') or '').strip().upper() not in ('M', 'F', 'O'):
        errors.append('Patient sex must be M, F, or O.')
    if not (values.get('accession_no') or '').strip():
        errors.append('Accession number is required.')
    if not str(values.get('patient_birth_date') or '').isdigit() or len(str(values.get('patient_birth_date') or '')) != 8:
        errors.append('Patient DOB must be 8 digits.')
    if not str(values.get('scheduled_date') or '').isdigit() or len(str(values.get('scheduled_date') or '')) != 8:
        errors.append('Scheduled date must be 8 digits.')
    if not str(values.get('scheduled_time') or '').isdigit() or len(str(values.get('scheduled_time') or '')) != 6:
        errors.append('Scheduled time must be 6 digits.')
    if values.get('study_type') not in _ROUTE_PROFILE:
        errors.append('Study type must be XRAY or BMD.')
    return errors


def build_manual_payload_entry(values: Dict[str, Any], *, now: datetime) -> Dict[str, str]:
    study_type = _normalize_study_type(values.get('study_type'))
    route_cfg = _ROUTE_PROFILE[study_type]
    patient_id = str(values.get('patient_id') or '')
    patient_name = str(values.get('patient_name') or '')
    patient_birth_date = str(values.get('patient_birth_date') or '')
    patient_sex = str(values.get('patient_sex') or '').strip().upper()
    accession_no = str(values.get('accession_no') or '')
    scheduled_date = str(values.get('scheduled_date') or '')
    scheduled_time = str(values.get('scheduled_time') or '')
    procedure_description = str(values.get('procedure_description') or route_cfg['procedure_description'])

    return {
        'source_key': f"manual:{route_cfg['route']}:{accession_no}",
        'eghis_key': f"manual:{accession_no}",
        'patient_id': patient_id,
        'patient_name': patient_name,
        'patient_birth_date': patient_birth_date,
        'patient_sex': patient_sex,
        'accession_no': accession_no,
        'modality': route_cfg['modality'],
        'station_aet': route_cfg['station_aet'],
        'scheduled_procedure_step_description': procedure_description,
        'requested_procedure_description': procedure_description,
        'scheduled_date': scheduled_date,
        'scheduled_time': scheduled_time,
        'order_code': 'MANUAL',
        'route': route_cfg['route'],
    }


def _default_entry_values(timezone: str, study_type: str = 'XRAY') -> Dict[str, str]:
    now = datetime.now(pytz.timezone(timezone))
    study_type = _normalize_study_type(study_type)
    return {
        'study_type': study_type,
        'patient_id': '',
        'patient_name': '',
        'patient_sex': 'M',
        'patient_birth_date': now.strftime('%Y%m%d'),
        'scheduled_date': now.strftime('%Y%m%d'),
        'scheduled_time': now.strftime('%H%M%S'),
        'procedure_description': _ROUTE_PROFILE[study_type]['procedure_description'],
        'accession_no': _make_acc_no('', now),
    }


def run_manual_payload(settings, values: Dict[str, Any], *, now: datetime, sender=sync_client.post_payload, history_writer=history.append_event) -> Dict[str, Any]:
    history_path = history.history_file_for_today(settings.state_path, settings.timezone)
    errors = validate_manual_form(values)
    if errors:
        return {'posted': False, 'posted_summary': 'validation failed', 'errors': errors}

    if now.tzinfo is None:
        now = now.replace(tzinfo=pytz.timezone(settings.timezone))
    entry = build_manual_payload_entry(values, now=now)
    payload_obj = payload.build_payload([entry], now.isoformat())

    history_writer(
        history_path,
        event_type='manual_payload_created',
        source_key=entry['source_key'],
        eghis_key=entry['eghis_key'],
        patient_id=entry['patient_id'],
        modality=entry['modality'],
        route=entry['route'],
        accession_no=entry['accession_no'],
        order_code=entry['order_code'],
        result='created',
        status='pending',
    )

    if settings.dry_run:
        return {'posted': False, 'posted_summary': 'dry-run', 'payload': payload_obj}

    result = sender(settings.sync_url, payload_obj, 3)
    if result.ok:
        history_writer(
            history_path,
            event_type='manual_sync_posted',
            source_key=entry['source_key'],
            eghis_key=entry['eghis_key'],
            patient_id=entry['patient_id'],
            modality=entry['modality'],
            route=entry['route'],
            accession_no=entry['accession_no'],
            order_code=entry['order_code'],
            result=result.summary,
            status='success',
            payload_hash='',
        )
        return {'posted': True, 'posted_summary': result.summary, 'payload': payload_obj}

    history_writer(
        history_path,
        event_type='manual_sync_failed',
        source_key=entry['source_key'],
        eghis_key=entry['eghis_key'],
        patient_id=entry['patient_id'],
        modality=entry['modality'],
        route=entry['route'],
        accession_no=entry['accession_no'],
        order_code=entry['order_code'],
        result='failed',
        status='failed',
        reason=result.summary,
    )
    return {'posted': False, 'posted_summary': result.summary, 'payload': payload_obj}


def start_manual(settings) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception as exc:
        raise RuntimeError('manual mode requires Tkinter') from exc

    now = datetime.now(pytz.timezone(settings.timezone))
    route_cfg = _ROUTE_PROFILE['XRAY']

    root = tk.Tk()
    root.title('Kaoseghis PACS Manual Worklist')

    study_type = tk.StringVar(value='XRAY')
    patient_id = tk.StringVar(value='')
    patient_name = tk.StringVar(value='')
    patient_sex = tk.StringVar(value='M')
    patient_birth_date = tk.StringVar(value=now.strftime('%Y%m%d'))
    procedure_desc = tk.StringVar(value=route_cfg['procedure_description'])
    accession_no = tk.StringVar(
        value=_make_acc_no('', now),
    )
    scheduled_date = tk.StringVar(value=now.strftime('%Y%m%d'))
    scheduled_time = tk.StringVar(value=now.strftime('%H%M%S'))

    def _build_and_send():
        values = {
            'study_type': study_type.get(),
            'patient_id': patient_id.get(),
            'patient_name': patient_name.get(),
            'patient_sex': patient_sex.get(),
            'patient_birth_date': patient_birth_date.get(),
            'procedure_description': procedure_desc.get(),
            'accession_no': accession_no.get(),
            'scheduled_date': scheduled_date.get(),
            'scheduled_time': scheduled_time.get(),
        }
        errors = validate_manual_form(values)
        if errors:
            messagebox.showerror('Validation error', '\n'.join(errors))
            return
        result = run_manual_payload(settings, values, now=now, sender=sync_client.post_payload, history_writer=history.append_event)
        payload_text = json.dumps(result['payload'], ensure_ascii=False, indent=2)
        if result['posted_summary'] == 'dry-run':
            messagebox.showinfo('Dry-run', f'DRY_RUN is enabled.\n\nPayload preview:\n{payload_text}')
        elif result['posted']:
            messagebox.showinfo('Success', result['posted_summary'])
        else:
            messagebox.showerror('Failed', result['posted_summary'])

    def _update_defaults_for_study(*_args):
        profile = _ROUTE_PROFILE[study_type.get()]
        procedure_desc.set(profile['procedure_description'])
        new_accession = _make_acc_no(patient_id.get().strip(), now)
        accession_no.set(new_accession)

    def _add_row(label: str, widget: Any, row: int, *, col: int = 0, colspan: int = 1):
        tk.Label(root, text=label).grid(row=row, column=col, sticky='w', padx=4, pady=4)
        widget.grid(row=row, column=col + 1, sticky='we', padx=4, pady=4, columnspan=colspan)

    tk.Label(root, text='Study type').grid(row=0, column=0, sticky='w', padx=4, pady=4)
    tk.OptionMenu(root, study_type, 'XRAY', 'BMD', command=_update_defaults_for_study).grid(row=0, column=1, sticky='we', padx=4, pady=4)
    _add_row('Patient chart number / PatientID', tk.Entry(root, textvariable=patient_id), 1)
    _add_row('Patient name', tk.Entry(root, textvariable=patient_name), 2)
    tk.Label(root, text='Patient sex').grid(row=3, column=0, sticky='w', padx=4, pady=4)
    tk.OptionMenu(root, patient_sex, 'M', 'F', 'O').grid(row=3, column=1, sticky='we', padx=4, pady=4)
    _add_row('Patient DOB (YYYYMMDD)', tk.Entry(root, textvariable=patient_birth_date), 4)
    _add_row('Procedure description', tk.Entry(root, textvariable=procedure_desc), 5)
    _add_row('Accession number', tk.Entry(root, textvariable=accession_no), 6)
    _add_row('Scheduled date (YYYYMMDD)', tk.Entry(root, textvariable=scheduled_date), 7)
    _add_row('Scheduled time (HHMMSS)', tk.Entry(root, textvariable=scheduled_time), 8)

    tk.Button(root, text='Submit', command=_build_and_send).grid(row=9, column=0, columnspan=2, sticky='we', padx=4, pady=8)
    root.mainloop()

